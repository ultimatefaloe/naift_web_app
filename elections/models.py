from django.db import models

from admin_panel.models import AdminProfile


class Position(models.Model):
    title = models.CharField(max_length=100)
    modified_by = models.ForeignKey(AdminProfile, on_delete=models.PROTECT)
    modified_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class Election(models.Model):
    STATUS_UPCOMING = "upcoming"
    STATUS_ONGOING = "ongoing"
    STATUS_ENDED = "ended"
    STATUS_CHOICES = [
        (STATUS_UPCOMING, "Upcoming"),
        (STATUS_ONGOING, "Ongoing"),
        (STATUS_ENDED, "Ended"),
    ]

    session = models.CharField(max_length=20, help_text='e.g. "2026/2027"')
    start_time = models.DateTimeField(help_text="Display label only — does not gate access")
    close_time = models.DateTimeField(help_text="Display label only — does not gate access")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_UPCOMING)
    is_results_published = models.BooleanField(default=False)
    modified_by = models.ForeignKey(AdminProfile, on_delete=models.PROTECT)
    modified_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.session


class Contestant(models.Model):
    name = models.CharField(max_length=150)
    alias = models.CharField(max_length=100, blank=True, help_text="Popularly known as")
    photo = models.ImageField(upload_to="contestants/")
    manifesto = models.TextField()
    position = models.ForeignKey(Position, on_delete=models.CASCADE, related_name="contestants")
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name="contestants")

    def __str__(self):
        return f"{self.name} ({self.position.title})"
