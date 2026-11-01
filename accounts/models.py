from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models


class RoleUserManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", "admin")
        if extra_fields["role"] != "admin":
            raise ValueError("Superusers must have the admin role.")
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    objects = RoleUserManager()
    role = models.CharField(
        max_length=10,
        choices=[("student", "Student"), ("teacher", "Teacher"), ("admin", "Admin")],
        default="student",
    )

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        verbose_name = "User"
        verbose_name_plural = "Users"

    def save(self, *args, **kwargs):
        if self.role == "admin" or self.is_superuser:
            self.role = "admin"
            self.is_staff = self.is_superuser = True
        if kwargs.get("update_fields"):
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {
                "role",
                "is_staff",
                "is_superuser",
            }
        super().save(*args, **kwargs)
