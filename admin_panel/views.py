from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, ListView, TemplateView, UpdateView

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
