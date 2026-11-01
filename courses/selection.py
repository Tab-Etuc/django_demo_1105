from collections import defaultdict
from datetime import time

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, F, Q
from django.utils import timezone

from enrollments.models import Enrollment

from .academic import CompletedCourse, StudentProfile
from .models import CourseOffering

# 大學日間部節次。課程資料本身仍存實際起迄時間。
PERIODS = [
    ("08:10", "09:00"),
    ("09:10", "10:00"),
    ("10:10", "11:00"),
    ("11:10", "12:00"),
    ("13:30", "14:20"),
    ("14:25", "15:15"),
    ("15:25", "16:15"),
    ("16:20", "17:10"),
    ("17:15", "18:05"),
]


def graduation_requirements(info):
    return {
        "target": 72 if info["program_type"] == "two_year" else 128,
        "professional": 33 if info["admission_year"] == 114 else 31,
    }


def student_info(student):
    cached = getattr(student, "_selection_student_info", None)
    if cached is not None:
        return cached
    profile = StudentProfile.objects.filter(student=student).first()
    info = {
        "student_id": student.pk,
        "username": student.username,
        "grade": profile.grade if profile else 1,
        "class_name": profile.class_name if profile else "",
        "department": profile.department if profile else "資訊管理系",
        "program_type": profile.program_type if profile else "four_year",
        "admission_year": profile.admission_year if profile else 115,
        "semester": profile.semester if profile else "115-1",
        "min_credits": profile.min_credits if profile else 16,
        "max_credits": 25,
        "profile_configured": profile is not None,
        "demo": True,
    }
    student._selection_student_info = info
    return info


def period_numbers(start, end):
    return [
        number
        for number, (begin, finish) in enumerate(PERIODS, 1)
        if start < time.fromisoformat(finish) and end > time.fromisoformat(begin)
    ]


def display_period_numbers(start, end):
    numbers = period_numbers(start, end)
    if not numbers:
        return []
    first, last = PERIODS[numbers[0] - 1][0], PERIODS[numbers[-1] - 1][1]
    return numbers if (start, end) == (time.fromisoformat(first), time.fromisoformat(last)) else []


def offering_slots(offering):
    return [
        {
            "day": day,
            "start": start.strftime("%H:%M"),
            "end": end.strftime("%H:%M"),
            "room": room,
            "periods": display_period_numbers(start, end),
        }
        for day, start, end, room, _ in offering.slots()
    ]


def with_enrolled_counts(offerings):
    return offerings.annotate(
        enrolled_count=Count("enrollments", filter=Q(enrollments__status="enrolled")),
    )


def enrolled(student, semester):
    return list(
        Enrollment.objects.filter(student=student, status="enrolled", offering__semester=semester)
        .select_related(
            "offering", "offering__course", "offering__teacher", "offering__course__teacher"
        )
        .prefetch_related("offering__meetings")
    )


def credit_summary(records, student):
    info = student_info(student)
    credits = sum(item.offering.course.credits for item in records)
    return {
        "confirmed": credits,
        "minimum": info["min_credits"],
        "maximum": info["max_credits"],
        "remaining": max(0, info["max_credits"] - credits),
        "missing": max(0, info["min_credits"] - credits),
        "over_limit": credits > info["max_credits"],
    }


def overlap(a, b):
    return a[0] == b[0] and a[1] < b[2] and b[1] < a[2]


def collisions(offering, records):
    result = []
    candidate_slots = offering.slots()
    for record in records:
        other = record.offering
        for first in candidate_slots:
            for second in other.slots():
                if overlap(first, second):
                    result.append(
                        {
                            "course": other.course.name,
                            "offering_id": other.pk,
                            "day": first[0],
                            "periods": sorted(
                                set(period_numbers(first[1], first[2]))
                                & set(period_numbers(second[1], second[2]))
                            ),
                        }
                    )
    return result


def reasons(
    offering, student, records, *, check_limit=True, enrolled_count=None, completed_ids=None
):
    course = offering.course
    info = student_info(student)
    errors = []
    if offering.course.program_type != info["program_type"]:
        errors.append("此課程學制與目前學生不符。")
    if offering.assigned_class and offering.assigned_class != info["class_name"]:
        errors.append("此班別限原班學生。")
    if not offering.min_grade <= info["grade"] <= offering.max_grade:
        errors.append("不符合開課年級限制。")
    now = timezone.now()
    if offering.enroll_opens_at and now < offering.enroll_opens_at:
        errors.append("選課尚未開放。")
    if offering.enroll_closes_at and now >= offering.enroll_closes_at:
        errors.append("選課時間已截止。")
    # Seat availability includes enrollments from every student.
    enrolled_count = (
        offering.enrollments.filter(status="enrolled").count()
        if enrolled_count is None
        else enrolled_count
    )
    if enrolled_count >= offering.effective_capacity:
        errors.append("課程已額滿。")
    if any(item.offering.course_id == course.pk for item in records):
        errors.append("本學期已選相同課程。")
    conflicts = collisions(offering, records)
    if conflicts:
        errors.append("與既有課表衝堂。")
    if completed_ids is None:
        completed_ids = set(
            CompletedCourse.objects.filter(student=student).values_list("course_id", flat=True)
        )
    if course.pk in completed_ids:
        errors.append("這門課已修習通過或抵免。")
    required = {link.required_course_id for link in course.prerequisite_links.all()}
    if required - completed_ids:
        errors.append("尚未完成先修課程。")
    if check_limit and sum(item.offering.course.credits for item in records) + course.credits > 25:
        errors.append("超過每學期 25 學分上限。")
    return errors, conflicts


def weekly_metrics(offerings):
    occupied = defaultdict(set)
    for offering in offerings:
        for slot in offering_slots(offering):
            occupied[slot["day"]].update(slot["periods"])
    return {
        "campus_days": len(occupied),
        "earliest_period": min((min(used) for used in occupied.values() if used), default=None),
        "gaps": sum(max(used) - min(used) + 1 - len(used) for used in occupied.values() if used),
    }


def review(student, semester, offering_ids, *, excluded_id=None):
    if not isinstance(offering_ids, list) or len(offering_ids) > 40:
        raise ValidationError("offering_ids 必須是最多 40 筆的陣列。")
    if any(type(pk) is not int or pk < 1 for pk in offering_ids):
        raise ValidationError("班別 ID 格式錯誤。")
    if len(set(offering_ids)) != len(offering_ids):
        raise ValidationError("試排包含重複班別。")
    current = [r for r in enrolled(student, semester) if r.offering_id != excluded_id]
    originals = [r.offering for r in current]
    choices = list(
        with_enrolled_counts(
            CourseOffering.objects.filter(
                pk__in=offering_ids,
                semester=semester,
            )
            .select_related("course", "teacher", "course__teacher")
            .prefetch_related(
                "meetings",
                "course__prerequisite_links",
            )
        )
    )
    if len(choices) != len(offering_ids):
        raise ValidationError("班別不存在或不屬於目前學期。")
    by_id = {offering.pk: offering for offering in choices}
    completed_ids = set(
        CompletedCourse.objects.filter(student=student).values_list("course_id", flat=True)
    )
    errors = []
    trial_records = current[:]
    for offering_id in offering_ids:
        offering = by_id[offering_id]
        issues, conflicts = reasons(
            offering,
            student,
            trial_records,
            enrolled_count=offering.enrolled_count,
            completed_ids=completed_ids,
        )
        if issues:
            errors.append({"offering_id": offering_id, "reasons": issues, "conflicts": conflicts})
        trial_records.append(Enrollment(student=student, offering=offering))
    confirmed = sum(offering.course.credits for offering in originals)
    proposed = sum(offering.course.credits for offering in choices)
    return {
        "semester": semester,
        "ok": not errors,
        "errors": errors,
        "confirmed_credits": confirmed,
        "trial_credits": proposed,
        "total_credits": confirmed + proposed,
        "minimum_credits": student_info(student)["min_credits"],
        "maximum_credits": 25,
        "missing_credits": max(0, student_info(student)["min_credits"] - confirmed - proposed),
        "remaining_credits": max(0, 25 - confirmed - proposed),
        "added_slots": [
            {"offering_id": item.pk, "course": item.course.name, "slots": offering_slots(item)}
            for item in choices
        ],
        "before": weekly_metrics(originals),
        "after": weekly_metrics(originals + choices),
    }


def select(student, semester, offering_ids):
    if not offering_ids:
        raise ValidationError("請至少選擇一個班別。")
    if (
        not isinstance(offering_ids, list)
        or len(offering_ids) > 40
        or any(type(pk) is not int or pk < 1 for pk in offering_ids)
    ):
        raise ValidationError("班別 ID 格式錯誤。")
    with transaction.atomic():
        # Obtain a write lock before reading capacities and timetable state.
        CourseOffering.objects.filter(pk__in=offering_ids).update(capacity=F("capacity"))
        result = review(student, semester, offering_ids)
        if not result["ok"]:
            raise ValidationError(
                "；".join(message for error in result["errors"] for message in error["reasons"])
            )
        for offering_id in offering_ids:
            entry = Enrollment.objects.filter(student=student, offering_id=offering_id).first()
            if entry:
                entry.status = "enrolled"
                entry.enrolled_at = timezone.now()
                entry.save()
            else:
                Enrollment.objects.create(student=student, offering_id=offering_id)
    return result


def drop(student, semester, offering_id):
    with transaction.atomic():
        CourseOffering.objects.filter(pk=offering_id, semester=semester).update(
            capacity=F("capacity")
        )
        record = Enrollment.objects.filter(
            student=student,
            offering_id=offering_id,
            offering__semester=semester,
            status="enrolled",
        ).first()
        if not record:
            raise ValidationError("尚未選擇這個班別。")
        if record.is_assigned:
            raise ValidationError("系統預排的必修課須由系辦辦理異動。")
        record.status = "dropped"
        record.save()
    return credit_summary(enrolled(student, semester), student)


def switch(student, semester, source_id, target_id):
    if source_id == target_id:
        raise ValidationError("請選擇不同班別。")
    with transaction.atomic():
        CourseOffering.objects.filter(pk__in=sorted([source_id, target_id])).update(
            capacity=F("capacity")
        )
        source = (
            Enrollment.objects.filter(
                student=student,
                offering_id=source_id,
                offering__semester=semester,
                status="enrolled",
            )
            .select_related("offering__course")
            .first()
        )
        target = (
            CourseOffering.objects.filter(
                pk=target_id,
                semester=semester,
            )
            .select_related("course")
            .first()
        )
        if not source or not target or source.offering.course_id != target.course_id:
            raise ValidationError("只能更換同學期、同一課程的已選班別。")
        if source.is_assigned:
            raise ValidationError("已配必修須由系辦辦理換班。")
        result = review(student, semester, [target_id], excluded_id=source_id)
        if not result["ok"]:
            raise ValidationError(
                "；".join(message for error in result["errors"] for message in error["reasons"])
            )
        source.status = "dropped"
        source.save()
        record = Enrollment.objects.filter(student=student, offering_id=target_id).first()
        if record is None:
            record = Enrollment(student=student, offering=target)
        record.status = "enrolled"
        record.enrolled_at = timezone.now()
        record.save()
    return result
