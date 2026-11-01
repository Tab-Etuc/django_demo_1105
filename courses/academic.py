from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q


class StudentProfile(models.Model):
    student = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    admission_year = models.PositiveSmallIntegerField(default=115)
    grade = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(4)]
    )
    class_name = models.CharField(max_length=40, blank=True)
    department = models.CharField(max_length=60, default="資訊管理系")
    program_type = models.CharField(
        max_length=12, choices=[("four_year", "四技"), ("two_year", "二技")], default="four_year"
    )
    semester = models.CharField(max_length=20, default="115-1")

    @property
    def min_credits(self):
        return 9 if (self.program_type == "two_year" and self.grade == 2) or self.grade == 4 else 16

    def __str__(self):
        return f"{self.student.username} {self.class_name}"


class CoursePrerequisite(models.Model):
    course = models.ForeignKey(
        "courses.Course", on_delete=models.CASCADE, related_name="prerequisite_links"
    )
    required_course = models.ForeignKey(
        "courses.Course", on_delete=models.CASCADE, related_name="unlocks"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["course", "required_course"], name="unique_course_prerequisite"
            ),
            models.CheckConstraint(
                condition=~Q(course_id=models.F("required_course_id")), name="prerequisite_not_self"
            ),
        ]


class CompletedCourse(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="completed_courses"
    )
    course = models.ForeignKey("courses.Course", on_delete=models.CASCADE)
    status = models.CharField(
        max_length=12, choices=[("passed", "Passed"), ("credited", "Credited")]
    )
    completed_semester = models.CharField(max_length=20, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "course"], name="one_completed_course_per_student"
            ),
        ]


class FailedCourseAttempt(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="failed_attempts"
    )
    course = models.ForeignKey("courses.Course", on_delete=models.CASCADE)
    term = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(8)])

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "course", "term"], name="unique_failed_plan_attempt"
            ),
            models.CheckConstraint(
                condition=Q(term__gte=1, term__lte=8), name="failed_plan_term_range"
            ),
        ]


class StudyPlan(models.Model):
    student = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="study_plan"
    )
    version = models.PositiveIntegerField(default=1)


class PlannedCourse(models.Model):
    plan = models.ForeignKey(StudyPlan, on_delete=models.CASCADE, related_name="entries")
    course = models.ForeignKey("courses.Course", on_delete=models.CASCADE)
    term = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(8)])
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["term", "position", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["plan", "course"], name="one_course_per_study_plan"),
            models.CheckConstraint(
                condition=Q(term__gte=1, term__lte=8), name="plan_term_between_1_and_8"
            ),
        ]
