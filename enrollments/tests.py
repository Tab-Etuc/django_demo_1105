from datetime import time

from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.models import User
from courses.academic import CompletedCourse
from courses.models import Course, CourseOffering

from .models import Enrollment


class EnrollmentValidationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.student = User.objects.create_user("student", role="student")
        cls.teacher = User.objects.create_user("teacher", role="teacher")
        cls.teacher2 = User.objects.create_user("teacher2", role="teacher")
        cls.first = CourseOffering.objects.create(
            course=Course.objects.create(code="A", name="A", teacher=cls.teacher, capacity=1),
            semester="115-1",
            day_of_week=0,
            start_time=time(8),
            end_time=time(9),
            room="R1",
        )
        cls.second = CourseOffering.objects.create(
            course=Course.objects.create(code="B", name="B", teacher=cls.teacher2),
            semester="115-1",
            day_of_week=0,
            start_time=time(8, 30),
            end_time=time(10),
            room="R2",
        )

    def test_direct_enrollment_checks_role(self):
        with self.assertRaises(ValidationError):
            Enrollment.objects.create(student=self.teacher, offering=self.first)

    def test_direct_enrollment_rejects_completed_course(self):
        CompletedCourse.objects.create(
            student=self.student, course=self.first.course, status="credited"
        )
        with self.assertRaises(ValidationError):
            Enrollment.objects.create(student=self.student, offering=self.first)

    def test_direct_enrollment_checks_capacity(self):
        Enrollment.objects.create(student=self.student, offering=self.first)
        second_student = User.objects.create_user("second", role="student")
        with self.assertRaises(ValidationError):
            Enrollment.objects.create(student=second_student, offering=self.first)

    def test_direct_enrollment_checks_time_conflicts(self):
        Enrollment.objects.create(student=self.student, offering=self.first)
        with self.assertRaises(ValidationError):
            Enrollment.objects.create(student=self.student, offering=self.second)

    def test_direct_enrollment_checks_duplicate_course_section(self):
        later = CourseOffering.objects.create(
            course=self.first.course,
            semester="115-1",
            section="B",
            day_of_week=3,
            start_time=time(8),
            end_time=time(9),
            room="R3",
        )
        Enrollment.objects.create(student=self.student, offering=self.first)
        with self.assertRaises(ValidationError):
            Enrollment.objects.create(student=self.student, offering=later)
