from django.test import TestCase

from .models import User


class RoleTests(TestCase):
    def test_superuser_receives_admin_role(self):
        user = User.objects.create_superuser("admin")
        self.assertEqual(user.role, "admin")
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)

    def test_admin_role_preserves_staff_flags(self):
        user = User.objects.create_user("admin", role="admin")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_student_has_no_staff_permissions(self):
        user = User.objects.create_user("student", role="student")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
