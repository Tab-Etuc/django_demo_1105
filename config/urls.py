"""
URL configuration for config project.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

urlpatterns = [
    path("accounts/", include("accounts.urls")),
    path("api/", include("courses.api_urls")),
    path("", include("courses.urls")),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.STATIC_URL,
        document_root=settings.BASE_DIR / "courses" / "static",
    )
