from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib import messages
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView, View

from elections.models import Contestant, Election, Position
from executives.models import Executive
from .forms import ElectionForm
from .mixins import AdminRequiredMixin


def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username", "")
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            auth_login(request, user)
            return redirect("admin_panel:dashboard")
        messages.error(request, "Invalid username or password.")
    return render(request, "admin_panel/login.html")


@require_POST
def logout_view(request):
    auth_logout(request)
    return redirect("admin_panel:login")


class DashboardView(AdminRequiredMixin, TemplateView):
    template_name = "admin_panel/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["position_count"] = Position.objects.count()
        context["contestant_count"] = Contestant.objects.count()
        context["executive_count"] = Executive.objects.count()
        context["current_election"] = (
            Election.objects.exclude(status=Election.STATUS_ENDED).order_by("-id").first()
        )
        return context


class PositionListView(AdminRequiredMixin, ListView):
    model = Position
    template_name = "admin_panel/position_list.html"
    context_object_name = "positions"


class PositionCreateView(AdminRequiredMixin, CreateView):
    model = Position
    fields = ["title"]
    template_name = "admin_panel/position_form.html"
    success_url = reverse_lazy("admin_panel:position_list")

    def form_valid(self, form):
        form.instance.modified_by = self.request.user.adminprofile
        return super().form_valid(form)


class PositionUpdateView(AdminRequiredMixin, UpdateView):
    model = Position
    fields = ["title"]
    template_name = "admin_panel/position_form.html"
    success_url = reverse_lazy("admin_panel:position_list")

    def form_valid(self, form):
        form.instance.modified_by = self.request.user.adminprofile
        return super().form_valid(form)


class PositionDeleteView(AdminRequiredMixin, DeleteView):
    model = Position
    template_name = "admin_panel/position_confirm_delete.html"
    success_url = reverse_lazy("admin_panel:position_list")


class ContestantListView(AdminRequiredMixin, ListView):
    model = Contestant
    template_name = "admin_panel/contestant_list.html"
    context_object_name = "contestants"


class ContestantCreateView(AdminRequiredMixin, CreateView):
    model = Contestant
    fields = ["name", "alias", "manifesto", "position", "election", "photo"]
    template_name = "admin_panel/contestant_form.html"
    success_url = reverse_lazy("admin_panel:contestant_list")


class ContestantUpdateView(AdminRequiredMixin, UpdateView):
    model = Contestant
    fields = ["name", "alias", "manifesto", "position", "election", "photo"]
    template_name = "admin_panel/contestant_form.html"
    success_url = reverse_lazy("admin_panel:contestant_list")


class ContestantDeleteView(AdminRequiredMixin, DeleteView):
    model = Contestant
    template_name = "admin_panel/contestant_confirm_delete.html"
    success_url = reverse_lazy("admin_panel:contestant_list")


class ExecutiveListView(AdminRequiredMixin, ListView):
    model = Executive
    template_name = "admin_panel/executive_list.html"
    context_object_name = "executives"


class ExecutiveCreateView(AdminRequiredMixin, CreateView):
    model = Executive
    fields = ["name", "position", "photo", "session", "is_current"]
    template_name = "admin_panel/executive_form.html"
    success_url = reverse_lazy("admin_panel:executive_list")


class ExecutiveUpdateView(AdminRequiredMixin, UpdateView):
    model = Executive
    fields = ["name", "position", "photo", "session", "is_current"]
    template_name = "admin_panel/executive_form.html"
    success_url = reverse_lazy("admin_panel:executive_list")


class ExecutiveDeleteView(AdminRequiredMixin, DeleteView):
    model = Executive
    template_name = "admin_panel/executive_confirm_delete.html"
    success_url = reverse_lazy("admin_panel:executive_list")


class ElectionListView(AdminRequiredMixin, ListView):
    model = Election
    template_name = "admin_panel/election_list.html"
    context_object_name = "elections"


class ElectionCreateView(AdminRequiredMixin, CreateView):
    model = Election
    form_class = ElectionForm
    template_name = "admin_panel/election_form.html"
    success_url = reverse_lazy("admin_panel:election_list")

    def form_valid(self, form):
        form.instance.modified_by = self.request.user.adminprofile
        return super().form_valid(form)


class ElectionUpdateView(AdminRequiredMixin, UpdateView):
    model = Election
    form_class = ElectionForm
    template_name = "admin_panel/election_form.html"
    success_url = reverse_lazy("admin_panel:election_list")

    def form_valid(self, form):
        form.instance.modified_by = self.request.user.adminprofile
        return super().form_valid(form)


class ElectionResultsView(AdminRequiredMixin, DetailView):
    model = Election
    template_name = "admin_panel/election_results.html"
    context_object_name = "election"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Kept in sync with voting.views.results_view's tally query — update
        # both if the ordering/annotation logic ever changes.
        context["tallies"] = (
            Contestant.objects.filter(election=self.object)
            .select_related("position")
            .annotate(vote_count=Count("votes"))
            .order_by("position__title", "position_id", "-vote_count")
        )
        return context


class ElectionStartView(AdminRequiredMixin, View):
    def post(self, request, pk):
        election = get_object_or_404(Election, pk=pk)
        if election.status != Election.STATUS_UPCOMING:
            messages.error(request, "This election must be upcoming to start voting.")
            return redirect("admin_panel:election_list")
        election.status = Election.STATUS_ONGOING
        election.modified_by = request.user.adminprofile
        election.save()
        return redirect("admin_panel:election_list")


class ElectionEndView(AdminRequiredMixin, View):
    def post(self, request, pk):
        election = get_object_or_404(Election, pk=pk)
        if election.status != Election.STATUS_ONGOING:
            messages.error(request, "This election must be ongoing to end voting.")
            return redirect("admin_panel:election_list")
        election.status = Election.STATUS_ENDED
        election.modified_by = request.user.adminprofile
        election.save()
        return redirect("admin_panel:election_list")


class ElectionPublishResultsView(AdminRequiredMixin, View):
    def post(self, request, pk):
        election = get_object_or_404(Election, pk=pk)
        if election.status != Election.STATUS_ENDED or election.is_results_published:
            messages.error(request, "This election must be ended and not yet published to publish results.")
            return redirect("admin_panel:election_list")
        election.is_results_published = True
        election.modified_by = request.user.adminprofile
        election.save()
        return redirect("admin_panel:election_list")
