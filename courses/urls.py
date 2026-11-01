from django.urls import path

from . import views

urlpatterns = [
    path("", views.student_app, name="offering_list"),
    path("plans/", views.student_app, name="study_plans"),
]
