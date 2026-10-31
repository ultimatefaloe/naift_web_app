from functools import wraps

from django.db import transaction
from django.db.models import Count
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
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


@student_required
def wizard_step(request, position_id):
    election = get_ongoing_election()
    if election is None:
        return redirect("voting:vote_entry")
    if Vote.objects.filter(student=request.student, election=election).exists():
        return redirect("voting:vote_entry")
    position = get_object_or_404(Position, pk=position_id)
    contestants = position.contestants.filter(election=election)
    if request.method == "POST":
        contestant_id = request.POST.get("contestant")
        try:
            contestant_id = int(contestant_id)
        except (TypeError, ValueError):
            raise Http404("Invalid contestant selection.")
        contestant = get_object_or_404(Contestant, pk=contestant_id, position=position, election=election)
        picks = request.session.get("vote_picks", {})
        picks[str(position.id)] = contestant.id
        request.session["vote_picks"] = picks
        return redirect("voting:vote_entry")
    return render(request, "voting/wizard_step.html", {"position": position, "contestants": contestants})


@student_required
def wizard_review(request):
    election = get_ongoing_election()
    if election is None:
        return redirect("voting:vote_entry")
    if Vote.objects.filter(student=request.student, election=election).exists():
        return redirect("voting:vote_entry")
    positions = Position.objects.filter(contestants__election=election).distinct().order_by("title")
    picks = request.session.get("vote_picks", {})
    for position in positions:
        if str(position.id) not in picks:
            return redirect("voting:vote_entry")
    selections = [
        get_object_or_404(Contestant, pk=contestant_id, election=election) for contestant_id in picks.values()
    ]
    if request.method == "POST":
        with transaction.atomic():
            for contestant in selections:
                Vote.objects.create(
                    student=request.student,
                    election=election,
                    position=contestant.position,
                    contestant=contestant,
                )
        request.session.pop("vote_picks", None)
        return redirect("voting:vote_entry")
    return render(request, "voting/wizard_review.html", {"selections": selections})


def results_view(request, pk=None):
    if pk:
        election = get_object_or_404(Election, pk=pk, is_results_published=True)
    else:
        election = Election.objects.filter(is_results_published=True).order_by("-id").first()
        if election is None:
            return render(request, "voting/results_not_published.html")
    tallies = (
        Contestant.objects.filter(election=election)
        .select_related("position")
        .annotate(vote_count=Count("votes"))
        .order_by("position__title", "position_id", "-vote_count")
    )
    return render(request, "voting/results.html", {"election": election, "tallies": tallies})


def results_archive(request):
    elections = Election.objects.filter(is_results_published=True).order_by("-id")
    return render(request, "voting/results_archive.html", {"elections": elections})
