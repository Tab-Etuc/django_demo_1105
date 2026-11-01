from django.urls import path

from . import api, plans

urlpatterns = [
    path("", api.index),
    path("me/", api.me),
    path("periods/", api.periods),
    path("courses/", api.courses),
    path("courses/<int:course_id>/", api.course_detail),
    path("timetable/", api.timetable),
    path("preview/", api.preview),
    path("recommendations/", api.recommendations),
    path("enrollments/", api.enroll_api),
    path("enrollments/drop/", api.drop_api),
    path("enrollments/switch/", api.switch_api),
    path("plan/", plans.plan),
    path("plan/failed/", plans.mark_failed),
    path("plan/failed/restore/", plans.restore_failed),
    path("plan/courses/", plans.add_plan_course),
    path("plan/courses/<int:entry_id>/", plans.change_plan_course),
]
