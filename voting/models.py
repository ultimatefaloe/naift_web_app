from django.core.validators import RegexValidator
from django.db import models

matric_number_validator = RegexValidator(
    regex=r"^\d{4}/\d+/\d+CF$",
    message="Matric number must be in the format YYYY/<digits>/<digits>CF (e.g. 2022/1/90976CF).",
)


class Student(models.Model):
    LEVEL_CHOICES = [
        ("100", "100 Level"),
        ("200", "200 Level"),
        ("300", "300 Level"),
        ("400", "400 Level"),
        ("500", "500 Level"),
    ]

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    matric_number = models.CharField(max_length=30, unique=True, validators=[matric_number_validator])
    level = models.CharField(max_length=3, choices=LEVEL_CHOICES)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.matric_number})"


class Vote(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="votes")
    election = models.ForeignKey("elections.Election", on_delete=models.CASCADE, related_name="votes")
    position = models.ForeignKey("elections.Position", on_delete=models.CASCADE, related_name="votes")
    contestant = models.ForeignKey("elections.Contestant", on_delete=models.CASCADE, related_name="votes")
    voted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("student", "election", "position")

    def __str__(self):
        return f"{self.student} -> {self.contestant} ({self.position})"
