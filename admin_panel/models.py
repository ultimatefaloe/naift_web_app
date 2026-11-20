from django.conf import settings
from django.db import models


class AdminProfile(models.Model):
    ROLE_CHAIRMAN = "chairman"
    ROLE_MEMBER = "member"
    ROLE_CHOICES = [
        (ROLE_CHAIRMAN, "Chairman"),
        (ROLE_MEMBER, "Member"),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.user.username
