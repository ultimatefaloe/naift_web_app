from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase

from admin_panel.models import AdminProfile
from .models import Position, Election


class PositionModelTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="admin1", password="pass12345")
        self.admin_profile = AdminProfile.objects.create(user=user, is_admin=True)

    def test_string_representation(self):
        position = Position.objects.create(title="President", modified_by=self.admin_profile)
        self.assertEqual(str(position), "President")

    def test_save_without_modified_by_raises_integrity_error(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Position.objects.create(title="President")

    def test_deleting_admin_profile_with_position_is_protected(self):
        Position.objects.create(title="President", modified_by=self.admin_profile)
        with self.assertRaises(ProtectedError):
            self.admin_profile.delete()


class ElectionModelTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="admin2", password="pass12345")
        self.admin_profile = AdminProfile.objects.create(user=user, is_admin=True)

    def test_string_representation(self):
        election = Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            status="upcoming",
            modified_by=self.admin_profile,
        )
        self.assertEqual(str(election), "2026/2027")

    def test_default_status_and_results_published(self):
        election = Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            modified_by=self.admin_profile,
        )
        self.assertEqual(election.status, "upcoming")
        self.assertFalse(election.is_results_published)

    def test_save_without_modified_by_raises_integrity_error(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Election.objects.create(
                    session="2026/2027",
                    start_time="2026-11-01T09:00:00Z",
                    close_time="2026-11-01T17:00:00Z",
                )
