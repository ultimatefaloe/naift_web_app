from .models import AdminProfile


def admin_role_flags(request):
    user = request.user
    if not user.is_authenticated:
        return {"can_manage_elections": False, "can_manage_committee": False}
    if user.is_superuser:
        return {"can_manage_elections": True, "can_manage_committee": True}
    profile = getattr(user, "adminprofile", None)
    is_chairman = bool(profile and profile.is_active and profile.role == AdminProfile.ROLE_CHAIRMAN)
    return {"can_manage_elections": is_chairman, "can_manage_committee": is_chairman}
