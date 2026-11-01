import json
from functools import wraps

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.db.models import Count, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import ensure_csrf_cookie

from enrollments.models import Enrollment

from .academic import CompletedCourse
from .models import Course, CourseOffering
from .selection import (
    PERIODS,
    credit_summary,
    drop,
    enrolled,
    graduation_requirements,
    offering_slots,
    reasons,
    review,
    select,
    student_info,
    switch,
    with_enrolled_counts,
)


class VersionConflict(Exception):
    pass


def endpoint(*methods, roles=("student",)):
    def decorate(view):
        @wraps(view)
        def invoke(request, *args, **kwargs):
            if request.method not in methods:
                response = JsonResponse({"error": "不支援此請求方法。"}, status=405)
                response["Allow"] = ", ".join(methods)
                return response
            if not request.user.is_authenticated:
                return JsonResponse({"error": "請先登入。"}, status=401)
            if request.user.role not in roles:
                return JsonResponse({"error": "沒有操作權限。"}, status=403)
            try:
                data = (
                    json.loads(request.body or b"{}")
                    if request.method in ("POST", "PATCH", "PUT", "DELETE")
                    else {}
                )
                if not isinstance(data, dict):
                    raise ValidationError("請傳入 JSON 物件。")
                result = view(request, data, *args, **kwargs)
                return JsonResponse(result)
            except json.JSONDecodeError:
                return JsonResponse({"error": "JSON 格式錯誤。"}, status=400)
            except (ValidationError, ValueError, KeyError, TypeError) as exc:
                message = "；".join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
                return JsonResponse({"error": message}, status=400)
            except VersionConflict as exc:
                return JsonResponse({"error": str(exc)}, status=409)
            except PermissionDenied:
                return JsonResponse({"error": "沒有操作權限。"}, status=403)
            except Http404:
                return JsonResponse({"error": "找不到指定資料。"}, status=404)
            except IntegrityError:
                return JsonResponse({"error": "資料已變更，請重新整理後再試。"}, status=409)

        return invoke

    return decorate


def active_semester(request, value=None):
    return value or request.GET.get("semester") or student_info(request.user)["semester"]


def serialize_course(course):
    return {
        "id": course.pk,
        "code": course.code,
        "name": course.name,
        "category": course.category,
        "category_label": course.get_category_display(),
        "credits": course.credits,
        "description": course.description,
        "department": course.department,
        "program_type": course.program_type,
        "program_label": course.get_program_type_display(),
        "general_area": course.general_area,
        "english_interest": course.english_interest,
        "recommended_term": course.recommended_term,
        "curriculum_year": course.curriculum_year,
        "is_demo": course.is_demo,
        "credit_group": course.category,
        "contribution": (
            "專業選修"
            if course.category == "professional_elective"
            else "通識核心：" + course.general_area
            if course.category == "general_core"
            else "通識興趣英語"
            if course.english_interest
            else course.get_category_display()
        ),
    }


def serialize_offering(offering, records=None, *, student=None, detailed=False, completed_ids=None):
    records = records or []
    assigned = next((r for r in records if r.offering_id == offering.pk), None)
    count = getattr(offering, "enrolled_count", None)
    if count is None:
        count = offering.enrollments.filter(status="enrolled").count()
    if assigned:
        errors, conflicts = (["已選上此班別。"], [])
    else:
        errors, conflicts = (
            reasons(offering, student, records, enrolled_count=count, completed_ids=completed_ids)
            if student
            else ([], [])
        )
    teacher = offering.teacher or offering.course.teacher
    return {
        "id": offering.pk,
        "course_id": offering.course_id,
        "semester": offering.semester,
        "section": offering.section,
        "teacher": (
            {"id": teacher.pk, "name": teacher.get_full_name() or teacher.username}
            if teacher
            else None
        ),
        "slots": offering_slots(offering),
        "capacity": offering.effective_capacity,
        "enrolled": count,
        "remaining": max(0, offering.effective_capacity - count),
        "assigned_class": offering.assigned_class,
        "class_label": offering.class_label,
        "target_grade": offering.target_grade,
        "grade_label": f"{'一二三四'[offering.target_grade - 1]}年級"
        if offering.target_grade and 1 <= offering.target_grade <= 4
        else "不限年級",
        "min_grade": offering.min_grade,
        "max_grade": offering.max_grade,
        "is_selected": assigned is not None,
        "is_assigned": bool(assigned and assigned.is_assigned),
        "can_select": not errors,
        "unavailable_reasons": errors,
        "conflicts": conflicts,
        **({"syllabus": offering.syllabus} if detailed else {}),
    }


def serialize_record(record):
    return {
        "id": record.pk,
        "is_assigned": record.is_assigned,
        "enrolled_at": record.enrolled_at.isoformat(),
        "course": serialize_course(record.offering.course),
        "offering": serialize_offering(record.offering),
    }


def curriculum(student, records):
    requirements = graduation_requirements(student_info(student))
    professional_target = requirements["professional"]
    complete = list(CompletedCourse.objects.filter(student=student).select_related("course"))

    def credits(items, category):
        return sum(item.course.credits for item in items if item.course.category == category)

    def selected(category):
        return sum(
            item.offering.course.credits
            for item in records
            if item.offering.course.category == category
        )

    completed_total = sum(item.course.credits for item in complete)
    return {
        "graduation_target": requirements["target"],
        "professional_elective_target": professional_target,
        "completed_credits": completed_total,
        "selected_credits": sum(item.offering.course.credits for item in records),
        "professional_elective": {
            "completed": credits(complete, "professional_elective"),
            "selected": selected("professional_elective"),
            "target": professional_target,
        },
        "general_core": {
            area: {
                "completed": sum(
                    item.course.credits
                    for item in complete
                    if item.course.category == "general_core" and item.course.general_area == area
                ),
                "selected": sum(
                    item.offering.course.credits
                    for item in records
                    if item.offering.course.category == "general_core"
                    and item.offering.course.general_area == area
                ),
                "target": 2,
            }
            for area in ("civic", "sustainability", "aesthetics")
        },
        "general_interest": {
            "completed": credits(complete, "general_interest"),
            "selected": selected("general_interest"),
            "target": 8,
            "english_required": 2,
            "english_completed": sum(
                item.course.credits
                for item in complete
                if item.course.category == "general_interest" and item.course.english_interest
            ),
            "english_selected": sum(
                item.offering.course.credits
                for item in records
                if item.offering.course.category == "general_interest"
                and item.offering.course.english_interest
            ),
        },
        "status": "completed、selected、planned 分別計算；selected 尚未取得畢業學分。",
    }


@endpoint("GET")
def index(request, data):
    return {
        "system": "大學選課 Demo API",
        "demo": True,
        "auth": "Django Session；POST、PATCH、DELETE 需 CSRF Token",
        "student": [
            "/api/me/",
            "/api/courses/",
            "/api/courses/{id}/",
            "/api/timetable/",
            "/api/preview/",
            "/api/recommendations/",
            "/api/enrollments/",
            "/api/enrollments/drop/",
            "/api/enrollments/switch/",
            "/api/plan/",
            "/api/plan/courses/",
        ],
    }


@ensure_csrf_cookie
@endpoint("GET")
def me(request, data):
    semester = active_semester(request)
    records = enrolled(request.user, semester)
    counts = dict(
        Enrollment.objects.filter(
            offering_id__in=[r.offering_id for r in records],
            status="enrolled",
        )
        .values("offering_id")
        .annotate(total=Count("id"))
        .values_list("offering_id", "total")
    )
    for record in records:
        record.offering.enrolled_count = counts.get(record.offering_id, 0)
    return {
        "student": student_info(request.user),
        "semester": semester,
        "credits": credit_summary(records, request.user),
        "curriculum": curriculum(request.user, records),
        "enrollments": [serialize_record(r) for r in records],
    }


@endpoint("GET")
def periods(request, data):
    return {"periods": [{"number": i, "start": a, "end": b} for i, (a, b) in enumerate(PERIODS, 1)]}


def catalog_data(request, params=None, *, rescue=True):
    params = request.GET if params is None else params
    semester = params.get("semester") or student_info(request.user)["semester"]
    offerings = (
        with_enrolled_counts(CourseOffering.objects.filter(semester=semester))
        .select_related(
            "course",
            "course__teacher",
            "teacher",
        )
        .prefetch_related("meetings", "course__prerequisite_links")
    )
    if q := params.get("q", "").strip():
        offerings = offerings.filter(
            Q(course__name__icontains=q)
            | Q(course__code__icontains=q)
            | Q(course__department__icontains=q)
            | Q(teacher__username__icontains=q)
            | Q(course__teacher__username__icontains=q)
            | Q(teacher__first_name__icontains=q)
            | Q(teacher__last_name__icontains=q)
            | Q(course__teacher__first_name__icontains=q)
            | Q(course__teacher__last_name__icontains=q)
        )
    if category := params.get("category"):
        offerings = offerings.filter(course__category=category)
    if program_type := params.get("program_type"):
        if program_type not in ("four_year", "two_year"):
            raise ValidationError("學制篩選格式錯誤。")
        offerings = offerings.filter(course__program_type=program_type)
    if department := params.get("department"):
        offerings = offerings.filter(course__department=department)
    if section := params.get("section"):
        offerings = offerings.filter(section=section)
    if class_group := params.get("class_group"):
        if class_group not in ("甲班", "乙班", "unassigned"):
            raise ValidationError("班級篩選格式錯誤。")
        offerings = offerings.filter(class_label="" if class_group == "unassigned" else class_group)
    if params.get("grade"):
        grade = int(params["grade"])
        if grade not in (1, 2, 3, 4):
            raise ValidationError("年級必須介於一至四年級。")
        offerings = offerings.filter(
            Q(target_grade=grade)
            | Q(target_grade__isnull=True, min_grade__lte=grade, max_grade__gte=grade)
        )
    if area := params.get("area"):
        offerings = offerings.filter(course__general_area=area)
    if params.get("max_credits"):
        credits = int(params["max_credits"])
        if not 0 <= credits <= 25:
            raise ValidationError("max_credits 必須介於 0 到 25。")
        offerings = offerings.filter(course__credits__lte=credits)
    records = enrolled(request.user, semester)
    completed_ids = set(
        CompletedCourse.objects.filter(student=request.user).values_list("course_id", flat=True)
    )
    grouped = {}
    for offering in offerings:
        details = serialize_offering(
            offering, records, student=request.user, completed_ids=completed_ids
        )
        if params.get("available") == "1" and not details["can_select"]:
            continue
        if params.get("no_conflict") == "1" and details["conflicts"]:
            continue
        if params.get("has_seats") == "1" and details["remaining"] == 0:
            continue
        if params.get("period") is not None and params.get("day") is None:
            raise ValidationError("篩選節次時請同時指定星期。")
        if params.get("day") is not None:
            day = int(params["day"])
            period = int(params["period"]) if params.get("period") is not None else None
            if day not in range(7) or (period is not None and period not in range(1, 10)):
                raise ValidationError("星期與節次超出範圍。")
            if not any(
                s["day"] == day and (period is None or period in s["periods"])
                for s in details["slots"]
            ):
                continue
        course = offering.course
        grouped.setdefault(course.pk, {"course": serialize_course(course), "offerings": []})
        grouped[course.pk]["offerings"].append(details)
    result = {"semester": semester, "count": len(grouped), "courses": list(grouped.values())}
    if not grouped and rescue:
        relaxations = []
        for key in (
            "available",
            "no_conflict",
            "has_seats",
            "max_credits",
            "category",
            "program_type",
            "department",
            "section",
            "grade",
            "area",
            "q",
            "day",
        ):
            if key not in params:
                continue
            relaxed = params.copy()
            relaxed.pop(key, None)
            if key == "day":
                relaxed.pop("period", None)
            alternative = catalog_data(request, relaxed, rescue=False)
            if alternative["count"]:
                relaxations.append({"remove": key, "courses_found": alternative["count"]})
        result["relaxations"] = relaxations[:3]
    return result


@endpoint("GET")
def courses(request, data):
    return catalog_data(request)


@endpoint("GET")
def course_detail(request, data, course_id):
    course = get_object_or_404(Course, pk=course_id)
    semester = active_semester(request)
    records = enrolled(request.user, semester)
    offerings = (
        with_enrolled_counts(
            CourseOffering.objects.filter(
                course=course,
                semester=semester,
            )
        )
        .select_related("teacher", "course__teacher")
        .prefetch_related("meetings", "course__prerequisite_links")
    )
    completed_ids = set(
        CompletedCourse.objects.filter(student=request.user).values_list("course_id", flat=True)
    )
    return {
        "course": serialize_course(course),
        "prerequisites": [
            serialize_course(link.required_course)
            for link in course.prerequisite_links.select_related("required_course")
        ],
        "offerings": [
            serialize_offering(
                offering, records, student=request.user, detailed=True, completed_ids=completed_ids
            )
            for offering in offerings
        ],
    }


@endpoint("GET")
def timetable(request, data):
    semester = active_semester(request)
    records = enrolled(request.user, semester)
    counts = dict(
        Enrollment.objects.filter(
            offering_id__in=[r.offering_id for r in records],
            status="enrolled",
        )
        .values("offering_id")
        .annotate(total=Count("id"))
        .values_list("offering_id", "total")
    )
    for record in records:
        record.offering.enrolled_count = counts.get(record.offering_id, 0)
    return {
        "semester": semester,
        "credits": credit_summary(records, request.user),
        "enrollments": [serialize_record(record) for record in records],
    }


@endpoint("POST")
def preview(request, data):
    return review(
        request.user, active_semester(request, data.get("semester")), data.get("offering_ids", [])
    )


@endpoint("POST")
def enroll_api(request, data):
    result = select(
        request.user, active_semester(request, data.get("semester")), data["offering_ids"]
    )
    return {
        "message": "加選成功。",
        "preview": result,
        "credits": credit_summary(enrolled(request.user, result["semester"]), request.user),
    }


@endpoint("POST")
def drop_api(request, data):
    semester = active_semester(request, data.get("semester"))
    credits = drop(request.user, semester, int(data["offering_id"]))
    return {"message": "退選成功。", "credits": credits}


@endpoint("POST")
def switch_api(request, data):
    semester = active_semester(request, data.get("semester"))
    result = switch(
        request.user, semester, int(data["from_offering_id"]), int(data["to_offering_id"])
    )
    return {
        "message": "換班成功。",
        "preview": result,
        "credits": credit_summary(enrolled(request.user, semester), request.user),
    }


@endpoint("GET")
def recommendations(request, data):
    params = request.GET.copy()
    if params.get("remaining") == "1":
        records = enrolled(request.user, active_semester(request))
        params["max_credits"] = str(max(0, 25 - sum(r.offering.course.credits for r in records)))
    result = catalog_data(request, params)
    suggestions = [
        {
            "course": item["course"],
            "offering": offering,
            "reason": ("符合" + item["course"]["category_label"] + "條件，且有剩餘名額與可用時段"),
        }
        for item in result["courses"]
        for offering in item["offerings"]
        if offering["can_select"]
    ]
    suggestions.sort(key=lambda x: (x["course"]["credits"], -x["offering"]["remaining"]))
    return {
        "semester": result["semester"],
        "count": len(suggestions),
        "suggestions": suggestions[:3],
    }
