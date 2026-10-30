from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase

from admin_panel.models import AdminProfile
from .models import Position


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
