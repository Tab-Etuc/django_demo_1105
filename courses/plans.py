from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Q
from django.shortcuts import get_object_or_404

from .academic import (
    CompletedCourse,
    CoursePrerequisite,
    FailedCourseAttempt,
    PlannedCourse,
    StudyPlan,
)
from .api import VersionConflict, endpoint, serialize_course
from .models import Course
from .selection import enrolled, graduation_requirements, student_info


def curriculum_courses(info):
    return (
        Course.objects.filter(
            Q(curriculum_year=info["admission_year"]) | Q(curriculum_year__isnull=True),
            category__in=["required", "general_base", "pe"],
            program_type=info["program_type"],
            recommended_term__range=(1, 8),
        )
        .filter(
            Q(department=info["department"]) | Q(category__in=["general_base", "pe"]),
        )
        .order_by("recommended_term", "code")
    )


def plan_data(student):
    info = student_info(student)
    requirements = graduation_requirements(info)
    plan = StudyPlan.objects.filter(student=student).first()
    entries = list(plan.entries.select_related("course")) if plan else []
    overrides = {entry.course_id: entry for entry in entries}
    presets = list(curriculum_courses(info))
    finished = list(CompletedCourse.objects.filter(student=student).select_related("course"))
    finished_ids = {entry.course_id for entry in finished}
    records = enrolled(student, info["semester"])
    selected_ids = {record.offering.course_id for record in records}
    failures = list(FailedCourseAttempt.objects.filter(student=student).select_related("course"))
    term_count = (
        8
        if info["program_type"] == "four_year"
        else max(
            [4]
            + [entry.term for entry in entries]
            + [min(8, item.term + 1) for item in failures]
            + [course.recommended_term for course in presets if course.recommended_term]
        )
    )
    current_term = min(
        term_count, max(1, (info["grade"] - 1) * 2 + (2 if info["semester"].endswith("-2") else 1))
    )
    terms = [{"term": number, "credits": 0, "courses": []} for number in range(1, term_count + 1)]
    located = {}
    warnings = []
    latest_failures = {}
    for failure in failures:
        latest_failures[failure.course_id] = max(
            latest_failures.get(failure.course_id, 0), failure.term
        )

    def add(course, term, source, *, entry_id=None, position=0, locked=False):
        # Legacy reset operations may have removed the retake override. Keep the
        # failed attempt and the active retake in distinct semesters on reads.
        last_failed = latest_failures.get(course.pk, 0)
        if last_failed and term <= last_failed:
            term = min(8, last_failed + 1)
        terms[term - 1]["courses"].append(
            {
                "id": entry_id,
                "course": serialize_course(course),
                "locked": locked,
                "position": position,
                "source": source,
                "officially_selected": course.pk in selected_ids,
                "is_retake": bool(last_failed),
            }
        )
        terms[term - 1]["credits"] += course.credits
        located[course.pk] = term

    for course in presets:
        if course.pk not in overrides:
            add(course, course.recommended_term, "curriculum", locked=course.pk in finished_ids)

    for record in records:
        course = record.offering.course
        if course.pk not in located and course.pk not in overrides:
            add(course, current_term, "enrolled", locked=True)

    for entry in entries:
        add(
            entry.course,
            entry.term,
            "student",
            entry_id=entry.pk,
            position=entry.position,
            locked=entry.course_id in finished_ids,
        )
        if entry.course_id in selected_ids and entry.term != current_term:
            warnings.append(
                {
                    "course": entry.course.name,
                    "message": f"{entry.course.name}已正式配課，移到第 {entry.term} 學期僅更新四年規劃；正式退選仍需另行辦理。",
                }
            )

    for failure in failures:
        if failure.course_id not in located:
            add(failure.course, min(8, latest_failures[failure.course_id] + 1), "retake")

    for failed in failures:
        terms[failed.term - 1]["courses"].append(
            {
                "id": None,
                "course": serialize_course(failed.course),
                "locked": True,
                "source": "failed",
                "position": 9999,
                "officially_selected": False,
                "failed": True,
                "can_restore": failed.term == latest_failures[failed.course_id],
            }
        )

    for link in CoursePrerequisite.objects.filter(course_id__in=located).select_related(
        "course", "required_course"
    ):
        earlier = located.get(link.required_course_id)
        if link.required_course_id not in finished_ids and (
            earlier is None or earlier >= located[link.course_id]
        ):
            warnings.append(
                {
                    "course": link.course.name,
                    "required": link.required_course.name,
                    "message": f"{link.course.name}的先修課程「{link.required_course.name}」尚未排在較早學期。",
                }
            )

    courses_by_id = {
        entry["course"]["id"]: entry["course"]
        for term in terms
        for entry in term["courses"]
        if entry["source"] != "failed"
    }
    courses = list(courses_by_id.values())
    covered = list(
        {
            **courses_by_id,
            **{item.course_id: serialize_course(item.course) for item in finished},
        }.values()
    )
    professional = sum(
        course["credits"] for course in courses if course["category"] == "professional_elective"
    )
    general_core = {
        area: sum(
            course["credits"]
            for course in courses
            if course["category"] == "general_core" and course["general_area"] == area
        )
        for area in ("civic", "sustainability", "aesthetics")
    }
    return {
        "version": plan.version if plan else 0,
        "terms": terms,
        "available_courses": [
            serialize_course(course)
            for course in Course.objects.filter(
                program_type=info["program_type"],
            ).exclude(category__in=("required", "general_base", "pe"))
            if course.pk not in courses_by_id and course.pk not in finished_ids
        ],
        "completed_courses": [
            {
                "course": serialize_course(item.course),
                "status": item.status,
                "semester": item.completed_semester,
            }
            for item in finished
        ],
        "total_planned_credits": sum(term["credits"] for term in terms),
        "graduation": {
            "target": requirements["target"],
            "professional_target": requirements["professional"],
            "professional_planned": professional,
            "general_core_planned": general_core,
            "covered_credits": sum(course["credits"] for course in covered),
            "professional_covered": sum(
                course["credits"]
                for course in covered
                if course["category"] == "professional_elective"
            ),
            "general_core_covered": {
                area: sum(
                    course["credits"]
                    for course in covered
                    if course["category"] == "general_core" and course["general_area"] == area
                )
                for area in ("civic", "sustainability", "aesthetics")
            },
        },
        "warnings": warnings,
    }


@endpoint("GET")
def plan(request, data):
    return plan_data(request.user)


def claim_plan(student, expected):
    if type(expected) is not int or expected < 0:
        raise ValidationError("請提供目前的 version 整數。")
    existing = StudyPlan.objects.filter(student=student).first()
    if (existing.version if existing else 0) != expected:
        raise VersionConflict("四年規劃已更新，請重新取得版本。")
    if existing:
        if not StudyPlan.objects.filter(pk=existing.pk, version=expected).update(
            version=F("version") + 1
        ):
            raise VersionConflict("四年規劃已更新，請重新取得版本。")
        return existing
    return StudyPlan.objects.create(student=student, version=1)


def validate_term(data):
    term = data.get("term")
    position = data.get("position", 0)
    if type(term) is not int or not 1 <= term <= 8 or type(position) is not int or position < 0:
        raise ValidationError("學期須為 1～8，排序位置須為非負整數。")
    return term, position


def validate_retake_term(student, course_id, term):
    latest = (
        FailedCourseAttempt.objects.filter(student=student, course_id=course_id)
        .order_by("-term")
        .first()
    )
    if latest and term <= latest.term:
        raise ValidationError("重修須排在最後一次未通過之後；若為誤觸，請使用取消未通過。")


def alter_plan(student, data, operation, entry_id=None):
    with transaction.atomic():
        plan = claim_plan(student, data.get("version"))
        if operation == "add":
            course = get_object_or_404(Course, pk=int(data["course_id"]))
            info = student_info(student)
            if course.program_type != info["program_type"]:
                raise ValidationError("此課程學制與目前學生不符。")
            if CompletedCourse.objects.filter(student=student, course=course).exists():
                raise ValidationError("這門課已修習通過或抵免。")
            if (
                course.category in ("required", "general_base", "pe")
                and not curriculum_courses(info).filter(pk=course.pk).exists()
            ):
                raise ValidationError("此必修課不在目前學制與入學年度的規劃中。")
            term, position = validate_term(data)
            validate_retake_term(student, course.pk, term)
            if PlannedCourse.objects.filter(plan=plan, course=course).exists():
                raise ValidationError("課程已排入規劃，請直接拖曳原卡片。")
            PlannedCourse.objects.create(plan=plan, course=course, term=term, position=position)
        else:
            entry = get_object_or_404(PlannedCourse, plan=plan, pk=entry_id)
            if entry.course_id in CompletedCourse.objects.filter(student=student).values_list(
                "course_id", flat=True
            ):
                raise ValidationError("已完成課程不提供移動。")
            if operation == "move":
                term, position = validate_term(
                    {**data, "position": data.get("position", entry.position)}
                )
                validate_retake_term(student, entry.course_id, term)
                entry.term, entry.position = term, position
                entry.full_clean()
                entry.save(update_fields=["term", "position"])
            else:
                if FailedCourseAttempt.objects.filter(
                    student=student, course_id=entry.course_id
                ).exists():
                    raise ValidationError(
                        "此課程有未通過紀錄，請先在未通過卡片取消未通過，再還原或移除規劃。"
                    )
                entry.delete()
    return plan_data(student)


@endpoint("POST")
def add_plan_course(request, data):
    return alter_plan(request.user, data, "add")


@endpoint("PATCH", "DELETE")
def change_plan_course(request, data, entry_id):
    return alter_plan(
        request.user, data, "move" if request.method == "PATCH" else "delete", entry_id
    )


@endpoint("POST")
def mark_failed(request, data):
    course = get_object_or_404(Course, pk=int(data["course_id"]))
    term = data.get("term")
    retake_term = data.get("retake_term", term + 1 if type(term) is int else None)
    if type(term) is not int or type(retake_term) is not int or not 1 <= term < retake_term <= 8:
        raise ValidationError("重修學期須在未通過學期之後，且介於八個學期內。")
    if CompletedCourse.objects.filter(student=request.user, course=course).exists():
        raise ValidationError("已完成的課程無法標記為未通過。")
    current = plan_data(request.user)
    if not any(
        item["course"]["id"] == course.pk and item["source"] != "failed"
        for item in current["terms"][term - 1]["courses"]
    ):
        raise ValidationError("這門課目前不在指定學期。")
    with transaction.atomic():
        plan = claim_plan(request.user, data.get("version"))
        if FailedCourseAttempt.objects.filter(
            student=request.user, course=course, term=term
        ).exists():
            raise ValidationError("這個學期已記錄未通過。")
        FailedCourseAttempt.objects.create(student=request.user, course=course, term=term)
        PlannedCourse.objects.update_or_create(
            plan=plan,
            course=course,
            defaults={"term": retake_term, "position": 0},
        )
    return plan_data(request.user)


@endpoint("DELETE")
def restore_failed(request, data):
    term, _ = validate_term(data)
    with transaction.atomic():
        plan = claim_plan(request.user, data.get("version"))
        attempt = get_object_or_404(
            FailedCourseAttempt,
            student=request.user,
            course_id=int(data["course_id"]),
            term=term,
        )
        if CompletedCourse.objects.filter(student=request.user, course=attempt.course).exists():
            raise ValidationError("已完成課程無法更改未通過紀錄。")
        if FailedCourseAttempt.objects.filter(
            student=request.user, course=attempt.course, term__gt=term
        ).exists():
            raise ValidationError("請先復原這門課較晚學期的未通過紀錄。")
        PlannedCourse.objects.update_or_create(
            plan=plan,
            course=attempt.course,
            defaults={"term": term, "position": 0},
        )
        attempt.delete()
    return plan_data(request.user)
