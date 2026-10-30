from django.urls import path

from . import views

app_name = "executives"

urlpatterns = [
    path("", views.CurrentExecutiveView.as_view(), name="current"),
]
