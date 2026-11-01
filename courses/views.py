from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render


@login_required
def student_app(request):
    if request.user.role != "student":
        raise PermissionDenied
    return render(request, "courses/react_app.html")
