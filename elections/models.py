from django.db import models

from admin_panel.models import AdminProfile


class Position(models.Model):
    title = models.CharField(max_length=100)
    modified_by = models.ForeignKey(AdminProfile, on_delete=models.PROTECT)
    modified_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title
