from django.views.generic import ListView

from .models import Executive


class CurrentExecutiveView(ListView):
    template_name = "executives/current.html"
    context_object_name = "executives"

    def get_queryset(self):
        return Executive.objects.filter(is_current=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["past"] = Executive.objects.filter(is_current=False).order_by("-session")
        return context
