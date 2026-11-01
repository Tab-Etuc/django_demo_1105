from datetime import time, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from enrollments.models import Enrollment

from .models import Course, CourseMeeting, CourseOffering, has_time_conflict, overlapping_slots


class StudentPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.student = User.objects.create_user("student", role="student")
        cls.teacher = User.objects.create_user("teacher", role="teacher")
        cls.admin = User.objects.create_superuser("admin")

    def test_login_required_and_react_pages(self):
        for path in ("/", "/plans/"):
            self.assertEqual(self.client.get(path).status_code, 302)
        self.client.force_login(self.student)
        for path in ("/", "/plans/"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed(response, "courses/react_app.html")
            self.assertNotContains(response, "bootstrap")

    def test_non_student_cannot_access_student_pages(self):
        for user in (self.teacher, self.admin):
            self.client.force_login(user)
            for path in ("/", "/plans/"):
                self.assertEqual(self.client.get(path).status_code, 403)

    def test_removed_legacy_routes_are_unavailable(self):
        self.client.force_login(self.student)
        for path in (
            "/admin/",
            "/teacher/",
            "/timetable/",
            "/enroll/1/",
            "/drop/1/",
            "/api/admin/assign-required/",
            "/api/teacher/offerings/",
        ):
            self.assertEqual(self.client.get(path).status_code, 404, path)


class EnrollmentScheduleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.student = User.objects.create_user("student", role="student")
        cls.teacher = User.objects.create_user("teacher", role="teacher")
        cls.course = Course.objects.create(code="FIRST", name="First", teacher=cls.teacher)
        cls.course2 = Course.objects.create(code="SECOND", name="Second", teacher=cls.teacher)
        cls.first = CourseOffering.objects.create(
            course=cls.course,
            semester="115-1",
            day_of_week=0,
            start_time=time(9),
            end_time=time(10),
            room="A",
        )

    def test_changing_time_cannot_conflict_with_enrolled_courses(self):
        second = CourseOffering.objects.create(
            course=self.course2,
            semester="115-1",
            day_of_week=1,
            start_time=time(9),
            end_time=time(10),
            room="B",
        )
        Enrollment.objects.create(student=self.student, offering=self.first)
        Enrollment.objects.create(student=self.student, offering=second)
        second.day_of_week = 0
        second.start_time = time(9, 30)
        second.end_time = time(10, 30)
        with self.assertRaises(ValidationError):
            second.save()

    def test_new_meeting_cannot_conflict_with_enrolled_courses(self):
        second = CourseOffering.objects.create(
            course=self.course2,
            semester="115-1",
            day_of_week=2,
            start_time=time(9),
            end_time=time(10),
            room="B",
        )
        Enrollment.objects.create(student=self.student, offering=self.first)
        Enrollment.objects.create(student=self.student, offering=second)
        with self.assertRaises(ValidationError):
            CourseMeeting.objects.create(
                offering=self.first,
                day_of_week=2,
                start_time=time(9, 30),
                end_time=time(10, 30),
                room="C",
            )


class ScheduleValidationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.teacher = User.objects.create_user("teacher", role="teacher")
        cls.teacher2 = User.objects.create_user("teacher2", role="teacher")
        cls.course = Course.objects.create(code="D", name="Databases", teacher=cls.teacher)
        cls.course2 = Course.objects.create(code="N", name="Networks", teacher=cls.teacher2)
        cls.offering = CourseOffering.objects.create(
            course=cls.course,
            semester="115-1",
            day_of_week=0,
            start_time=time(10),
            end_time=time(11),
            room="R101",
        )

    def test_sorted_overlap_handles_nested_and_touching_intervals(self):
        from datetime import time

        self.assertTrue(
            has_time_conflict(
                [
                    (0, time(9), time(12)),
                    (0, time(10), time(11)),
                    (0, time(13), time(14)),
                ]
            )
        )
        self.assertFalse(
            has_time_conflict(
                [
                    (0, time(9), time(10)),
                    (0, time(10), time(11)),
                    (1, time(9, 30), time(10, 30)),
                ]
            )
        )

    def test_room_conflict_with_inherited_extra_meeting_room(self):
        CourseMeeting.objects.create(
            offering=self.offering,
            day_of_week=2,
            start_time=time(13),
            end_time=time(15),
            room="",
        )
        with self.assertRaises(ValidationError):
            CourseOffering.objects.create(
                course=self.course2,
                semester="115-1",
                day_of_week=2,
                start_time=time(14),
                end_time=time(16),
                room="R101",
            )

    def test_room_and_teacher_conflicts_match_the_same_meeting(self):
        other = CourseOffering.objects.create(
            course=self.course2,
            semester="115-1",
            day_of_week=4,
            start_time=time(9),
            end_time=time(10),
            room="R201",
        )
        CourseMeeting.objects.create(
            offering=other,
            day_of_week=2,
            start_time=time(13),
            end_time=time(14),
            room="R202",
        )
        # An unrelated room and time cannot be combined into a false conflict.
        offering = CourseOffering.objects.create(
            course=self.course,
            semester="115-1",
            section="B",
            day_of_week=2,
            start_time=time(9),
            end_time=time(10),
            room="R202",
        )
        self.assertIsNotNone(offering.pk)

    def test_orm_overlap_filters_only_matching_offerings(self):
        exact = CourseOffering.objects.create(
            course=self.course2,
            semester="115-1",
            day_of_week=0,
            start_time=time(11),
            end_time=time(12),
            room="R201",
        )
        matches = CourseOffering.objects.filter(
            overlapping_slots([(0, time(10, 30), time(11, 30), "", None)])
        )
        self.assertEqual(set(matches.values_list("pk", flat=True)), {exact.pk, self.offering.pk})

    def test_invalid_time_and_zero_capacity(self):
        with self.assertRaises(ValidationError):
            CourseOffering.objects.create(
                course=self.course2,
                semester="115-1",
                day_of_week=3,
                start_time=time(15),
                end_time=time(14),
                room="R102",
            )
        with self.assertRaises(ValidationError):
            Course.objects.create(code="ZERO", name="Invalid", capacity=0)
        with self.assertRaises(ValidationError):
            CourseOffering.objects.create(
                course=self.course2,
                semester="115-1",
                day_of_week=3,
                start_time=time(9),
                end_time=time(10),
                capacity=0,
            )

    def test_duplicate_section_for_same_course_and_semester_is_rejected(self):
        with self.assertRaises(ValidationError):
            CourseOffering.objects.create(
                course=self.course,
                semester="115-1",
                section="A",
                day_of_week=2,
                start_time=time(13),
                end_time=time(14),
                room="R303",
            )

    def test_parallel_sections_with_distinct_teacher_and_room(self):
        CourseOffering.objects.create(
            course=self.course,
            teacher=self.teacher2,
            semester="115-1",
            section="B",
            day_of_week=0,
            start_time=time(10),
            end_time=time(11),
            room="R102",
        )
        self.assertEqual(CourseOffering.objects.filter(course=self.course).count(), 2)

    def test_teacher_and_room_conflict(self):
        with self.assertRaises(ValidationError):
            CourseOffering.objects.create(
                course=self.course,
                semester="115-1",
                day_of_week=0,
                start_time=time(10, 30),
                end_time=time(11, 30),
                room="R102",
            )
        with self.assertRaises(ValidationError):
            CourseOffering.objects.create(
                course=self.course2,
                semester="115-1",
                day_of_week=0,
                start_time=time(10, 30),
                end_time=time(11, 30),
                room="R101",
            )

    def test_extra_meeting_checks_primary_and_others(self):
        with self.assertRaises(ValidationError):
            CourseMeeting.objects.create(
                offering=self.offering,
                day_of_week=0,
                start_time=time(10, 30),
                end_time=time(11, 30),
            )
        meeting = CourseMeeting.objects.create(
            offering=self.offering,
            day_of_week=2,
            start_time=time(9),
            end_time=time(10),
        )
        with self.assertRaises(ValidationError):
            CourseMeeting.objects.create(
                offering=self.offering,
                day_of_week=2,
                start_time=time(9, 30),
                end_time=time(10, 30),
            )
        self.assertIsNotNone(meeting.pk)

    def test_edit_existing_meeting_replaces_its_old_slot(self):
        meeting = CourseMeeting.objects.create(
            offering=self.offering,
            day_of_week=2,
            start_time=time(9),
            end_time=time(10),
            room="R102",
        )
        meeting.start_time, meeting.end_time = time(10), time(11)
        meeting.save()
        self.assertEqual(meeting.start_time, time(10))
        meeting.day_of_week = 0
        meeting.start_time, meeting.end_time = time(10, 30), time(11, 30)
        with self.assertRaises(ValidationError):
            meeting.save()

    def test_cannot_reduce_capacity_below_enrollments(self):
        student = User.objects.create_user("student", role="student")
        Enrollment.objects.create(student=student, offering=self.offering)
        self.course.capacity = 0
        with self.assertRaises(ValidationError):
            self.course.save()
        self.offering.capacity = 0
        with self.assertRaises(ValidationError):
            self.offering.save()

    def test_reducing_positive_capacity_below_enrollments(self):
        self.course.capacity = 3
        self.course.save()
        for name in ("student1", "student2"):
            Enrollment.objects.create(
                student=User.objects.create_user(name, role="student"),
                offering=self.offering,
            )
        self.course.capacity = 1
        with self.assertRaises(ValidationError):
            self.course.save()
        self.offering.capacity = 1
        with self.assertRaises(ValidationError):
            self.offering.save()

    def test_invalid_enrollment_window(self):
        self.offering.enroll_opens_at = timezone.now() + timedelta(days=1)
        self.offering.enroll_closes_at = timezone.now() - timedelta(days=1)
        with self.assertRaises(ValidationError):
            self.offering.save()
