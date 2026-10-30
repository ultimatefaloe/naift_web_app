from django.contrib.auth.models import User
from django.test import TestCase

from .models import AdminProfile


class AdminProfileModelTests(TestCase):
    def test_string_representation(self):
        user = User.objects.create_user(username="admin1", password="pass12345")
        profile = AdminProfile.objects.create(user=user, is_admin=True)
        self.assertEqual(str(profile), "admin1")
