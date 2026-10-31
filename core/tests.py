from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from admin_panel.models import AdminProfile
from elections.models import Election


class CorePagesTests(TestCase):
    def test_home_page_returns_200(self):
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/home.html")

    def test_about_page_returns_200(self):
        response = self.client.get(reverse("core:about"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/about.html")

    def test_academics_page_returns_200(self):
        response = self.client.get(reverse("core:academics"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/academics.html")


class HomeMarqueeTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="admin_marquee", password="pass12345")
        self.admin_profile = AdminProfile.objects.create(user=user, is_admin=True)

    def test_no_election_shows_no_marquee(self):
        response = self.client.get(reverse("core:home"))
        self.assertNotContains(response, "Voting Ongoing")
        self.assertNotContains(response, "Election starts")

    def test_upcoming_election_shows_announcement(self):
        Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            status="upcoming",
            modified_by=self.admin_profile,
        )
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, "Election starts")
        self.assertContains(response, "2026/2027")

    def test_ongoing_election_shows_voting_banner(self):
        Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            status="ongoing",
            modified_by=self.admin_profile,
        )
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, "Voting Ongoing")

    def test_ended_election_shows_no_marquee(self):
        Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            status="ended",
            modified_by=self.admin_profile,
        )
        response = self.client.get(reverse("core:home"))
        self.assertNotContains(response, "Voting Ongoing")
        self.assertNotContains(response, "Election starts")
