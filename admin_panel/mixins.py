from django.contrib import messages
from django.shortcuts import redirect

from .models import AdminProfile


class AdminRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("admin_panel:login")
        if request.user.is_superuser:
            AdminProfile.objects.get_or_create(user=request.user, defaults={"role": None, "is_active": True})
            return super().dispatch(request, *args, **kwargs)
        profile = getattr(request.user, "adminprofile", None)
        if profile is None or not profile.is_active or profile.role is None:
            messages.error(request, "You are not authorized to access the admin dashboard.")
            return redirect("admin_panel:login")
        return super().dispatch(request, *args, **kwargs)


class ChairmanOrAboveRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("admin_panel:login")
        if request.user.is_superuser:
            AdminProfile.objects.get_or_create(user=request.user, defaults={"role": None, "is_active": True})
            return super().dispatch(request, *args, **kwargs)
        profile = getattr(request.user, "adminprofile", None)
        if profile is None or not profile.is_active:
            messages.error(request, "You are not authorized to access the admin dashboard.")
            return redirect("admin_panel:login")
        if profile.role != AdminProfile.ROLE_CHAIRMAN:
            messages.error(request, "You are not authorized to access this page.")
            return redirect("admin_panel:dashboard")
        return super().dispatch(request, *args, **kwargs)
