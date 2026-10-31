from django.urls import path

from . import views

app_name = "voting"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("", views.vote_entry, name="vote_entry"),
    path("position/<int:position_id>/", views.wizard_step, name="wizard_step"),
    path("review/", views.wizard_review, name="wizard_review"),
    path("results/", views.results_view, name="results"),
    path("results/<int:pk>/", views.results_view, name="results_detail"),
]
