from django.urls import path

from . import views

app_name = "admin_panel"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("positions/", views.PositionListView.as_view(), name="position_list"),
    path("positions/add/", views.PositionCreateView.as_view(), name="position_create"),
    path("positions/<int:pk>/edit/", views.PositionUpdateView.as_view(), name="position_update"),
    path("positions/<int:pk>/delete/", views.PositionDeleteView.as_view(), name="position_delete"),
    path("contestants/", views.ContestantListView.as_view(), name="contestant_list"),
    path("contestants/add/", views.ContestantCreateView.as_view(), name="contestant_create"),
    path("contestants/<int:pk>/edit/", views.ContestantUpdateView.as_view(), name="contestant_update"),
    path("contestants/<int:pk>/delete/", views.ContestantDeleteView.as_view(), name="contestant_delete"),
    path("executives/", views.DashboardView.as_view(), name="executive_list"),
    path("elections/", views.DashboardView.as_view(), name="election_list"),
]
