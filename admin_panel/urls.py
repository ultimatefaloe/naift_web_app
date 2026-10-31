from django.urls import path

from . import views

app_name = "admin_panel"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("positions/", views.DashboardView.as_view(), name="position_list"),
    path("contestants/", views.DashboardView.as_view(), name="contestant_list"),
    path("executives/", views.DashboardView.as_view(), name="executive_list"),
    path("elections/", views.DashboardView.as_view(), name="election_list"),
]
