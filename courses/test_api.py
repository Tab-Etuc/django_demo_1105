import json
from datetime import time
from io import StringIO
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import OperationalError, connection
from django.db.models import Count
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext

from accounts.models import User
from enrollments.models import Enrollment

from .academic import CompletedCourse, CoursePrerequisite, PlannedCourse, StudentProfile, StudyPlan
from .models import Course, CourseOffering


class DemoApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", stdout=StringIO())
        cls.student = User.objects.get(username="demo_student")
        cls.teacher = User.objects.get(username="demo_teacher_a")
        cls.other = User.objects.create_user("other_api_student", role="student")
        StudentProfile.objects.create(
            student=cls.other,
            grade=1,
            class_name="資管乙班",
            semester="115-1",
        )

    def setUp(self):
        self.client.force_login(self.student)

    def post(self, url, payload):
        return self.client.post(url, json.dumps(payload), content_type="application/json")

    def get_offering(self, code, section="A"):
        return CourseOffering.objects.get(course__code=f"NTUB115-{code}", section=section)

    def test_catalog_queries_do_not_grow_with_offerings(self):
        courses = Course.objects.bulk_create(
            [Course(code=f"PERF-{i:03d}", name=f"Perf {i}", category="other") for i in range(25)]
        )
        offerings = CourseOffering.objects.bulk_create(
            [
                CourseOffering(
                    course=course,
                    semester="115-1",
                    day_of_week=i % 5,
                    start_time=time(8),
                    end_time=time(9),
                    room=f"PERF-{i}",
                )
                for i, course in enumerate(courses)
            ]
        )

        def query_count(limit):
            CourseOffering.objects.filter(pk__in=[row.pk for row in offerings[limit:]]).delete()
            with CaptureQueriesContext(connection) as queries:
                response = self.client.get("/api/courses/?q=PERF")
            self.assertEqual(response.status_code, 200, response.content)
            self.assertEqual(response.json()["count"], limit)
            return len(queries)

        with CaptureQueriesContext(connection) as queries:
            response = self.client.get("/api/courses/?q=PERF")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 25)
        many = len(queries)
        few = query_count(3)
        self.assertEqual(many, few)

    def test_detail_queries_do_not_grow_with_sections(self):
        course = Course.objects.create(code="PERF-DETAIL", name="Perf Detail")
        offerings = CourseOffering.objects.bulk_create(
            [
                CourseOffering(
                    course=course,
                    semester="115-1",
                    section=str(i),
                    day_of_week=i % 5,
                    start_time=time(8),
                    end_time=time(9),
                    room=f"D-{i}",
                )
                for i in range(20)
            ]
        )
        url = f"/api/courses/{course.pk}/"

        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(url)
        self.assertEqual(len(response.json()["offerings"]), 20)
        many = len(queries)
        CourseOffering.objects.filter(pk__in=[row.pk for row in offerings[3:]]).delete()
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(url)
        self.assertEqual(len(response.json()["offerings"]), 3)
        self.assertEqual(many, len(queries))

    def test_student_dashboard_queries_do_not_grow_with_enrollments(self):
        new_courses = Course.objects.bulk_create(
            [Course(code=f"PERF-ME-{i}", name=f"Dashboard {i}", credits=0) for i in range(18)]
        )
        offerings = CourseOffering.objects.bulk_create(
            [
                CourseOffering(
                    course=course,
                    semester="115-1",
                    section="A",
                    day_of_week=i % 5,
                    start_time=time(8),
                    end_time=time(9),
                    room=f"ME-{i}",
                )
                for i, course in enumerate(new_courses)
            ]
        )
        Enrollment.objects.bulk_create(
            [Enrollment(student=self.student, offering=offering) for offering in offerings]
        )
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get("/api/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["enrollments"]), 26)
        many = len(queries)
        Enrollment.objects.filter(offering__in=offerings[3:], student=self.student).delete()
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get("/api/me/")
        self.assertEqual(len(response.json()["enrollments"]), 11)
        self.assertEqual(many, len(queries))

    def test_scheduled_timetable_queries_do_not_grow_with_enrollments(self):
        courses = Course.objects.bulk_create(
            [
                Course(code=f"PERF-TIMETABLE-{i}", name=f"Timetable {i}", credits=0)
                for i in range(12)
            ]
        )
        offerings = CourseOffering.objects.bulk_create(
            [
                CourseOffering(
                    course=course,
                    semester="115-1",
                    section="A",
                    day_of_week=i % 5,
                    start_time=time(8),
                    end_time=time(9),
                    room=f"T-{i}",
                )
                for i, course in enumerate(courses)
            ]
        )
        Enrollment.objects.bulk_create(
            [Enrollment(student=self.student, offering=offering) for offering in offerings]
        )
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get("/api/timetable/")
        self.assertEqual(len(response.json()["enrollments"]), 20)
        many = len(queries)
        Enrollment.objects.filter(offering__in=offerings[3:], student=self.student).delete()
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get("/api/timetable/")
        self.assertEqual(len(response.json()["enrollments"]), 11)
        self.assertEqual(many, len(queries))

    def test_demo_seed_is_repeatable_and_preserves_data(self):
        before = (
            Course.objects.count(),
            CourseOffering.objects.count(),
            Enrollment.objects.count(),
        )
        call_command("seed_demo", stdout=StringIO())
        self.assertEqual(
            (Course.objects.count(), CourseOffering.objects.count(), Enrollment.objects.count()),
            before,
        )

    def test_get_student_dashboard_and_required_assignments(self):
        response = self.client.get("/api/me/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["credits"]["confirmed"], 18)
        self.assertEqual(data["credits"]["minimum"], 16)
        self.assertEqual(len(data["enrollments"]), 8)
        self.assertTrue(all(row["is_assigned"] for row in data["enrollments"]))
        self.assertEqual(data["curriculum"]["professional_elective_target"], 31)

    def test_unauthenticated_and_role_restrictions(self):
        self.client.logout()
        self.assertEqual(self.client.get("/api/me/").status_code, 401)
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get("/api/me/").status_code, 403)
        self.assertEqual(self.client.get("/api/").status_code, 403)

    def test_catalog_filters_categories_teacher_and_available(self):
        all_courses = self.client.get("/api/courses/?category=professional_elective").json()
        self.assertTrue(
            all(
                item["course"]["category"] == "professional_elective"
                for item in all_courses["courses"]
            )
        )
        filtered = self.client.get("/api/courses/?category=professional_elective&q=網站").json()
        self.assertEqual(filtered["count"], 1)
        self.assertEqual(len(filtered["courses"][0]["offerings"]), 2)
        eligible = self.client.get(
            "/api/courses/?category=professional_elective&available=1"
        ).json()
        courses = {item["course"]["code"] for item in eligible["courses"]}
        self.assertNotIn("NTUB115-104", courses)
        self.assertIn("NTUB115-101", courses)
        self.assertEqual(self.client.get("/api/periods/").json()["periods"][0]["number"], 1)

    def test_details_offer_sections_syllabi_and_conflicts(self):
        course = Course.objects.get(code="NTUB115-103")
        result = self.client.get(f"/api/courses/{course.pk}/").json()
        by_section = {off["section"]: off for off in result["offerings"]}
        self.assertNotEqual(
            by_section["A"]["syllabus"]["evaluation"], by_section["B"]["syllabus"]["evaluation"]
        )
        self.assertFalse(by_section["A"]["can_select"])
        self.assertTrue(by_section["B"]["can_select"])
        self.assertIn("與既有課表衝堂。", by_section["A"]["unavailable_reasons"])
        self.assertEqual(by_section["A"]["slots"][0]["periods"], [5, 6, 7])
        self.assertEqual(by_section["B"]["slots"][0]["periods"], [1, 2, 3])

    def test_conflict_and_occupied_course_are_labeled(self):
        result = self.client.get("/api/courses/?category=professional_elective").json()
        indexed = {entry["course"]["code"]: entry["offerings"] for entry in result["courses"]}
        self.assertEqual(indexed["NTUB115-104"][0]["remaining"], 0)
        self.assertFalse(
            next(item for item in indexed["NTUB115-103"] if item["section"] == "A")["can_select"]
        )

    def test_filters_by_available_day_and_period(self):
        response = self.client.get("/api/courses/?day=3&period=5")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            any(item["course"]["code"] == "NTUB115-101" for item in response.json()["courses"])
        )
        self.assertEqual(self.client.get("/api/courses/?day=7&period=20").status_code, 400)

    def test_preview_is_read_only_and_reports_changes(self):
        offering = self.get_offering("101")
        before = Enrollment.objects.count()
        preview = self.post("/api/preview/", {"offering_ids": [offering.pk]}).json()
        self.assertTrue(preview["ok"])
        self.assertEqual(preview["confirmed_credits"], 18)
        self.assertEqual(preview["total_credits"], 21)
        self.assertEqual(len(preview["added_slots"]), 1)
        self.assertEqual(Enrollment.objects.count(), before)
        self.assertEqual(self.client.get("/api/preview/").status_code, 405)

    def test_enroll_and_drop_and_reenroll(self):
        offering = self.get_offering("101")
        add = self.post("/api/enrollments/", {"offering_ids": [offering.pk]})
        self.assertEqual(add.status_code, 200, add.content)
        self.assertEqual(add.json()["credits"]["confirmed"], 21)
        response = self.post("/api/enrollments/drop/", {"offering_id": offering.pk})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["credits"]["confirmed"], 18)
        self.assertEqual(
            self.post("/api/enrollments/", {"offering_ids": [offering.pk]}).status_code, 200
        )
        self.assertEqual(
            Enrollment.objects.filter(student=self.student, offering=offering).count(), 1
        )

    def test_reject_duplicate_enrollment(self):
        offering = self.get_offering("101")
        self.post("/api/enrollments/", {"offering_ids": [offering.pk]})
        response = self.post("/api/enrollments/", {"offering_ids": [offering.pk]})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            Enrollment.objects.filter(student=self.student, offering=offering).count(), 1
        )

    def test_no_enrollment_for_full_class(self):
        offering = self.get_offering("104")
        result = self.post("/api/enrollments/", {"offering_ids": [offering.pk]})
        self.assertEqual(result.status_code, 400)
        self.assertEqual(
            Enrollment.objects.filter(student=self.student, offering=offering).count(), 0
        )

    def test_conflicting_section_cannot_be_selected(self):
        offering = self.get_offering("103", "A")
        data = self.post("/api/preview/", {"offering_ids": [offering.pk]}).json()
        self.assertFalse(data["ok"])
        self.assertTrue(data["errors"][0]["conflicts"])
        self.assertEqual(
            self.post("/api/enrollments/", {"offering_ids": [offering.pk]}).status_code, 400
        )

    def test_23_plus_3_is_over_limit(self):
        digital, english, web = (
            self.get_offering("101"),
            self.get_offering("102"),
            self.get_offering("103", "B"),
        )
        result = self.post("/api/enrollments/", {"offering_ids": [digital.pk, english.pk]})
        self.assertEqual(result.status_code, 200, result.content)
        self.assertEqual(result.json()["credits"]["confirmed"], 23)
        trial = self.post("/api/preview/", {"offering_ids": [web.pk]}).json()
        self.assertFalse(trial["ok"])
        self.assertEqual(trial["total_credits"], 26)
        self.assertEqual(
            self.post("/api/enrollments/", {"offering_ids": [web.pk]}).status_code, 400
        )
        self.assertEqual(self.client.get("/api/me/").json()["credits"]["confirmed"], 23)

    def test_multi_select_rolls_back_if_one_invalid(self):
        digital, full = self.get_offering("101"), self.get_offering("104")
        response = self.post("/api/enrollments/", {"offering_ids": [digital.pk, full.pk]})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Enrollment.objects.filter(student=self.student, offering=digital).exists())

    def test_multi_select_rejects_same_course_twice(self):
        a, b = self.get_offering("101", "A"), self.get_offering("101", "B")
        result = self.post("/api/enrollments/", {"offering_ids": [a.pk, b.pk]})
        self.assertEqual(result.status_code, 400)
        self.assertFalse(
            Enrollment.objects.filter(student=self.student, offering__course=a.course).exists()
        )

    def test_assigned_mandatory_cannot_drop_from_api(self):
        offering = self.get_offering("001")
        response = self.post("/api/enrollments/drop/", {"offering_id": offering.pk})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            Enrollment.objects.get(student=self.student, offering=offering).status, "enrolled"
        )

    def test_switch_class_is_atomic_and_preserves_credit(self):
        a, b = self.get_offering("101", "A"), self.get_offering("101", "B")
        self.post("/api/enrollments/", {"offering_ids": [a.pk]})
        result = self.post(
            "/api/enrollments/switch/",
            {
                "from_offering_id": a.pk,
                "to_offering_id": b.pk,
            },
        )
        self.assertEqual(result.status_code, 200, result.content)
        self.assertEqual(result.json()["credits"]["confirmed"], 21)
        self.assertEqual(Enrollment.objects.get(student=self.student, offering=a).status, "dropped")
        self.assertEqual(
            Enrollment.objects.get(student=self.student, offering=b).status, "enrolled"
        )

    def test_failed_switch_keeps_original_section(self):
        a, b = self.get_offering("101", "A"), self.get_offering("101", "B")
        self.post("/api/enrollments/", {"offering_ids": [a.pk]})
        b.capacity = 1
        b.save()
        Enrollment.objects.create(student=self.other, offering=b)
        response = self.post(
            "/api/enrollments/switch/",
            {
                "from_offering_id": a.pk,
                "to_offering_id": b.pk,
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            Enrollment.objects.get(student=self.student, offering=a).status, "enrolled"
        )
        self.assertFalse(
            Enrollment.objects.filter(student=self.student, offering=b, status="enrolled").exists()
        )

    def test_different_course_cannot_switch(self):
        a, b = self.get_offering("101"), self.get_offering("102")
        self.post("/api/enrollments/", {"offering_ids": [a.pk]})
        self.assertEqual(
            self.post(
                "/api/enrollments/switch/",
                {
                    "from_offering_id": a.pk,
                    "to_offering_id": b.pk,
                },
            ).status_code,
            400,
        )

    def test_recommendations_and_remaining_credit_filter(self):
        digital, english = self.get_offering("101"), self.get_offering("102")
        self.post("/api/enrollments/", {"offering_ids": [digital.pk, english.pk]})
        results = self.client.get("/api/recommendations/?remaining=1").json()
        self.assertTrue(results["suggestions"])
        self.assertTrue(all(x["course"]["credits"] <= 2 for x in results["suggestions"]))

    def test_preview_csrf_allows_local_origin_without_port(self):
        browser = Client(enforce_csrf_checks=True, HTTP_HOST="127.0.0.1:8000")
        browser.force_login(self.student)
        browser.get("/api/me/")
        csrf_token = browser.cookies["csrftoken"].value
        payload = json.dumps({"offering_ids": [self.get_offering("101").pk]})

        for origin in ("http://127.0.0.1", "http://localhost"):
            with self.subTest(origin=origin):
                response = browser.post(
                    "/api/preview/",
                    payload,
                    content_type="application/json",
                    HTTP_ORIGIN=origin,
                    HTTP_X_CSRFTOKEN=csrf_token,
                )
                self.assertEqual(response.status_code, 200, response.content)

        self.assertEqual(
            browser.post(
                "/api/preview/",
                payload,
                content_type="application/json",
                HTTP_ORIGIN="http://malicious.example",
                HTTP_X_CSRFTOKEN=csrf_token,
            ).status_code,
            403,
        )
        self.assertEqual(
            browser.post(
                "/api/preview/",
                payload,
                content_type="application/json",
                HTTP_ORIGIN="http://127.0.0.1",
            ).status_code,
            403,
        )

    def test_csrf_cookie_and_post_enforcement(self):
        c = Client(enforce_csrf_checks=True)
        c.force_login(self.student)
        self.assertEqual(c.get("/api/me/").status_code, 200)
        self.assertIn("csrftoken", c.cookies)
        offering = self.get_offering("101")
        self.assertEqual(
            c.post(
                "/api/enrollments/",
                json.dumps(
                    {
                        "offering_ids": [offering.pk],
                    }
                ),
                content_type="application/json",
            ).status_code,
            403,
        )
        result = c.post(
            "/api/enrollments/",
            json.dumps(
                {
                    "offering_ids": [offering.pk],
                }
            ),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=c.cookies["csrftoken"].value,
        )
        self.assertEqual(result.status_code, 200, result.content)

    def test_sqlite_lock_returns_retryable_error(self):
        offering = self.get_offering("101")
        with patch("courses.api.select", side_effect=OperationalError("database table is locked")):
            response = self.post("/api/enrollments/", {"offering_ids": [offering.pk]})
        self.assertEqual(response.status_code, 409)
        self.assertIn("稍後再試", response.json()["error"])

    def test_reject_invalid_json_and_body(self):
        self.assertEqual(
            self.client.post(
                "/api/preview/",
                "{bad",
                content_type="application/json",
            ).status_code,
            400,
        )
        self.assertEqual(self.post("/api/preview/", {"offering_ids": "text"}).status_code, 400)
        self.assertEqual(self.post("/api/preview/", {"offering_ids": [True]}).status_code, 400)
        self.assertEqual(self.post("/api/preview/", {"offering_ids": [999999]}).status_code, 400)

    def test_writing_other_semester_is_forbidden(self):
        current = self.get_offering("101")
        future = CourseOffering.objects.create(
            course=current.course,
            semester="116-1",
            day_of_week=6,
            start_time=time(8, 10),
            end_time=time(9),
            room="未來學期教室",
        )
        self.assertEqual(self.client.get("/api/timetable/?semester=116-1").status_code, 200)
        for url, payload in (
            ("/api/preview/", {"offering_ids": [future.pk]}),
            ("/api/enrollments/", {"offering_ids": [future.pk]}),
            ("/api/enrollments/drop/", {"offering_id": current.pk}),
            (
                "/api/enrollments/switch/",
                {"from_offering_id": current.pk, "to_offering_id": future.pk},
            ),
        ):
            response = self.post(url, {"semester": "116-1", **payload})
            self.assertEqual(response.status_code, 400, (url, response.content))
        self.assertFalse(Enrollment.objects.filter(student=self.student, offering=future).exists())

    def test_completed_course_is_not_available_for_reenrollment(self):
        offering = self.get_offering("101")
        CompletedCourse.objects.create(
            student=self.student, course=offering.course, status="passed"
        )
        preview = self.post("/api/preview/", {"offering_ids": [offering.pk]}).json()
        self.assertFalse(preview["ok"])
        self.assertIn("已修習通過", " ".join(preview["errors"][0]["reasons"]))
        self.assertEqual(
            self.post("/api/enrollments/", {"offering_ids": [offering.pk]}).status_code, 400
        )
        course = self.client.get(f"/api/courses/{offering.course_id}/").json()
        self.assertTrue(
            all("已修習通過" in " ".join(row["unavailable_reasons"]) for row in course["offerings"])
        )

    def test_off_grid_meeting_keeps_its_real_time(self):
        course = Course.objects.create(code="OFFGRID", name="午間講座", credits=2)
        offering = CourseOffering.objects.create(
            course=course,
            semester="115-1",
            day_of_week=5,
            start_time=time(12, 5),
            end_time=time(12, 55),
            room="午間教室",
        )
        response = self.client.get(f"/api/courses/{course.pk}/")
        self.assertEqual(response.status_code, 200, response.content)
        slot = response.json()["offerings"][0]["slots"][0]
        self.assertEqual((slot["start"], slot["end"], slot["periods"]), ("12:05", "12:55", []))
        self.assertEqual(
            self.post("/api/preview/", {"offering_ids": [offering.pk]}).json()["ok"], True
        )

    def test_partially_off_grid_course_shows_actual_time(self):
        course = Course.objects.create(code="OFFGRID-PARTIAL", name="跨午休講座", credits=2)
        for section, start, end in (
            ("A", time(12, 5), time(13, 45)),
            ("B", time(9, 40), time(10, 20)),
            ("C", time(8, 10), time(9)),
        ):
            CourseOffering.objects.create(
                course=course,
                semester="115-1",
                section=section,
                day_of_week=5,
                start_time=start,
                end_time=end,
                room=f"測試教室{section}",
            )
        response = self.client.get(f"/api/courses/{course.pk}/")
        self.assertEqual(response.status_code, 200, response.content)
        slots = {item["section"]: item["slots"][0] for item in response.json()["offerings"]}
        self.assertEqual(
            (slots["A"]["start"], slots["A"]["end"], slots["A"]["periods"]),
            ("12:05", "13:45", []),
        )
        self.assertEqual(
            (slots["B"]["start"], slots["B"]["end"], slots["B"]["periods"]),
            ("09:40", "10:20", []),
        )
        self.assertEqual(slots["C"]["periods"], [1])

    def test_other_semester_is_not_selected(self):
        current = self.client.get("/api/timetable/?semester=115-2").json()
        self.assertEqual(current["credits"]["confirmed"], 0)
        self.assertEqual(current["enrollments"], [])

    def test_grade_four_minimum_and_114_curriculum(self):
        profile = StudentProfile.objects.get(student=self.student)
        profile.grade = 4
        profile.admission_year = 114
        profile.save()
        response = self.client.get("/api/me/").json()
        self.assertEqual(response["credits"]["minimum"], 9)
        self.assertEqual(response["curriculum"]["professional_elective_target"], 33)

    def test_completion_updates_graduation_only(self):
        course = Course.objects.get(code="NTUB115-101")
        CompletedCourse.objects.create(student=self.student, course=course, status="passed")
        response = self.client.get("/api/me/").json()
        self.assertEqual(response["curriculum"]["professional_elective"]["completed"], 3)
        self.assertEqual(response["curriculum"]["professional_elective"]["selected"], 0)

    def test_plan_supports_future_electives_without_current_offerings(self):
        future = Course.objects.create(
            code="FUTURE-ELECTIVE",
            name="未來開課選修",
            category="professional_elective",
            credits=3,
            program_type="four_year",
        )
        self.assertFalse(CourseOffering.objects.filter(course=future).exists())
        data = self.client.get("/api/plan/").json()
        self.assertIn(future.pk, {course["id"] for course in data["available_courses"]})
        added = self.post(
            "/api/plan/courses/",
            {
                "course_id": future.pk,
                "term": 6,
                "version": data["version"],
            },
        )
        self.assertEqual(added.status_code, 200, added.content)
        self.assertIn(
            future.pk, {entry["course"]["id"] for entry in added.json()["terms"][5]["courses"]}
        )
        self.assertNotIn(future.pk, {course["id"] for course in added.json()["available_courses"]})

    def test_plan_rejects_courses_from_another_degree_program(self):
        course = Course.objects.get(code="NTUB-DEMO-503")
        response = self.post(
            "/api/plan/courses/",
            {
                "course_id": course.pk,
                "term": 2,
                "version": 0,
            },
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("學制", response.json()["error"])
        self.assertFalse(StudyPlan.objects.filter(student=self.student).exists())

    def test_graduation_credits_count_each_course_once(self):
        course = Course.objects.get(code="NTUB115-105")
        original = self.client.get("/api/plan/").json()
        added = self.post(
            "/api/plan/courses/",
            {
                "course_id": course.pk,
                "term": 2,
                "version": original["version"],
            },
        ).json()
        before = added["graduation"]["covered_credits"]
        self.assertEqual(added["graduation"]["general_core_covered"]["civic"], 2)
        CompletedCourse.objects.create(student=self.student, course=course, status="passed")
        with_completion = self.client.get("/api/plan/").json()
        self.assertEqual(with_completion["graduation"]["covered_credits"], before)
        self.assertEqual(with_completion["graduation"]["general_core_covered"]["civic"], 2)

    def test_plan_read_is_not_mutating(self):
        before = StudyPlan.objects.count()
        response = self.client.get("/api/plan/")
        data = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["version"], 0)
        self.assertEqual(len(data["terms"]), 8)
        self.assertTrue(data["terms"][0]["courses"])
        self.assertEqual(StudyPlan.objects.count(), before)

    def test_plan_add_move_delete_and_version(self):
        course = Course.objects.get(code="NTUB115-101")
        first = self.post(
            "/api/plan/courses/",
            {
                "course_id": course.pk,
                "term": 5,
                "version": 0,
            },
        )
        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(first.json()["version"], 1)
        entry = PlannedCourse.objects.get(plan__student=self.student, course=course)
        move = self.client.patch(
            f"/api/plan/courses/{entry.pk}/",
            json.dumps(
                {
                    "term": 6,
                    "version": 1,
                    "position": 3,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(move.status_code, 200, move.content)
        self.assertEqual(move.json()["version"], 2)
        entry.refresh_from_db()
        self.assertEqual((entry.term, entry.position), (6, 3))
        delete = self.client.delete(
            f"/api/plan/courses/{entry.pk}/",
            json.dumps(
                {
                    "version": 2,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(delete.status_code, 200, delete.content)
        self.assertEqual(delete.json()["version"], 3)
        self.assertFalse(PlannedCourse.objects.filter(pk=entry.pk).exists())

    def test_plan_prevents_stale_update_and_invalid_term(self):
        course = Course.objects.get(code="NTUB115-101")
        self.assertEqual(
            self.post(
                "/api/plan/courses/",
                {
                    "course_id": course.pk,
                    "term": 9,
                    "version": 0,
                },
            ).status_code,
            400,
        )
        self.assertFalse(StudyPlan.objects.filter(student=self.student).exists())
        self.assertEqual(
            self.post(
                "/api/plan/courses/",
                {
                    "course_id": course.pk,
                    "term": 3,
                    "version": 0,
                },
            ).status_code,
            200,
        )
        self.assertEqual(
            self.post(
                "/api/plan/courses/",
                {
                    "course_id": course.pk,
                    "term": 4,
                    "version": 0,
                },
            ).status_code,
            409,
        )

    def test_plan_cannot_modify_other_students_entry(self):
        course = Course.objects.get(code="NTUB115-101")
        self.client.force_login(self.other)
        self.post(
            "/api/plan/courses/",
            {
                "course_id": course.pk,
                "term": 3,
                "version": 0,
            },
        )
        entry = PlannedCourse.objects.get(plan__student=self.other)
        self.client.force_login(self.student)
        response = self.client.patch(
            f"/api/plan/courses/{entry.pk}/",
            json.dumps(
                {
                    "term": 5,
                    "version": 0,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(PlannedCourse.objects.get(pk=entry.pk).term, 3)

    def test_plan_can_reschedule_required_without_changing_enrollment(self):
        course = Course.objects.get(code="NTUB115-001")
        original = Enrollment.objects.get(student=self.student, offering__course=course)
        result = self.post(
            "/api/plan/courses/",
            {
                "course_id": course.pk,
                "term": 3,
                "version": 0,
            },
        )
        self.assertEqual(result.status_code, 200, result.content)
        self.assertEqual(
            PlannedCourse.objects.get(plan__student=self.student, course=course).term, 3
        )
        self.assertEqual(Enrollment.objects.get(pk=original.pk).status, "enrolled")
        self.assertIn("正式", result.json()["warnings"][0]["message"])
        self.assertEqual(result.json()["terms"][2]["courses"][-1]["course"]["id"], course.pk)

    def test_empty_selection_is_rejected(self):
        response = self.post("/api/enrollments/", {"offering_ids": []})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Enrollment.objects.filter(student=self.student).count(), 8)

    def test_zero_results_suggests_relaxing_filter(self):
        response = self.client.get(
            "/api/courses/?category=professional_elective&max_credits=1",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 0)
        self.assertIn("max_credits", {entry["remove"] for entry in data["relaxations"]})

    def test_completed_prerequisite_unlocks_elective(self):
        web = self.get_offering("103", "B")
        required = Course.objects.get(code="NTUB115-001")
        CoursePrerequisite.objects.get_or_create(course=web.course, required_course=required)
        before = self.post("/api/preview/", {"offering_ids": [web.pk]}).json()
        self.assertFalse(before["ok"])
        self.assertIn("尚未完成先修課程。", before["errors"][0]["reasons"])
        CompletedCourse.objects.create(student=self.student, course=required, status="passed")
        after = self.post("/api/preview/", {"offering_ids": [web.pk]}).json()
        self.assertTrue(after["ok"])

    def test_model_and_api_obey_max_25(self):
        a, english, web = (
            self.get_offering("101"),
            self.get_offering("102"),
            self.get_offering("103", "B"),
        )
        self.post("/api/enrollments/", {"offering_ids": [a.pk, english.pk]})
        with self.assertRaises(ValidationError):
            Enrollment.objects.create(student=self.student, offering=web)
        self.assertEqual(
            self.post("/api/enrollments/", {"offering_ids": [web.pk]}).status_code, 400
        )
        self.assertEqual(self.client.get("/api/me/").json()["credits"]["confirmed"], 23)

    def test_admission_year_filters_curriculum_presets(self):
        profile = StudentProfile.objects.get(student=self.other)
        profile.admission_year = 114
        profile.save()
        self.client.force_login(self.other)
        plan = self.client.get("/api/plan/").json()
        self.assertEqual(plan["total_planned_credits"], 0)
        self.assertEqual(plan["graduation"]["professional_target"], 33)

    def test_plan_flags_bad_prerequisite_order(self):
        required = Course.objects.get(code="NTUB115-201")
        required.recommended_term = 4
        required.save()
        response = self.client.get("/api/plan/").json()
        self.assertTrue(any(w["required"] == "程式設計（二）" for w in response["warnings"]))

    def test_selected_elective_appears_in_plan_as_locked(self):
        digital = self.get_offering("101")
        self.post("/api/enrollments/", {"offering_ids": [digital.pk]})
        response = self.client.get("/api/plan/").json()
        current = response["terms"][0]["courses"]
        self.assertTrue(
            any(
                item["course"]["id"] == digital.course_id
                and item["source"] == "enrolled"
                and item["locked"]
                for item in current
            )
        )
        self.assertEqual(response["graduation"]["professional_planned"], 3)

    def test_demo_catalog_has_four_year_two_year_and_other_departments(self):
        sample = Course.objects.filter(code__startswith="NTUB-DEMO-")
        self.assertGreaterEqual(sample.count(), 26)
        self.assertTrue(sample.filter(program_type="two_year", department="資訊管理系").exists())
        self.assertTrue(sample.filter(program_type="four_year", department="企業管理系").exists())
        self.assertTrue(
            CourseOffering.objects.filter(
                course__code="NTUB115-001",
                section="B",
                assigned_class="資管一乙",
            ).exists()
        )

    def test_catalog_filters_degree_department_grade_and_section(self):
        response = self.client.get(
            "/api/courses/",
            {
                "program_type": "two_year",
                "department": "資訊管理系",
                "section": "B",
                "grade": 1,
            },
        )
        self.assertEqual(response.status_code, 200, response.content)
        items = response.json()["courses"]
        self.assertTrue(items)
        self.assertTrue(all(item["course"]["program_type"] == "two_year" for item in items))
        self.assertTrue(all(item["course"]["department"] == "資訊管理系" for item in items))
        self.assertTrue(
            all(
                offering["section"] == "B" and offering["min_grade"] <= 1 <= offering["max_grade"]
                for item in items
                for offering in item["offerings"]
            )
        )
        self.assertEqual(self.client.get("/api/courses/?program_type=unknown").status_code, 400)
        self.assertEqual(self.client.get("/api/courses/?grade=5").status_code, 400)

    def test_external_department_search_and_filter(self):
        selected = self.client.get("/api/courses/?department=財務金融系").json()["courses"]
        self.assertTrue(selected)
        self.assertTrue(all(item["course"]["department"] == "財務金融系" for item in selected))
        self.assertTrue(self.client.get("/api/courses/?q=財務金融系").json()["courses"])

    def test_wednesday_chinese_english_have_four_afternoon_periods(self):
        chinese, english = self.get_offering("005"), self.get_offering("006")
        self.assertEqual((chinese.day_of_week, english.day_of_week), (2, 2))
        self.assertEqual((chinese.start_time, chinese.end_time), (time(13, 30), time(15, 15)))
        self.assertEqual((english.start_time, english.end_time), (time(15, 25), time(17, 10)))
        enrolled = self.client.get("/api/me/").json()["enrollments"]
        by_code = {
            row["course"]["code"]: row["offering"]["slots"][0]["periods"] for row in enrolled
        }
        self.assertEqual(by_code["NTUB115-005"], [5, 6])
        self.assertEqual(by_code["NTUB115-006"], [7, 8])

    def test_b_class_demo_student_has_own_required_lessons(self):
        self.client.force_login(User.objects.get(username="demo_student_b"))
        data = self.client.get("/api/me/").json()
        self.assertEqual(data["student"]["class_name"], "資管一乙")
        self.assertEqual(data["credits"]["confirmed"], 18)
        self.assertEqual(len(data["enrollments"]), 8)
        self.assertTrue(all(row["offering"]["section"] == "B" for row in data["enrollments"]))

    def test_two_year_graduation_uses_official_program_requirements(self):
        student = User.objects.get(username="demo_student_two_year")
        self.client.force_login(student)
        dashboard = self.client.get("/api/me/").json()
        self.assertEqual(dashboard["curriculum"]["graduation_target"], 72)
        self.assertEqual(dashboard["curriculum"]["professional_elective_target"], 31)
        plan = self.client.get("/api/plan/").json()
        self.assertEqual(len(plan["terms"]), 4)
        self.assertEqual(plan["graduation"]["target"], 72)
        self.assertEqual(plan["graduation"]["professional_target"], 31)

    def test_two_year_rejects_unreachable_failed_term_and_unrelated_fifth_term(self):
        student = User.objects.get(username="demo_student_two_year")
        self.client.force_login(student)
        course = Course.objects.get(code="NTUB-DEMO-501")
        baseline = self.client.get("/api/plan/").json()
        self.assertEqual(len(baseline["terms"]), 4)
        failed = self.post(
            "/api/plan/failed/",
            {"course_id": course.pk, "term": 6, "retake_term": 7, "version": 0},
        )
        self.assertEqual(failed.status_code, 400, failed.content)
        added = self.post(
            "/api/plan/courses/",
            {"course_id": course.pk, "term": 5, "version": 0},
        )
        self.assertEqual(added.status_code, 400, added.content)
        self.assertFalse(StudyPlan.objects.filter(student=student).exists())

    def test_two_year_plan_extends_for_retake_after_fourth_semester(self):
        student = User.objects.get(username="demo_student_two_year")
        self.client.force_login(student)
        course = Course.objects.get(code="NTUB-DEMO-501")
        current = self.client.get("/api/plan/").json()
        self.assertEqual(len(current["terms"]), 4)
        moved = self.post(
            "/api/plan/courses/",
            {
                "version": current["version"],
                "term": 4,
                "course_id": course.pk,
            },
        )
        self.assertEqual(moved.status_code, 200, moved.content)
        failed = self.post(
            "/api/plan/failed/",
            {
                "version": moved.json()["version"],
                "term": 4,
                "retake_term": 5,
                "course_id": course.pk,
            },
        )
        self.assertEqual(failed.status_code, 200, failed.content)
        self.assertEqual(len(failed.json()["terms"]), 5)
        self.assertTrue(
            any(item["course"]["id"] == course.pk for item in failed.json()["terms"][4]["courses"])
        )

    def test_two_year_profile_minimum_and_study_plan(self):
        student = User.objects.get(username="demo_student_two_year")
        self.client.force_login(student)
        self.assertEqual(self.client.get("/api/me/").json()["student"]["program_type"], "two_year")
        profile = StudentProfile.objects.get(student=student)
        profile.grade = 2
        profile.save()
        self.assertEqual(self.client.get("/api/me/").json()["credits"]["minimum"], 9)
        plan = self.client.get("/api/plan/").json()
        self.assertTrue(plan["terms"][0]["courses"])
        self.assertTrue(
            all(
                item["course"]["program_type"] == "two_year"
                for term in plan["terms"]
                for item in term["courses"]
            )
        )

    def test_cross_system_student_cannot_pick_two_year_course(self):
        offering = CourseOffering.objects.get(course__code="NTUB-DEMO-503", section="A")
        response = self.post("/api/preview/", {"offering_ids": [offering.pk]})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["ok"])
        self.assertIn("此課程學制與目前學生不符。", response.json()["errors"][0]["reasons"])

    def test_eighteen_week_syllabi_and_separate_class_information(self):
        offerings = CourseOffering.objects.filter(course__is_demo=True)
        self.assertGreaterEqual(offerings.count(), 50)
        self.assertTrue(all(len(item.syllabus.get("weeks", [])) == 18 for item in offerings))
        a, b = self.get_offering("001", "A"), self.get_offering("001", "B")
        self.assertEqual((a.class_label, a.target_grade), ("甲班", 1))
        self.assertEqual((b.class_label, b.target_grade), ("乙班", 1))
        detail = self.client.get(f"/api/courses/{a.course_id}/").json()
        self.assertEqual(detail["course"]["program_label"], "四技")
        self.assertEqual(detail["course"]["department"], "資訊管理系")
        self.assertEqual(len(detail["offerings"][0]["syllabus"]["weeks"]), 18)
        self.assertEqual({item["class_label"] for item in detail["offerings"]}, {"甲班", "乙班"})
        self.assertTrue(all(item["grade_label"] == "一年級" for item in detail["offerings"]))
        self.assertTrue(all("class_display" not in item for item in detail["offerings"]))

    def test_class_group_filters_separate_true_class_from_offering_code(self):
        assigned = self.client.get("/api/courses/?class_group=甲班").json()["courses"]
        self.assertTrue(assigned)
        self.assertTrue(
            all(
                offering["class_label"] == "甲班"
                for item in assigned
                for offering in item["offerings"]
            )
        )
        unassigned = self.client.get("/api/courses/?class_group=unassigned").json()["courses"]
        self.assertTrue(unassigned)
        self.assertTrue(
            all(
                offering["class_label"] == ""
                for item in unassigned
                for offering in item["offerings"]
            )
        )
        self.assertEqual(self.client.get("/api/courses/?class_group=四技資管一甲").status_code, 400)

    def test_course_offerings_can_be_single_section_or_unassigned_to_class(self):
        single = CourseOffering.objects.filter(course__code="NTUB-DEMO-302")
        self.assertEqual(single.count(), 1)
        offering = single.get()
        self.assertEqual(offering.class_label, "")
        self.assertEqual(offering.target_grade, 1)
        paired = CourseOffering.objects.filter(course__code="NTUB-DEMO-301")
        self.assertEqual(set(paired.values_list("section", flat=True)), {"A", "B"})
        self.assertTrue(all(not item.class_label for item in paired))
        self.assertEqual(
            CourseOffering.objects.filter(course__code__startswith="NTUB-DEMO-")
            .values("course_id")
            .annotate(n=Count("id"))
            .filter(n=1)
            .count(),
            21,
        )

    def test_future_required_can_move_and_reset_to_curriculum(self):
        course = Course.objects.get(code="NTUB115-201")
        initial = self.client.get("/api/plan/").json()
        term2 = initial["terms"][1]["courses"]
        self.assertTrue(
            any(item["course"]["id"] == course.pk and not item["locked"] for item in term2)
        )
        changed = self.post(
            "/api/plan/courses/",
            {
                "course_id": course.pk,
                "term": 4,
                "version": 0,
            },
        )
        self.assertEqual(changed.status_code, 200, changed.content)
        self.assertFalse(
            any(item["course"]["id"] == course.pk for item in changed.json()["terms"][1]["courses"])
        )
        self.assertTrue(
            any(item["course"]["id"] == course.pk for item in changed.json()["terms"][3]["courses"])
        )
        self.assertEqual(changed.json()["total_planned_credits"], initial["total_planned_credits"])
        entry = PlannedCourse.objects.get(plan__student=self.student, course=course)
        reset = self.client.delete(
            f"/api/plan/courses/{entry.pk}/",
            json.dumps(
                {
                    "version": changed.json()["version"],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(reset.status_code, 200, reset.content)
        self.assertTrue(
            any(item["course"]["id"] == course.pk for item in reset.json()["terms"][1]["courses"])
        )

    def test_failed_required_creates_retake_and_keeps_original_attempt(self):
        course = Course.objects.get(code="NTUB115-201")
        before = self.client.get("/api/plan/").json()
        outcome = self.post(
            "/api/plan/failed/",
            {
                "course_id": course.pk,
                "term": 2,
                "retake_term": 3,
                "version": 0,
            },
        )
        self.assertEqual(outcome.status_code, 200, outcome.content)
        data = outcome.json()
        self.assertTrue(
            any(
                item["course"]["id"] == course.pk and item["source"] == "failed"
                for item in data["terms"][1]["courses"]
            )
        )
        self.assertTrue(
            any(
                item["course"]["id"] == course.pk and item["source"] == "student"
                for item in data["terms"][2]["courses"]
            )
        )
        self.assertEqual(before["total_planned_credits"], data["total_planned_credits"])
        self.assertEqual(
            self.post(
                "/api/plan/failed/",
                {
                    "course_id": course.pk,
                    "term": 2,
                    "version": data["version"],
                },
            ).status_code,
            400,
        )

    def test_current_assigned_failed_scenario_keeps_formal_enrollment(self):
        course = Course.objects.get(code="NTUB115-001")
        before = Enrollment.objects.get(student=self.student, offering__course=course)
        result = self.post(
            "/api/plan/failed/",
            {
                "course_id": course.pk,
                "term": 1,
                "retake_term": 3,
                "version": 0,
            },
        )
        self.assertEqual(result.status_code, 200, result.content)
        self.assertEqual(Enrollment.objects.get(pk=before.pk).status, "enrolled")
        self.assertEqual(result.json()["terms"][0]["courses"][-1]["source"], "failed")
        self.assertTrue(any("正式配課" in entry["message"] for entry in result.json()["warnings"]))

    def test_retake_rejects_invalid_term_and_foreign_course_location(self):
        course = Course.objects.get(code="NTUB115-201")
        self.assertEqual(
            self.post(
                "/api/plan/failed/",
                {
                    "course_id": course.pk,
                    "term": 8,
                    "retake_term": 9,
                    "version": 0,
                },
            ).status_code,
            400,
        )
        self.assertEqual(
            self.post(
                "/api/plan/failed/",
                {
                    "course_id": course.pk,
                    "term": 4,
                    "retake_term": 5,
                    "version": 0,
                },
            ).status_code,
            400,
        )

    def test_restore_failed_returns_course_and_preserves_enrollment(self):
        course = Course.objects.get(code="NTUB115-001")
        enrollment = Enrollment.objects.get(student=self.student, offering__course=course)
        before = self.client.get("/api/plan/").json()
        failed = self.post(
            "/api/plan/failed/",
            {
                "course_id": course.pk,
                "term": 1,
                "version": before["version"],
            },
        ).json()
        restored = self.client.delete(
            "/api/plan/failed/restore/",
            json.dumps(
                {
                    "course_id": course.pk,
                    "term": 1,
                    "version": failed["version"],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(restored.status_code, 200, restored.content)
        result = restored.json()
        entries = [
            entry
            for term in result["terms"]
            for entry in term["courses"]
            if entry["course"]["id"] == course.pk
        ]
        self.assertEqual(len(entries), 1)
        self.assertNotEqual(entries[0]["source"], "failed")
        self.assertTrue(
            any(entry["course"]["id"] == course.pk for entry in result["terms"][0]["courses"])
        )
        self.assertEqual(result["total_planned_credits"], before["total_planned_credits"])
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.status, "enrolled")
        stale = self.client.delete(
            "/api/plan/failed/restore/",
            json.dumps(
                {
                    "course_id": course.pk,
                    "term": 1,
                    "version": failed["version"],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(stale.status_code, 409)

    def test_restore_failed_requires_latest_attempt(self):
        course = Course.objects.get(code="NTUB115-201")
        first = self.post(
            "/api/plan/failed/", {"course_id": course.pk, "term": 2, "version": 0}
        ).json()
        second = self.post(
            "/api/plan/failed/", {"course_id": course.pk, "term": 3, "version": first["version"]}
        ).json()
        result = self.client.delete(
            "/api/plan/failed/restore/",
            json.dumps(
                {
                    "course_id": course.pk,
                    "term": 2,
                    "version": second["version"],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(result.status_code, 400)
        self.assertEqual(self.client.get("/api/plan/").json()["version"], second["version"])

    def test_retake_cannot_reset_remove_or_move_before_failure(self):
        course = Course.objects.get(code="NTUB115-201")
        failed = self.post(
            "/api/plan/failed/", {"course_id": course.pk, "term": 2, "version": 0}
        ).json()
        entry = PlannedCourse.objects.get(plan__student=self.student, course=course)
        for method in (self.client.delete, self.client.patch):
            response = method(
                f"/api/plan/courses/{entry.pk}/",
                json.dumps(
                    {
                        "version": failed["version"],
                        "term": 2,
                    }
                ),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(self.client.get("/api/plan/").json()["version"], failed["version"])

    def test_legacy_reset_keeps_failure_and_retake_separate_and_restorable(self):
        course = Course.objects.get(code="NTUB115-201")
        failed = self.post(
            "/api/plan/failed/", {"course_id": course.pk, "term": 2, "version": 0}
        ).json()
        PlannedCourse.objects.filter(plan__student=self.student, course=course).delete()
        data = self.client.get("/api/plan/").json()
        matches = [
            (term["term"], entry)
            for term in data["terms"]
            for entry in term["courses"]
            if entry["course"]["id"] == course.pk
        ]
        self.assertEqual(len(matches), 2)
        self.assertEqual({term for term, entry in matches}, {2, 3})
        self.assertTrue(next(entry for term, entry in matches if term == 3)["is_retake"])
        restored = self.client.delete(
            "/api/plan/failed/restore/",
            json.dumps(
                {
                    "course_id": course.pk,
                    "term": 2,
                    "version": failed["version"],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(restored.status_code, 200, restored.content)
        self.assertEqual(
            sum(
                entry["course"]["id"] == course.pk
                for term in restored.json()["terms"]
                for entry in term["courses"]
            ),
            1,
        )
