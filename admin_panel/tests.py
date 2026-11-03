from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from elections.models import Contestant, Election, Position
from executives.models import Executive
from voting.models import Student, Vote

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


class DashboardStatisticsTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username="admin_dashboard_stats", password="pass12345")
        self.admin_profile = AdminProfile.objects.create(user=self.admin_user, is_admin=True)
        self.client.force_login(self.admin_user)

    def test_no_ongoing_election_has_no_chart_positions(self):
        response = self.client.get(reverse("admin_panel:dashboard"))
        self.assertIsNone(response.context["ongoing_election"])
        self.assertEqual(response.context["chart_positions"], [])

    def test_upcoming_or_ended_election_does_not_count_as_ongoing(self):
        Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            status="upcoming",
            modified_by=self.admin_profile,
        )
        Election.objects.create(
            session="2025/2026",
            start_time="2025-11-01T09:00:00Z",
            close_time="2025-11-01T17:00:00Z",
            status="ended",
            modified_by=self.admin_profile,
        )
        response = self.client.get(reverse("admin_panel:dashboard"))
        self.assertIsNone(response.context["ongoing_election"])
        self.assertEqual(response.context["chart_positions"], [])

    def test_ongoing_election_with_contested_position_has_correct_tallies(self):
        election = Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            status="ongoing",
            modified_by=self.admin_profile,
        )
        position = Position.objects.create(title="President", modified_by=self.admin_profile)
        winner = Contestant.objects.create(
            name="Jane Doe", manifesto="Vote for me.", position=position, election=election
        )
        loser = Contestant.objects.create(
            name="John Roe", manifesto="Vote for me too.", position=position, election=election
        )
        student1 = Student.objects.create(
            first_name="A", last_name="One", matric_number="2026/1/00001CF", level="300"
        )
        student2 = Student.objects.create(
            first_name="B", last_name="Two", matric_number="2026/1/00002CF", level="300"
        )
        Vote.objects.create(student=student1, election=election, position=position, contestant=winner)
        Vote.objects.create(student=student2, election=election, position=position, contestant=winner)
        response = self.client.get(reverse("admin_panel:dashboard"))
        chart_positions = response.context["chart_positions"]
        self.assertEqual(len(chart_positions), 1)
        self.assertEqual(chart_positions[0]["position_title"], "President")
        self.assertEqual(chart_positions[0]["data"]["labels"], ["Jane Doe", "John Roe"])
        self.assertEqual(chart_positions[0]["data"]["votes"], [2, 0])

    def test_ongoing_election_with_unopposed_position_has_single_bar(self):
        election = Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            status="ongoing",
            modified_by=self.admin_profile,
        )
        position = Position.objects.create(title="President", modified_by=self.admin_profile)
        Contestant.objects.create(
            name="Jane Doe", manifesto="Vote for me.", position=position, election=election
        )
        response = self.client.get(reverse("admin_panel:dashboard"))
        chart_positions = response.context["chart_positions"]
        self.assertEqual(len(chart_positions), 1)
        self.assertEqual(chart_positions[0]["data"]["labels"], ["Jane Doe"])
        self.assertEqual(chart_positions[0]["data"]["votes"], [0])

    def test_current_executive_widget_shows_only_current_executives(self):
        current = Executive.objects.create(
            name="Jane Doe", position="President", session="2026/2027", is_current=True
        )
        past = Executive.objects.create(
            name="John Smith", position="President", session="2025/2026", is_current=False
        )
        response = self.client.get(reverse("admin_panel:dashboard"))
        self.assertIn(current, response.context["current_executives"])
        self.assertNotIn(past, response.context["current_executives"])

    def test_current_executive_widget_present_regardless_of_election_state(self):
        Executive.objects.create(name="Jane Doe", position="President", session="2026/2027", is_current=True)
        response = self.client.get(reverse("admin_panel:dashboard"))
        self.assertIn(
            Executive.objects.get(name="Jane Doe"),
            response.context["current_executives"],
        )

    def test_chart_tally_excludes_votes_from_a_different_election_even_if_contestant_was_reassigned(self):
        old_election = Election.objects.create(
            session="2025/2026",
            start_time="2025-11-01T09:00:00Z",
            close_time="2025-11-01T17:00:00Z",
            status="ended",
            modified_by=self.admin_profile,
        )
        ongoing_election = Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            status="ongoing",
            modified_by=self.admin_profile,
        )
        position = Position.objects.create(title="President", modified_by=self.admin_profile)
        contestant = Contestant.objects.create(
            name="Jane Doe", manifesto="Vote for me.", position=position, election=old_election
        )
        student = Student.objects.create(
            first_name="A", last_name="One", matric_number="2026/1/00001CF", level="300"
        )
        Vote.objects.create(student=student, election=old_election, position=position, contestant=contestant)
        contestant.election = ongoing_election
        contestant.save()
        response = self.client.get(reverse("admin_panel:dashboard"))
        chart_positions = response.context["chart_positions"]
        self.assertEqual(chart_positions[0]["data"]["votes"], [0])


class DashboardChartRenderingTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username="admin_dashboard_chart", password="pass12345")
        self.admin_profile = AdminProfile.objects.create(user=self.admin_user, is_admin=True)
        self.client.force_login(self.admin_user)

    def test_no_ongoing_election_shows_message_and_no_canvas(self):
        response = self.client.get(reverse("admin_panel:dashboard"))
        self.assertContains(response, "No voting currently in progress")
        self.assertNotContains(response, "<canvas")

    def test_ongoing_election_renders_canvas_per_position(self):
        election = Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            status="ongoing",
            modified_by=self.admin_profile,
        )
        position_a = Position.objects.create(title="President", modified_by=self.admin_profile)
        position_b = Position.objects.create(title="Secretary", modified_by=self.admin_profile)
        Contestant.objects.create(
            name="Jane Doe", manifesto="Vote for me.", position=position_a, election=election
        )
        Contestant.objects.create(
            name="John Roe", manifesto="Vote for me.", position=position_b, election=election
        )
        response = self.client.get(reverse("admin_panel:dashboard"))
        self.assertContains(response, f'id="chart-{position_a.pk}"')
        self.assertContains(response, f'id="chart-{position_b.pk}"')
        self.assertNotContains(response, "No voting currently in progress")

    def test_current_executive_widget_renders_executive_names(self):
        Executive.objects.create(name="Jane Doe", position="President", session="2026/2027", is_current=True)
        response = self.client.get(reverse("admin_panel:dashboard"))
        self.assertContains(response, "Jane Doe")


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

    def test_update_does_not_change_election(self):
        # `Contestant.photo` is a required ImageField with no `blank=True`. If
        # the instance being updated has no photo already attached, Django's
        # ClearableFileInput has no existing file to "keep" when none is
        # resubmitted, so the update POST fails validation on photo alone —
        # which would make this test fail for the wrong reason. Attaching a
        # real photo at creation (same minimal-GIF fixture already used by
        # `test_create_contestant`) lets the update below omit `photo` and
        # still pass, so the test actually isolates the `election` field.
        gif_1px = (
            b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04"
            b"\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
        )
        other_election = Election.objects.create(
            session="2025/2026",
            start_time="2025-11-01T09:00:00Z",
            close_time="2025-11-01T17:00:00Z",
            modified_by=self.admin_profile,
        )
        contestant = Contestant.objects.create(
            name="John Smith",
            alias="JS",
            manifesto="Vote for stability.",
            position=self.position,
            election=self.election,
            photo=SimpleUploadedFile("candidate.gif", gif_1px, content_type="image/gif"),
        )
        response = self.client.post(
            reverse("admin_panel:contestant_update", args=[contestant.pk]),
            {
                "name": "John Smith",
                "alias": "JS",
                "manifesto": "Vote for stability, updated.",
                "position": self.position.pk,
                "election": other_election.pk,
            },
        )
        self.assertRedirects(response, reverse("admin_panel:contestant_list"))
        contestant.refresh_from_db()
        self.assertEqual(contestant.election, self.election)
        self.assertEqual(contestant.manifesto, "Vote for stability, updated.")


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

    def test_results_view_shows_vote_tally(self):
        contestant = Contestant.objects.filter(election=self.election).get()
        student = Student.objects.create(
            first_name="John", last_name="Smith", matric_number="2022/1/90976CF", level="300"
        )
        Vote.objects.create(
            student=student, election=self.election, position=self.position, contestant=contestant
        )
        response = self.client.get(reverse("admin_panel:election_results", args=[self.election.pk]))
        self.assertContains(response, "1 vote")

    def test_results_view_shows_winner_badge_for_unopposed_contestant(self):
        response = self.client.get(reverse("admin_panel:election_results", args=[self.election.pk]))
        self.assertContains(response, "Winner")

    def test_results_view_shows_no_winner_badge_for_tied_position(self):
        other_position = Position.objects.create(title="Secretary", modified_by=self.admin_profile)
        contestant_a = Contestant.objects.create(
            name="John Roe", manifesto="Vote for stability.", position=other_position, election=self.election
        )
        contestant_b = Contestant.objects.create(
            name="Amina Bello", manifesto="Vote for change.", position=other_position, election=self.election
        )
        student1 = Student.objects.create(
            first_name="A", last_name="One", matric_number="2026/1/00001CF", level="300"
        )
        student2 = Student.objects.create(
            first_name="B", last_name="Two", matric_number="2026/1/00002CF", level="300"
        )
        Vote.objects.create(
            student=student1, election=self.election, position=other_position, contestant=contestant_a
        )
        Vote.objects.create(
            student=student2, election=self.election, position=other_position, contestant=contestant_b
        )
        response = self.client.get(reverse("admin_panel:election_results", args=[self.election.pk]))
        # setUp's "Jane Doe" (unopposed in "President") still wins — exactly
        # one "Winner" badge, even though this tied "Secretary" position has none.
        self.assertContains(response, "Winner", count=1)

    def test_results_view_shows_winner_badge_on_correct_contestant_in_contested_position(self):
        other_position = Position.objects.create(title="Secretary", modified_by=self.admin_profile)
        winner = Contestant.objects.create(
            name="John Roe", manifesto="Vote for stability.", position=other_position, election=self.election
        )
        loser = Contestant.objects.create(
            name="Amina Bello", manifesto="Vote for change.", position=other_position, election=self.election
        )
        student1 = Student.objects.create(
            first_name="A", last_name="One", matric_number="2026/1/00001CF", level="300"
        )
        student2 = Student.objects.create(
            first_name="B", last_name="Two", matric_number="2026/1/00002CF", level="300"
        )
        student3 = Student.objects.create(
            first_name="C", last_name="Three", matric_number="2026/1/00003CF", level="300"
        )
        Vote.objects.create(student=student1, election=self.election, position=other_position, contestant=winner)
        Vote.objects.create(student=student2, election=self.election, position=other_position, contestant=winner)
        Vote.objects.create(student=student3, election=self.election, position=other_position, contestant=loser)
        response = self.client.get(reverse("admin_panel:election_results", args=[self.election.pk]))
        content = response.content.decode()
        john_index = content.index("John Roe")
        winner_badge_index = content.index("Winner", john_index)
        amina_index = content.index("Amina Bello")
        self.assertLess(winner_badge_index, amina_index)
        self.assertNotIn("Winner", content[content.index("Amina Bello"):])

    def test_results_view_shows_public_results_link_when_published(self):
        self.election.is_results_published = True
        self.election.save()
        response = self.client.get(reverse("admin_panel:election_results", args=[self.election.pk]))
        self.assertContains(
            response, f'href="{reverse("voting:results_detail", args=[self.election.pk])}"'
        )

    def test_results_view_hides_public_results_link_when_not_published(self):
        response = self.client.get(reverse("admin_panel:election_results", args=[self.election.pk]))
        self.assertNotContains(response, "View Public Results")

    def test_results_view_tally_excludes_votes_from_a_different_election_even_if_contestant_was_reassigned(self):
        other_election = Election.objects.create(
            session="2025/2026",
            start_time="2025-11-01T09:00:00Z",
            close_time="2025-11-01T17:00:00Z",
            modified_by=self.admin_profile,
        )
        contestant = Contestant.objects.filter(election=self.election).get()
        student = Student.objects.create(
            first_name="John", last_name="Smith", matric_number="2022/1/90976CF", level="300"
        )
        Vote.objects.create(
            student=student, election=self.election, position=self.position, contestant=contestant
        )
        contestant.election = other_election
        contestant.save()
        response = self.client.get(reverse("admin_panel:election_results", args=[other_election.pk]))
        self.assertContains(response, "0 vote")


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


class AdminFormBackLinkTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username="admin_backlinks", password="pass12345")
        self.admin_profile = AdminProfile.objects.create(user=self.admin_user, is_admin=True)
        self.client.force_login(self.admin_user)

    def test_position_form_links_back_to_position_list(self):
        response = self.client.get(reverse("admin_panel:position_create"))
        self.assertContains(
            response,
            f'href="{reverse("admin_panel:position_list")}" class="text-brand-purple hover:underline block mb-4">&larr; Back to Positions',
        )

    def test_contestant_form_links_back_to_contestant_list(self):
        response = self.client.get(reverse("admin_panel:contestant_create"))
        self.assertContains(
            response,
            f'href="{reverse("admin_panel:contestant_list")}" class="text-brand-purple hover:underline block mb-4">&larr; Back to Contestants',
        )

    def test_executive_form_links_back_to_executive_list(self):
        response = self.client.get(reverse("admin_panel:executive_create"))
        self.assertContains(
            response,
            f'href="{reverse("admin_panel:executive_list")}" class="text-brand-purple hover:underline block mb-4">&larr; Back to Executives',
        )

    def test_election_form_links_back_to_election_list(self):
        response = self.client.get(reverse("admin_panel:election_create"))
        self.assertContains(
            response,
            f'href="{reverse("admin_panel:election_list")}" class="text-brand-purple hover:underline block mb-4">&larr; Back to Elections',
        )

    def test_election_results_links_back_to_election_list(self):
        election = Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            modified_by=self.admin_profile,
        )
        response = self.client.get(reverse("admin_panel:election_results", args=[election.pk]))
        self.assertContains(
            response,
            f'href="{reverse("admin_panel:election_list")}" class="text-brand-purple hover:underline block mb-4">&larr; Back to Elections',
        )


class ContestantListFilterTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username="admin_contestant_filter", password="pass12345")
        self.admin_profile = AdminProfile.objects.create(user=self.admin_user, is_admin=True)
        self.client.force_login(self.admin_user)
        self.election_a = Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            modified_by=self.admin_profile,
        )
        self.election_b = Election.objects.create(
            session="2025/2026",
            start_time="2025-11-01T09:00:00Z",
            close_time="2025-11-01T17:00:00Z",
            modified_by=self.admin_profile,
        )
        self.position_a = Position.objects.create(title="President", modified_by=self.admin_profile)
        self.position_b = Position.objects.create(title="Secretary", modified_by=self.admin_profile)
        self.contestant_1 = Contestant.objects.create(
            name="Jane Doe", manifesto="Vote for me.", position=self.position_a, election=self.election_a
        )
        self.contestant_2 = Contestant.objects.create(
            name="John Roe", manifesto="Vote for me.", position=self.position_b, election=self.election_a
        )
        self.contestant_3 = Contestant.objects.create(
            name="Amina Bello", manifesto="Vote for me.", position=self.position_a, election=self.election_b
        )

    def test_no_filter_returns_all_contestants(self):
        response = self.client.get(reverse("admin_panel:contestant_list"))
        self.assertEqual(len(response.context["contestants"]), 3)

    def test_filter_by_election_returns_only_that_elections_contestants(self):
        response = self.client.get(reverse("admin_panel:contestant_list"), {"election": self.election_a.pk})
        contestants = set(response.context["contestants"])
        self.assertEqual(contestants, {self.contestant_1, self.contestant_2})

    def test_filter_by_position_returns_only_that_positions_contestants(self):
        response = self.client.get(reverse("admin_panel:contestant_list"), {"position": self.position_a.pk})
        contestants = set(response.context["contestants"])
        self.assertEqual(contestants, {self.contestant_1, self.contestant_3})

    def test_filter_by_both_election_and_position_returns_intersection(self):
        response = self.client.get(
            reverse("admin_panel:contestant_list"),
            {"election": self.election_a.pk, "position": self.position_a.pk},
        )
        contestants = list(response.context["contestants"])
        self.assertEqual(contestants, [self.contestant_1])

    def test_malformed_filter_value_is_ignored_instead_of_crashing(self):
        response = self.client.get(reverse("admin_panel:contestant_list"), {"election": "not-a-number"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["contestants"]), 3)

    def test_unicode_digit_filter_value_is_ignored_instead_of_crashing(self):
        # '²' (superscript two) passes str.isdigit() but int('²') raises
        # ValueError — a naive isdigit() guard wouldn't catch this.
        response = self.client.get(reverse("admin_panel:contestant_list"), {"election": "²"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["contestants"]), 3)

    def test_election_list_links_to_filtered_contestants(self):
        response = self.client.get(reverse("admin_panel:election_list"))
        expected_url = reverse("admin_panel:contestant_list") + f"?election={self.election_a.pk}"
        self.assertContains(response, f'href="{expected_url}"')

    def test_position_list_links_to_filtered_contestants(self):
        response = self.client.get(reverse("admin_panel:position_list"))
        expected_url = reverse("admin_panel:contestant_list") + f"?position={self.position_a.pk}"
        self.assertContains(response, f'href="{expected_url}"')


class AdminNavTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username="admin_nav", password="pass12345")
        AdminProfile.objects.create(user=self.admin_user, is_admin=True)
        self.client.force_login(self.admin_user)

    def test_nav_includes_public_site_link(self):
        response = self.client.get(reverse("admin_panel:dashboard"))
        self.assertContains(response, f'href="{reverse("core:home")}" class="hover:text-brand-purple">Public Site')
