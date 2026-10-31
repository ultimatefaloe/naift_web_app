from django import forms

from elections.models import Election


class ElectionForm(forms.ModelForm):
    class Meta:
        model = Election
        fields = ["session", "start_time", "close_time", "status", "is_results_published"]
        widgets = {
            "start_time": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "close_time": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        }
