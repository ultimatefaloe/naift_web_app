from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from admin_panel.models import AdminProfile
from elections.models import Contestant, Election, Position

from .models import Student, Vote


class StudentModelTests(TestCase):
    def test_string_representation(self):
        student = Student.objects.create(
            first_name="Jane", last_name="Doe", matric_number="2022/1/90976CF", level="300"
        )
        self.assertEqual(str(student), "Jane Doe (2022/1/90976CF)")

    def test_valid_matric_number_passes_validation(self):
        student = Student(
            first_name="Jane", last_name="Doe", matric_number="2022/1/90976CF", level="300"
        )
        student.full_clean()

    def test_invalid_matric_number_raises_validation_error(self):
        student = Student(
            first_name="Jane", last_name="Doe", matric_number="not-a-matric-number", level="300"
        )
        with self.assertRaises(ValidationError):
            student.full_clean()

    def test_matric_number_accepts_varying_digit_group_widths(self):
        student = Student(
            first_name="Jane", last_name="Doe", matric_number="2022/12/9CF", level="300"
        )
        student.full_clean()


class VoteModelTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="admin_voting1", password="pass12345")
        admin_profile = AdminProfile.objects.create(user=user, is_admin=True)
        self.position = Position.objects.create(title="President", modified_by=admin_profile)
        self.election = Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            status="ongoing",
            modified_by=admin_profile,
        )
        self.contestant = Contestant.objects.create(
            name="Jane Doe", manifesto="Vote for progress.", position=self.position, election=self.election
        )
        self.student = Student.objects.create(
            first_name="John", last_name="Smith", matric_number="2022/1/90976CF", level="300"
        )

    def test_string_representation(self):
        vote = Vote.objects.create(
            student=self.student, election=self.election, position=self.position, contestant=self.contestant
        )
        self.assertEqual(str(vote), f"{self.student} -> {self.contestant} ({self.position})")

    def test_duplicate_vote_for_same_position_raises_integrity_error(self):
        Vote.objects.create(
            student=self.student, election=self.election, position=self.position, contestant=self.contestant
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Vote.objects.create(
                    student=self.student,
                    election=self.election,
                    position=self.position,
                    contestant=self.contestant,
                )
