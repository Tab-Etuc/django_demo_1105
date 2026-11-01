from concurrent.futures import ThreadPoolExecutor
from datetime import time
from threading import Barrier

from django.core.exceptions import ValidationError
from django.db import OperationalError, close_old_connections, connections
from django.test import TransactionTestCase

from accounts.models import User
from enrollments.models import Enrollment

from .models import Course, CourseOffering
from .selection import select


class ConcurrentEnrollmentTests(TransactionTestCase):
    def test_last_seat_cannot_be_overbooked(self):
        first = User.objects.create_user("race_first", role="student")
        second = User.objects.create_user("race_second", role="student")
        course = Course.objects.create(code="RACE-ONE", name="限額選修", credits=1, capacity=1)
        offering = CourseOffering.objects.create(
            course=course,
            semester="115-1",
            day_of_week=0,
            start_time=time(7),
            end_time=time(8),
            room="測試教室",
        )
        barrier = Barrier(2)

        def enroll(student):
            close_old_connections()
            try:
                barrier.wait()
                select(student, "115-1", [offering.pk])
                return "enrolled"
            except ValidationError, OperationalError:
                return "rejected"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            one = executor.submit(enroll, first)
            two = executor.submit(enroll, second)
            results = [one.result(), two.result()]

        self.assertCountEqual(results, ["enrolled", "rejected"])
        self.assertEqual(Enrollment.objects.filter(offering=offering, status="enrolled").count(), 1)
