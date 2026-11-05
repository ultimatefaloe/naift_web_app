from django.views.generic import TemplateView

from elections.models import Election


class HomeView(TemplateView):
    template_name = "core/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["latest_election"] = (
            Election.objects.exclude(status=Election.STATUS_ENDED).order_by("-id").first()
        )
        return context


class AboutView(TemplateView):
    template_name = "core/about.html"


class AcademicsView(TemplateView):
    template_name = "core/academics.html"


class CreditView(TemplateView):
    template_name = "core/credit.html"
