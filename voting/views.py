from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .models import Student


def login_view(request):
    if request.method == "POST":
        first_name = request.POST.get("first_name", "").strip()
        matric_number = request.POST.get("matric_number", "").strip()
        student = Student.objects.filter(
            first_name__iexact=first_name, matric_number=matric_number
        ).first()
        if student is not None:
            request.session.cycle_key()
            request.session["student_id"] = student.id
            return redirect("voting:vote_entry")
        return render(request, "voting/login.html", {"error": "No matching student record found."})
    return render(request, "voting/login.html")


@require_POST
def logout_view(request):
    request.session.pop("student_id", None)
    return redirect("voting:login")
