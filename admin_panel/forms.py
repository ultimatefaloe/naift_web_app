from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from elections.models import Election


class ElectionForm(forms.ModelForm):
    class Meta:
        model = Election
        fields = ["session", "start_time", "close_time", "status", "is_results_published"]
        widgets = {
            "start_time": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "close_time": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        }


class AdminAccountCreateForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ["username", "email"]
