from typing import TYPE_CHECKING

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import F
from django.utils import timezone

from courses.academic import CompletedCourse
from courses.models import CourseOffering, overlapping_slots


class Enrollment(models.Model):
    if TYPE_CHECKING:
        student_id: int
        offering_id: int

    STATUS_CHOICES = [
        ("enrolled", "Enrolled"),
        ("dropped", "Dropped"),
    ]

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={"role": "student"},
        related_name="enrollments",
    )
    offering = models.ForeignKey(
        CourseOffering, on_delete=models.CASCADE, related_name="enrollments"
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="enrolled")
    enrolled_at = models.DateTimeField(auto_now_add=True)
    dropped_at = models.DateTimeField(null=True, blank=True)
    is_assigned = models.BooleanField(default=False)

    class Meta:
        ordering = ["-enrolled_at"]
        unique_together = [["student", "offering"]]

    def __str__(self):
        return f"{self.student.username} - {self.offering} [{self.status}]"

    def clean(self):
        super().clean()
        if self.student_id and self.student.role != "student":
            raise ValidationError({"student": "只有學生可以選課。"})
        if self.status == "dropped" and not self.dropped_at:
            self.dropped_at = timezone.now()
        if self.status == "enrolled":
            self.dropped_at = None
        if self.status != "enrolled" or not self.student_id or not self.offering_id:
            return
        offering = self.offering
        if CompletedCourse.objects.filter(
            student_id=self.student_id, course_id=offering.course_id
        ).exists():
            raise ValidationError("這門課已修習通過或抵免。")
        others = Enrollment.objects.filter(
            student_id=self.student_id,
            status="enrolled",
            offering__semester=offering.semester,
        ).exclude(pk=self.pk)
        if others.filter(offering__course_id=offering.course_id).exists():
            raise ValidationError("同一學期不可重複選擇相同課程。")
        if others.filter(overlapping_slots(offering.slots(), prefix="offering__")).exists():
            raise ValidationError("選課時間與既有課表衝突。")
        count = (
            Enrollment.objects.filter(offering=offering, status="enrolled")
            .exclude(pk=self.pk)
            .count()
        )
        if count >= offering.effective_capacity:
            raise ValidationError("課程已額滿。")
        enrolled_credits = sum(
            record.offering.course.credits
            for record in Enrollment.objects.filter(
                student_id=self.student_id,
                status="enrolled",
                offering__semester=offering.semester,
            )
            .exclude(pk=self.pk)
            .select_related("offering__course")
        )
        if enrolled_credits + offering.course.credits > 25:
            raise ValidationError("超過每學期 25 學分上限。")

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.offering_id:
                CourseOffering.objects.filter(pk=self.offering_id).update(capacity=F("capacity"))
            self.full_clean()
            if kwargs.get("update_fields"):
                kwargs["update_fields"] = set(kwargs["update_fields"]) | {"dropped_at"}
            super().save(*args, **kwargs)
