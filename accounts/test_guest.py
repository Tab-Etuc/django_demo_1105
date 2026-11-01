from django.test import Client, TestCase, override_settings

from .models import User


@override_settings(ENABLE_DEMO_GUEST=True)
class GuestLoginTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.guest = User.objects.create_user("demo_student", password="Demo1234!", role="student")

    def test_login_page_has_guest_switch_and_system_title(self):
        response = self.client.get("/accounts/login/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-guest-enabled="true"')
        self.assertContains(response, "<title>登入｜大學選課系統</title>", html=False)
        self.assertContains(response, "/static/courses/favicon.svg")

    def test_guest_login_is_single_post(self):
        self.assertEqual(self.client.get("/accounts/guest/").status_code, 405)
        response = self.client.post("/accounts/guest/", {"next": "/"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/")
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.guest.pk)

    def test_guest_login_keeps_next_on_same_site(self):
        response = self.client.post("/accounts/guest/", {"next": "/plans/"})
        self.assertEqual(response["Location"], "/plans/")
        response = self.client.post("/accounts/guest/", {"next": "https://example.org/"})
        self.assertEqual(response["Location"], "/")

    def test_guest_login_requires_csrf_token(self):
        browser = Client(enforce_csrf_checks=True)
        self.assertEqual(browser.post("/accounts/guest/").status_code, 403)
        browser.get("/accounts/login/")
        token = browser.cookies["csrftoken"].value
        response = browser.post("/accounts/guest/", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 302)

    @override_settings(ENABLE_DEMO_GUEST=False)
    def test_guest_route_disabled_outside_demo(self):
        self.assertEqual(self.client.post("/accounts/guest/").status_code, 404)
        response = self.client.get("/accounts/login/")
        self.assertContains(response, 'data-guest-enabled="false"')

    def test_inactive_demo_account_cannot_enter(self):
        self.guest.is_active = False
        self.guest.save()
        self.assertEqual(self.client.post("/accounts/guest/").status_code, 404)

    def test_fresh_database_guest_button_seeds_account_and_courses(self):
        self.guest.delete()
        self.assertFalse(User.objects.filter(username="demo_student").exists())
        response = self.client.post("/accounts/guest/", {"next": "/plans/"})
        self.assertEqual(response.status_code, 302, response.content)
        self.assertEqual(response["Location"], "/plans/")
        from courses.academic import StudentProfile
        from enrollments.models import Enrollment

        guest = User.objects.get(username="demo_student")
        self.assertTrue(guest.is_active)
        self.assertEqual(StudentProfile.objects.get(student=guest).class_name, "資管一甲")
        self.assertEqual(Enrollment.objects.filter(student=guest, is_assigned=True).count(), 8)
        self.assertEqual(self.client.get("/api/me/").json()["credits"]["confirmed"], 18)
