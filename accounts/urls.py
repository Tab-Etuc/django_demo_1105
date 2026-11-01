from django.contrib.auth import views as auth_views
from django.urls import path

from .views import DemoLoginView, demo_guest_login

urlpatterns = [
    path("login/", DemoLoginView.as_view(), name="login"),
    path("guest/", demo_guest_login, name="demo_guest_login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]
