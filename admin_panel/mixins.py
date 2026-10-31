from django.contrib import messages
from django.shortcuts import redirect


class AdminRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("admin_panel:login")
        if not hasattr(request.user, "adminprofile") or not request.user.adminprofile.is_admin:
            messages.error(request, "You are not authorized to access the admin dashboard.")
            return redirect("admin_panel:login")
        return super().dispatch(request, *args, **kwargs)
