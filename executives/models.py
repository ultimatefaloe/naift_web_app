from django.db import models


class Executive(models.Model):
    name = models.CharField(max_length=150)
    position = models.CharField(max_length=100)
    photo = models.ImageField(upload_to="executives/")
    session = models.CharField(max_length=20, help_text='e.g. "2026/2027"')
    is_current = models.BooleanField(default=True)

    class Meta:
        ordering = ["session", "position"]

    def __str__(self):
        return f"{self.name} ({self.position})"
