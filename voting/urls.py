from django.urls import path
from django.views.generic import TemplateView

from . import views

app_name = "voting"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("", views.vote_entry, name="vote_entry"),
    path(
        "position/<int:position_id>/",
        TemplateView.as_view(template_name="voting/login.html"),
        name="wizard_step",
    ),
    path(
        "review/",
        TemplateView.as_view(template_name="voting/login.html"),
        name="wizard_review",
    ),
]
