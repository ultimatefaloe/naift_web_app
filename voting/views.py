from functools import wraps

from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from elections.models import Contestant, Election, Position

from .models import Student, Vote


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


def student_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        student_id = request.session.get("student_id")
        student = Student.objects.filter(pk=student_id).first() if student_id else None
        if student is None:
            return redirect("voting:login")
        request.student = student
        return view_func(request, *args, **kwargs)
    return wrapper


def get_ongoing_election():
    return Election.objects.filter(status=Election.STATUS_ONGOING).order_by("-id").first()


@student_required
def vote_entry(request):
    election = get_ongoing_election()
    if election is None:
        return render(request, "voting/no_election.html")
    if Vote.objects.filter(student=request.student, election=election).exists():
        return render(request, "voting/voted.html")
    positions = Position.objects.filter(contestants__election=election).distinct().order_by("title")
    if not positions.exists():
        return render(request, "voting/no_election.html")
    picks = request.session.get("vote_picks", {})
    for position in positions:
        if str(position.id) not in picks:
            return redirect("voting:wizard_step", position_id=position.id)
    return redirect("voting:wizard_review")
