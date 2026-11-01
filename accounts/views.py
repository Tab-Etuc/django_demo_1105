from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.core.management import call_command
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import User


class DemoLoginView(LoginView):
    template_name = "accounts/login.html"

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), "guest_enabled": settings.ENABLE_DEMO_GUEST}


@require_POST
def demo_guest_login(request):
    if not settings.ENABLE_DEMO_GUEST:
        raise Http404
    if not User.objects.filter(username="demo_student").exists():
        call_command("seed_demo", verbosity=0)
    guest = get_object_or_404(User, username="demo_student", role="student", is_active=True)
    login(request, guest, backend="django.contrib.auth.backends.ModelBackend")
    next_url = request.POST.get("next", "/")
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        next_url = "/"
    return redirect(next_url)
