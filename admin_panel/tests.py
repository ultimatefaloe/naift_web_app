from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from elections.models import Position

from .models import AdminProfile


class AdminProfileModelTests(TestCase):
    def test_string_representation(self):
        user = User.objects.create_user(username="admin1", password="pass12345")
        profile = AdminProfile.objects.create(user=user, is_admin=True)
        self.assertEqual(str(profile), "admin1")


class DashboardAccessTests(TestCase):
    def setUp(self):
        self.non_admin = User.objects.create_user(username="student1", password="pass12345")
        self.admin_user = User.objects.create_user(username="admin4", password="pass12345")
        AdminProfile.objects.create(user=self.admin_user, is_admin=True)

    def test_unauthenticated_user_redirected_to_login(self):
        response = self.client.get(reverse("admin_panel:dashboard"))
        self.assertRedirects(response, reverse("admin_panel:login"))

    def test_authenticated_non_admin_redirected_to_login(self):
        self.client.force_login(self.non_admin)
        response = self.client.get(reverse("admin_panel:dashboard"))
        self.assertRedirects(response, reverse("admin_panel:login"))

    def test_admin_can_access_dashboard(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("admin_panel:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin_panel/dashboard.html")

    def test_logout_clears_session_and_requires_post(self):
        self.client.force_login(self.admin_user)
        response = self.client.post(reverse("admin_panel:logout"))
        self.assertRedirects(response, reverse("admin_panel:login"))
        dashboard_response = self.client.get(reverse("admin_panel:dashboard"))
        self.assertRedirects(dashboard_response, reverse("admin_panel:login"))


class LoginViewTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username="admin5", password="pass12345")
        AdminProfile.objects.create(user=self.admin_user, is_admin=True)

    def test_valid_credentials_log_the_user_in(self):
        response = self.client.post(
            reverse("admin_panel:login"),
            {"username": "admin5", "password": "pass12345"},
        )
        self.assertRedirects(response, reverse("admin_panel:dashboard"))

    def test_invalid_credentials_show_error(self):
        response = self.client.post(
            reverse("admin_panel:login"),
            {"username": "admin5", "password": "wrongpassword"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid username or password.")


class PositionCRUDTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username="admin6", password="pass12345")
        self.admin_profile = AdminProfile.objects.create(user=self.admin_user, is_admin=True)
        self.client.force_login(self.admin_user)

    def test_list_view_returns_200(self):
        response = self.client.get(reverse("admin_panel:position_list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin_panel/position_list.html")

    def test_create_sets_modified_by(self):
        response = self.client.post(reverse("admin_panel:position_create"), {"title": "President"})
        self.assertRedirects(response, reverse("admin_panel:position_list"))
        position = Position.objects.get(title="President")
        self.assertEqual(position.modified_by, self.admin_profile)

    def test_update_position(self):
        position = Position.objects.create(title="Secretary", modified_by=self.admin_profile)
        response = self.client.post(
            reverse("admin_panel:position_update", args=[position.pk]), {"title": "General Secretary"}
        )
        self.assertRedirects(response, reverse("admin_panel:position_list"))
        position.refresh_from_db()
        self.assertEqual(position.title, "General Secretary")

    def test_delete_position(self):
        position = Position.objects.create(title="Treasurer", modified_by=self.admin_profile)
        response = self.client.post(reverse("admin_panel:position_delete", args=[position.pk]))
        self.assertRedirects(response, reverse("admin_panel:position_list"))
        self.assertFalse(Position.objects.filter(pk=position.pk).exists())
