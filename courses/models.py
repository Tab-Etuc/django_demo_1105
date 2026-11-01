from itertools import pairwise
from typing import TYPE_CHECKING

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Count, F, Q

if TYPE_CHECKING:
    from .academic import CoursePrerequisite


def has_time_conflict(slots):
    ordered = sorted(slots, key=lambda slot: (slot[0], slot[1]))
    return any(a[0] == b[0] and a[2] > b[1] for a, b in pairwise(ordered))


def overlapping_slots(slots, *, prefix="", same_room=False):
    """Build one SQL condition for any overlapping main or extra meeting."""
    match = Q(pk__in=[])
    for day, start, end, room, _ in slots:
        if same_room and not room:
            continue
        main = Q(
            **{
                f"{prefix}day_of_week": day,
                f"{prefix}start_time__lt": end,
                f"{prefix}end_time__gt": start,
            }
        )
        extra = Q(
            **{
                f"{prefix}meetings__day_of_week": day,
                f"{prefix}meetings__start_time__lt": end,
                f"{prefix}meetings__end_time__gt": start,
            }
        )
        if same_room:
            main &= Q(**{f"{prefix}room": room})
            extra &= Q(**{f"{prefix}meetings__room": room}) | Q(
                **{f"{prefix}meetings__room": "", f"{prefix}room": room}
            )
        match |= main | extra
    return match


def validate_schedule(offering, slots):
    if has_time_conflict(slots):
        raise ValidationError("同一班別的上課時段彼此重疊。")
    if not offering.semester:
        return

    others = CourseOffering.objects.filter(semester=offering.semester).exclude(pk=offering.pk)
    if others.filter(overlapping_slots(slots, same_room=True)).exists():
        raise ValidationError("同學期、同時段的教室已被使用。")

    teacher_id = offering.teacher_id or offering.course.teacher_id
    if (
        teacher_id
        and others.filter(overlapping_slots(slots))
        .filter(Q(teacher_id=teacher_id) | Q(teacher__isnull=True, course__teacher_id=teacher_id))
        .exists()
    ):
        raise ValidationError("授課教師在同一時段已有其他課程。")


def validate_enrolled_slots(offering, slots):
    if not offering.pk:
        return
    from enrollments.models import Enrollment

    students = Enrollment.objects.filter(offering=offering, status="enrolled").values("student_id")
    others = Enrollment.objects.filter(
        student_id__in=students,
        status="enrolled",
        offering__semester=offering.semester,
    ).exclude(offering=offering)
    if others.filter(
        Q(offering__course_id=offering.course_id) | overlapping_slots(slots, prefix="offering__")
    ).exists():
        raise ValidationError("修改課程時段會造成已選學生的課表衝突。")


class Course(models.Model):
    if TYPE_CHECKING:
        teacher_id: int | None

        @property
        def offerings(self) -> models.Manager["CourseOffering"]: ...

        @property
        def prerequisite_links(self) -> models.Manager["CoursePrerequisite"]: ...

    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={"role": "teacher"},
        related_name="courses_teaching",
    )
    credits = models.PositiveIntegerField(default=0)
    capacity = models.PositiveIntegerField(default=30)
    description = models.TextField(blank=True)
    CATEGORY_CHOICES = [
        ("required", "系專業必修"),
        ("general_base", "通識基礎"),
        ("professional_elective", "專業選修"),
        ("general_core", "通識核心"),
        ("general_interest", "通識興趣"),
        ("pe", "體育"),
        ("other", "其他"),
    ]
    category = models.CharField(max_length=24, choices=CATEGORY_CHOICES, default="other")
    PROGRAM_CHOICES = [("four_year", "四技"), ("two_year", "二技")]
    program_type = models.CharField(max_length=12, choices=PROGRAM_CHOICES, default="four_year")
    department = models.CharField(max_length=60, default="資訊管理系")
    general_area = models.CharField(max_length=24, blank=True)
    english_interest = models.BooleanField(default=False)
    recommended_term = models.PositiveSmallIntegerField(null=True, blank=True)
    curriculum_year = models.PositiveSmallIntegerField(null=True, blank=True)
    is_demo = models.BooleanField(default=False)

    class Meta:
        ordering = ["code"]
        constraints = [
            models.CheckConstraint(condition=Q(capacity__gt=0), name="course_capacity_positive"),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def clean(self):
        super().clean()
        if self.teacher_id and self.teacher.role != "teacher":
            raise ValidationError({"teacher": "授課教師必須具有教師身分。"})
        if (
            self.pk
            and self.offerings.filter(capacity__isnull=True)
            .annotate(
                enrolled=Count("enrollments", filter=Q(enrollments__status="enrolled")),
            )
            .filter(enrolled__gt=self.capacity)
            .exists()
        ):
            raise ValidationError({"capacity": "課程容量不得低於既有選課人數。"})

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.pk:
                CourseOffering.objects.filter(course_id=self.pk, capacity__isnull=True).update(
                    capacity=F("capacity"),
                )
            self.full_clean()
            super().save(*args, **kwargs)


class CourseOffering(models.Model):
    if TYPE_CHECKING:
        course_id: int
        teacher_id: int | None

        @property
        def meetings(self) -> models.Manager["CourseMeeting"]: ...

        enrolled_count: int

        def get_day_of_week_display(self) -> str: ...

    DAYS_OF_WEEK = [
        (0, "Monday"),
        (1, "Tuesday"),
        (2, "Wednesday"),
        (3, "Thursday"),
        (4, "Friday"),
        (5, "Saturday"),
        (6, "Sunday"),
    ]

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="offerings")
    semester = models.CharField(max_length=20, db_index=True)
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={"role": "teacher"},
        related_name="offerings_teaching",
    )
    day_of_week = models.IntegerField(choices=DAYS_OF_WEEK)
    start_time = models.TimeField()
    end_time = models.TimeField()
    room = models.CharField(max_length=50, blank=True)
    capacity = models.PositiveIntegerField(
        null=True, blank=True, help_text="Override course capacity"
    )
    enroll_opens_at = models.DateTimeField(null=True, blank=True)
    enroll_closes_at = models.DateTimeField(null=True, blank=True)
    section = models.CharField(max_length=20, default="A")
    assigned_class = models.CharField(max_length=40, blank=True)
    class_label = models.CharField(max_length=60, blank=True)
    target_grade = models.PositiveSmallIntegerField(null=True, blank=True)
    min_grade = models.PositiveSmallIntegerField(default=1)
    max_grade = models.PositiveSmallIntegerField(default=4)
    syllabus = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["semester", "day_of_week", "start_time"]
        constraints = [
            models.UniqueConstraint(
                fields=["course", "semester", "section"], name="unique_course_semester_section"
            ),
            models.CheckConstraint(
                condition=Q(start_time__lt=F("end_time")), name="offering_valid_times"
            ),
            models.CheckConstraint(
                condition=Q(capacity__gt=0) | Q(capacity__isnull=True),
                name="offering_capacity_positive",
            ),
            models.CheckConstraint(
                condition=Q(enroll_opens_at__isnull=True)
                | Q(enroll_closes_at__isnull=True)
                | Q(enroll_opens_at__lt=F("enroll_closes_at")),
                name="offering_valid_enroll_window",
            ),
        ]

    def __str__(self):
        return (
            f"{self.course.code} {self.semester} {self.get_day_of_week_display()} {self.start_time}"
        )

    @property
    def effective_capacity(self):
        return self.capacity if self.capacity is not None else self.course.capacity

    def slots(self):
        return [(self.day_of_week, self.start_time, self.end_time, self.room, None)] + [
            (m.day_of_week, m.start_time, m.end_time, m.room or self.room, m.pk)
            for m in self.meetings.all()
        ]

    def clean(self):
        super().clean()
        if not 1 <= self.min_grade <= self.max_grade <= 4:
            raise ValidationError({"min_grade": "選課年級必須介於一至四年級。"})
        if self.target_grade is not None and not 1 <= self.target_grade <= 4:
            raise ValidationError({"target_grade": "開課年級必須介於一至四年級。"})
        if self.course_id and self.teacher_id is None and self._state.adding:
            self.teacher_id = self.course.teacher_id
        if self.teacher_id and self.teacher.role != "teacher":
            raise ValidationError({"teacher": "授課教師必須具有教師身分。"})
        if self.pk:
            from enrollments.models import Enrollment

            enrolled = Enrollment.objects.filter(offering=self, status="enrolled").count()
            if enrolled > self.effective_capacity:
                raise ValidationError({"capacity": "容量不得低於既有選課人數。"})
        if self.course_id and self.start_time and self.end_time and self.start_time < self.end_time:
            slots = (
                self.slots()
                if self.pk
                else [
                    (self.day_of_week, self.start_time, self.end_time, self.room, None),
                ]
            )
            if not getattr(self, "_editing_meetings", False):
                validate_schedule(self, slots)
                validate_enrolled_slots(self, slots)

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.pk:
                CourseOffering.objects.filter(pk=self.pk).update(capacity=F("capacity"))
            self.full_clean()
            super().save(*args, **kwargs)


class CourseMeeting(models.Model):
    if TYPE_CHECKING:
        offering_id: int

        def get_day_of_week_display(self) -> str: ...

    offering = models.ForeignKey(CourseOffering, on_delete=models.CASCADE, related_name="meetings")
    day_of_week = models.IntegerField(choices=CourseOffering.DAYS_OF_WEEK)
    start_time = models.TimeField()
    end_time = models.TimeField()
    room = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ["day_of_week", "start_time"]
        constraints = [
            models.CheckConstraint(
                condition=Q(start_time__lt=F("end_time")), name="meeting_valid_times"
            ),
        ]

    def __str__(self):
        return f"{self.offering} {self.get_day_of_week_display()} {self.start_time}-{self.end_time}"

    def clean(self):
        super().clean()
        if (
            self.offering_id
            and self.start_time
            and self.end_time
            and self.start_time < self.end_time
            and not getattr(self.offering, "_editing_meetings", False)
        ):
            slot = (
                self.day_of_week,
                self.start_time,
                self.end_time,
                self.room or self.offering.room,
                self.pk,
            )
            slots = [
                existing
                for existing in self.offering.slots()
                if existing[4] is None or existing[4] != self.pk
            ]
            slots.append(slot)
            validate_schedule(self.offering, slots)
            validate_enrolled_slots(self.offering, slots)

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.offering_id:
                CourseOffering.objects.filter(pk=self.offering_id).update(capacity=F("capacity"))
            self.full_clean()
            super().save(*args, **kwargs)


from .academic import (  # noqa: E402,F401
    CompletedCourse,
    CoursePrerequisite,
    FailedCourseAttempt,
    PlannedCourse,
    StudentProfile,
    StudyPlan,
)
