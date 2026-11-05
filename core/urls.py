from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("about/", views.AboutView.as_view(), name="about"),
    path("academics/", views.AcademicsView.as_view(), name="academics"),
    path("credit/", views.CreditView.as_view(), name="credit"),
]
