from django.contrib import admin

from .models import Executive


@admin.register(Executive)
class ExecutiveAdmin(admin.ModelAdmin):
    list_display = ("name", "position", "session", "is_current")
    list_filter = ("session", "is_current")
