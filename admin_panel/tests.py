from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from elections.models import Contestant, Election, Position
from executives.models import Executive

from .models import AdminProfile

TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


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


@override_settings(STORAGES=TEST_STORAGES)
class ContestantCRUDTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username="admin7", password="pass12345")
        self.admin_profile = AdminProfile.objects.create(user=self.admin_user, is_admin=True)
        self.client.force_login(self.admin_user)
        self.position = Position.objects.create(title="President", modified_by=self.admin_profile)
        self.election = Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            modified_by=self.admin_profile,
        )

    def test_list_view_returns_200(self):
        response = self.client.get(reverse("admin_panel:contestant_list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin_panel/contestant_list.html")

    def test_create_contestant(self):
        # A minimal valid 1x1 GIF — ImageField validates uploads are real images via
        # Pillow, so arbitrary bytes (e.g. b"fake-image-bytes") fail validation.
        gif_1px = (
            b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04"
            b"\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
        )
        photo = SimpleUploadedFile("candidate.gif", gif_1px, content_type="image/gif")
        response = self.client.post(
            reverse("admin_panel:contestant_create"),
            {
                "name": "Jane Doe",
                "alias": "JD",
                "manifesto": "Vote for progress.",
                "position": self.position.pk,
                "election": self.election.pk,
                "photo": photo,
            },
        )
        self.assertRedirects(response, reverse("admin_panel:contestant_list"))
        self.assertTrue(Contestant.objects.filter(name="Jane Doe").exists())

    def test_delete_contestant(self):
        contestant = Contestant.objects.create(
            name="John Smith",
            alias="JS",
            manifesto="Vote for stability.",
            position=self.position,
            election=self.election,
        )
        response = self.client.post(reverse("admin_panel:contestant_delete", args=[contestant.pk]))
        self.assertRedirects(response, reverse("admin_panel:contestant_list"))
        self.assertFalse(Contestant.objects.filter(pk=contestant.pk).exists())


class ExecutiveCRUDTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username="admin8", password="pass12345")
        AdminProfile.objects.create(user=self.admin_user, is_admin=True)
        self.client.force_login(self.admin_user)

    def test_list_view_returns_200(self):
        response = self.client.get(reverse("admin_panel:executive_list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin_panel/executive_list.html")

    def test_delete_executive(self):
        executive = Executive.objects.create(
            name="Jane Doe", position="President", session="2026/2027", is_current=True
        )
        response = self.client.post(reverse("admin_panel:executive_delete", args=[executive.pk]))
        self.assertRedirects(response, reverse("admin_panel:executive_list"))
        self.assertFalse(Executive.objects.filter(pk=executive.pk).exists())


@override_settings(STORAGES=TEST_STORAGES)
class ExecutiveCreateTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username="admin8b", password="pass12345")
        AdminProfile.objects.create(user=self.admin_user, is_admin=True)
        self.client.force_login(self.admin_user)

    def test_create_executive(self):
        gif_1px = (
            b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04"
            b"\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
        )
        photo = SimpleUploadedFile("exec.gif", gif_1px, content_type="image/gif")
        response = self.client.post(
            reverse("admin_panel:executive_create"),
            {
                "name": "Jane Doe",
                "position": "President",
                "session": "2026/2027",
                "is_current": "on",
                "photo": photo,
            },
        )
        self.assertRedirects(response, reverse("admin_panel:executive_list"))
        self.assertTrue(Executive.objects.filter(name="Jane Doe").exists())


class ElectionCRUDTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username="admin9", password="pass12345")
        self.admin_profile = AdminProfile.objects.create(user=self.admin_user, is_admin=True)
        self.client.force_login(self.admin_user)

    def test_list_view_returns_200(self):
        response = self.client.get(reverse("admin_panel:election_list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin_panel/election_list.html")

    def test_create_election_sets_modified_by(self):
        response = self.client.post(
            reverse("admin_panel:election_create"),
            {
                "session": "2026/2027",
                "start_time": "2026-11-01T09:00",
                "close_time": "2026-11-01T17:00",
                "status": "upcoming",
            },
        )
        self.assertRedirects(response, reverse("admin_panel:election_list"))
        election = Election.objects.get(session="2026/2027")
        self.assertEqual(election.modified_by, self.admin_profile)
        self.assertFalse(election.is_results_published)

    def test_update_election_status(self):
        election = Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            modified_by=self.admin_profile,
        )
        response = self.client.post(
            reverse("admin_panel:election_update", args=[election.pk]),
            {
                "session": "2026/2027",
                "start_time": "2026-11-01T09:00",
                "close_time": "2026-11-01T17:00",
                "status": "ongoing",
                "is_results_published": "",
            },
        )
        self.assertRedirects(response, reverse("admin_panel:election_list"))
        election.refresh_from_db()
        self.assertEqual(election.status, "ongoing")

    def test_update_form_prepopulates_existing_datetimes(self):
        election = Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            modified_by=self.admin_profile,
        )
        response = self.client.get(reverse("admin_panel:election_update", args=[election.pk]))
        self.assertContains(response, "2026-11-01T09:00")
        self.assertContains(response, "2026-11-01T17:00")


class ElectionResultsViewTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username="admin10", password="pass12345")
        self.admin_profile = AdminProfile.objects.create(user=self.admin_user, is_admin=True)
        self.client.force_login(self.admin_user)
        self.position = Position.objects.create(title="President", modified_by=self.admin_profile)
        self.election = Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            modified_by=self.admin_profile,
        )
        Contestant.objects.create(
            name="Jane Doe",
            manifesto="Vote for progress.",
            position=self.position,
            election=self.election,
        )

    def test_results_view_shows_contestants_by_position(self):
        response = self.client.get(reverse("admin_panel:election_results", args=[self.election.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin_panel/election_results.html")
        self.assertContains(response, "Jane Doe")
        self.assertContains(response, "President")


class ElectionActionViewTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username="admin11", password="pass12345")
        self.admin_profile = AdminProfile.objects.create(user=self.admin_user, is_admin=True)
        self.client.force_login(self.admin_user)
        self.election = Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            status="upcoming",
            modified_by=self.admin_profile,
        )

    def test_start_view_requires_post(self):
        response = self.client.get(reverse("admin_panel:election_start", args=[self.election.pk]))
        self.assertEqual(response.status_code, 405)

    def test_start_transitions_upcoming_to_ongoing_and_sets_modified_by(self):
        other_user = User.objects.create_user(username="admin12", password="pass12345")
        other_profile = AdminProfile.objects.create(user=other_user, is_admin=True)
        self.election.modified_by = other_profile
        self.election.save()

        response = self.client.post(reverse("admin_panel:election_start", args=[self.election.pk]))
        self.assertRedirects(response, reverse("admin_panel:election_list"))
        self.election.refresh_from_db()
        self.assertEqual(self.election.status, "ongoing")
        self.assertEqual(self.election.modified_by, self.admin_profile)

    def test_start_rejected_when_election_not_upcoming(self):
        self.election.status = "ongoing"
        self.election.save()
        response = self.client.post(reverse("admin_panel:election_start", args=[self.election.pk]))
        self.assertRedirects(response, reverse("admin_panel:election_list"))
        self.election.refresh_from_db()
        self.assertEqual(self.election.status, "ongoing")

    def test_end_transitions_ongoing_to_ended_and_sets_modified_by(self):
        self.election.status = "ongoing"
        self.election.save()
        response = self.client.post(reverse("admin_panel:election_end", args=[self.election.pk]))
        self.assertRedirects(response, reverse("admin_panel:election_list"))
        self.election.refresh_from_db()
        self.assertEqual(self.election.status, "ended")
        self.assertEqual(self.election.modified_by, self.admin_profile)

    def test_end_rejected_when_election_not_ongoing(self):
        response = self.client.post(reverse("admin_panel:election_end", args=[self.election.pk]))
        self.assertRedirects(response, reverse("admin_panel:election_list"))
        self.election.refresh_from_db()
        self.assertEqual(self.election.status, "upcoming")

    def test_publish_results_sets_flag_and_modified_by(self):
        self.election.status = "ended"
        self.election.save()
        response = self.client.post(reverse("admin_panel:election_publish_results", args=[self.election.pk]))
        self.assertRedirects(response, reverse("admin_panel:election_list"))
        self.election.refresh_from_db()
        self.assertTrue(self.election.is_results_published)
        self.assertEqual(self.election.modified_by, self.admin_profile)

    def test_publish_results_rejected_when_election_not_ended(self):
        response = self.client.post(reverse("admin_panel:election_publish_results", args=[self.election.pk]))
        self.assertRedirects(response, reverse("admin_panel:election_list"))
        self.election.refresh_from_db()
        self.assertFalse(self.election.is_results_published)

    def test_publish_results_rejected_when_already_published(self):
        self.election.status = "ended"
        self.election.is_results_published = True
        self.election.save()
        other_user = User.objects.create_user(username="admin13", password="pass12345")
        other_profile = AdminProfile.objects.create(user=other_user, is_admin=True)
        self.election.modified_by = other_profile
        self.election.save()

        response = self.client.post(reverse("admin_panel:election_publish_results", args=[self.election.pk]))
        self.assertRedirects(response, reverse("admin_panel:election_list"))
        self.election.refresh_from_db()
        self.assertEqual(self.election.modified_by, other_profile)

    def test_election_list_shows_start_button_for_upcoming_election(self):
        response = self.client.get(reverse("admin_panel:election_list"))
        self.assertContains(response, "Start Voting")
