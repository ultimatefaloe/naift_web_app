from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

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

    def test_duplicate_vote_with_different_contestant_still_raises_integrity_error(self):
        other_contestant = Contestant.objects.create(
            name="John Roe", manifesto="Vote for stability.", position=self.position, election=self.election
        )
        Vote.objects.create(
            student=self.student, election=self.election, position=self.position, contestant=self.contestant
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Vote.objects.create(
                    student=self.student,
                    election=self.election,
                    position=self.position,
                    contestant=other_contestant,
                )

    def test_same_student_can_vote_for_a_different_position_in_same_election(self):
        other_position = Position.objects.create(title="Vice President", modified_by=self.contestant.position.modified_by)
        other_contestant = Contestant.objects.create(
            name="John Roe", manifesto="Vote for stability.", position=other_position, election=self.election
        )
        Vote.objects.create(
            student=self.student, election=self.election, position=self.position, contestant=self.contestant
        )
        Vote.objects.create(
            student=self.student, election=self.election, position=other_position, contestant=other_contestant
        )
        self.assertEqual(Vote.objects.filter(student=self.student).count(), 2)

    def test_different_student_can_vote_for_same_election_and_position(self):
        other_student = Student.objects.create(
            first_name="Alice", last_name="Jones", matric_number="2022/2/55555CF", level="200"
        )
        Vote.objects.create(
            student=self.student, election=self.election, position=self.position, contestant=self.contestant
        )
        Vote.objects.create(
            student=other_student, election=self.election, position=self.position, contestant=self.contestant
        )
        self.assertEqual(Vote.objects.filter(position=self.position, election=self.election).count(), 2)


class LoginViewTests(TestCase):
    def setUp(self):
        self.student = Student.objects.create(
            first_name="Jane", last_name="Doe", matric_number="2022/1/90976CF", level="300"
        )

    def test_valid_credentials_log_student_in(self):
        response = self.client.post(
            reverse("voting:login"),
            {"first_name": "Jane", "matric_number": "2022/1/90976CF"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session["student_id"], self.student.id)

    def test_invalid_credentials_show_error(self):
        response = self.client.post(
            reverse("voting:login"),
            {"first_name": "Jane", "matric_number": "0000/0/00000CF"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No matching student record found.")


class LogoutViewTests(TestCase):
    def setUp(self):
        self.student = Student.objects.create(
            first_name="Jane", last_name="Doe", matric_number="2022/1/90976CF", level="300"
        )

    def test_logout_clears_session(self):
        session = self.client.session
        session["student_id"] = self.student.id
        session.save()
        response = self.client.post(reverse("voting:logout"))
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("student_id", self.client.session)

    def test_logout_rejects_get(self):
        session = self.client.session
        session["student_id"] = self.student.id
        session.save()
        response = self.client.get(reverse("voting:logout"))
        self.assertEqual(response.status_code, 405)


class VoteEntryAccessTests(TestCase):
    def test_unauthenticated_redirected_to_login(self):
        response = self.client.get(reverse("voting:vote_entry"))
        self.assertRedirects(response, reverse("voting:login"))


class VoteEntryTests(TestCase):
    def setUp(self):
        self.student = Student.objects.create(
            first_name="Jane", last_name="Doe", matric_number="2022/1/90976CF", level="300"
        )
        session = self.client.session
        session["student_id"] = self.student.id
        session.save()
        user = User.objects.create_user(username="admin_voting2", password="pass12345")
        self.admin_profile = AdminProfile.objects.create(user=user, is_admin=True)

    def test_no_ongoing_election_shows_no_election_page(self):
        response = self.client.get(reverse("voting:vote_entry"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "voting/no_election.html")

    def test_already_voted_shows_voted_page(self):
        position = Position.objects.create(title="President", modified_by=self.admin_profile)
        election = Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            status="ongoing",
            modified_by=self.admin_profile,
        )
        contestant = Contestant.objects.create(
            name="Jane Doe", manifesto="Vote for progress.", position=position, election=election
        )
        Vote.objects.create(student=self.student, election=election, position=position, contestant=contestant)
        response = self.client.get(reverse("voting:vote_entry"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "voting/voted.html")

    def test_eligible_student_redirected_to_first_wizard_step(self):
        position = Position.objects.create(title="President", modified_by=self.admin_profile)
        election = Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            status="ongoing",
            modified_by=self.admin_profile,
        )
        Contestant.objects.create(
            name="Jane Doe", manifesto="Vote for progress.", position=position, election=election
        )
        response = self.client.get(reverse("voting:vote_entry"))
        self.assertRedirects(response, reverse("voting:wizard_step", args=[position.pk]))


class WizardStepTests(TestCase):
    def setUp(self):
        self.student = Student.objects.create(
            first_name="Jane", last_name="Doe", matric_number="2022/1/90976CF", level="300"
        )
        session = self.client.session
        session["student_id"] = self.student.id
        session.save()
        user = User.objects.create_user(username="admin_voting3", password="pass12345")
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

    def test_get_shows_contestants(self):
        response = self.client.get(reverse("voting:wizard_step", args=[self.position.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "voting/wizard_step.html")
        self.assertContains(response, "Jane Doe")

    def test_post_stores_pick_in_session_not_database(self):
        response = self.client.post(
            reverse("voting:wizard_step", args=[self.position.pk]), {"contestant": self.contestant.pk}
        )
        self.assertRedirects(response, reverse("voting:vote_entry"), fetch_redirect_response=False)
        self.assertEqual(self.client.session["vote_picks"], {str(self.position.pk): self.contestant.pk})
        self.assertEqual(Vote.objects.count(), 0)

    def test_post_rejects_contestant_from_different_position(self):
        other_position = Position.objects.create(title="Vice President", modified_by=self.position.modified_by)
        other_contestant = Contestant.objects.create(
            name="John Roe", manifesto="Vote for stability.", position=other_position, election=self.election
        )
        response = self.client.post(
            reverse("voting:wizard_step", args=[self.position.pk]), {"contestant": other_contestant.pk}
        )
        self.assertEqual(response.status_code, 404)
        self.assertNotIn("vote_picks", self.client.session)

    def test_post_rejects_malformed_contestant_value(self):
        response = self.client.post(
            reverse("voting:wizard_step", args=[self.position.pk]), {"contestant": "not-a-number"}
        )
        self.assertEqual(response.status_code, 404)


class ResultsViewTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="admin_voting5", password="pass12345")
        self.admin_profile = AdminProfile.objects.create(user=user, is_admin=True)
        self.position = Position.objects.create(title="President", modified_by=self.admin_profile)
        self.election = Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            status="ended",
            is_results_published=True,
            modified_by=self.admin_profile,
        )
        self.contestant = Contestant.objects.create(
            name="Jane Doe", manifesto="Vote for progress.", position=self.position, election=self.election
        )
        student = Student.objects.create(
            first_name="John", last_name="Smith", matric_number="2022/1/90976CF", level="300"
        )
        Vote.objects.create(
            student=student, election=self.election, position=self.position, contestant=self.contestant
        )

    def test_results_not_published_shows_fallback_page(self):
        self.election.is_results_published = False
        self.election.save()
        response = self.client.get(reverse("voting:results"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "voting/results_not_published.html")

    def test_results_shows_vote_tally(self):
        response = self.client.get(reverse("voting:results"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Jane Doe")
        self.assertContains(response, "1 vote")

    def test_results_no_login_required(self):
        response = self.client.get(reverse("voting:results"))
        self.assertEqual(response.status_code, 200)

    def test_results_groups_tallies_correctly_with_duplicate_position_titles(self):
        other_position = Position.objects.create(title="President", modified_by=self.admin_profile)
        other_contestant = Contestant.objects.create(
            name="Alice Smith", manifesto="Vote for change.", position=other_position, election=self.election
        )
        other_student = Student.objects.create(
            first_name="Bob", last_name="Jones", matric_number="2022/2/11111CF", level="200"
        )
        Vote.objects.create(
            student=other_student,
            election=self.election,
            position=other_position,
            contestant=other_contestant,
        )
        response = self.client.get(reverse("voting:results"))
        self.assertContains(response, "Jane Doe")
        self.assertContains(response, "Alice Smith")

    def test_results_shows_zero_vote_contestant(self):
        Contestant.objects.create(
            name="No Votes Yet", manifesto="Vote for me.", position=self.position, election=self.election
        )
        response = self.client.get(reverse("voting:results"))
        self.assertContains(response, "No Votes Yet")
        self.assertContains(response, "0 vote")


class WizardReviewTests(TestCase):
    def setUp(self):
        self.student = Student.objects.create(
            first_name="Jane", last_name="Doe", matric_number="2022/1/90976CF", level="300"
        )
        session = self.client.session
        session["student_id"] = self.student.id
        session.save()
        user = User.objects.create_user(username="admin_voting4", password="pass12345")
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
        session = self.client.session
        session["vote_picks"] = {str(self.position.pk): self.contestant.pk}
        session.save()

    def test_get_shows_selections(self):
        response = self.client.get(reverse("voting:wizard_review"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Jane Doe")

    def test_post_submits_votes_atomically_and_clears_session(self):
        response = self.client.post(reverse("voting:wizard_review"))
        self.assertRedirects(response, reverse("voting:vote_entry"))
        self.assertEqual(Vote.objects.count(), 1)
        vote = Vote.objects.get()
        self.assertEqual(vote.student, self.student)
        self.assertEqual(vote.contestant, self.contestant)
        self.assertNotIn("vote_picks", self.client.session)

    def test_post_then_vote_entry_shows_voted_page(self):
        self.client.post(reverse("voting:wizard_review"))
        response = self.client.get(reverse("voting:vote_entry"))
        self.assertTemplateUsed(response, "voting/voted.html")

    def test_post_with_incomplete_picks_does_not_create_votes_and_redirects_away(self):
        other_position = Position.objects.create(
            title="Vice President", modified_by=self.position.modified_by
        )
        Contestant.objects.create(
            name="John Roe", manifesto="Vote for stability.", position=other_position, election=self.election
        )
        # setUp's session only has a pick for self.position, not other_position — incomplete.
        response = self.client.post(reverse("voting:wizard_review"))
        # vote_entry itself redirects onward to wizard_step for the still-unpicked position,
        # so the fetched target is a second 302, not a 200 render.
        self.assertRedirects(response, reverse("voting:vote_entry"), target_status_code=302)
        self.assertEqual(Vote.objects.count(), 0)

    def test_post_rejects_pick_from_a_different_election(self):
        other_election = Election.objects.create(
            session="2025/2026",
            start_time="2025-11-01T09:00:00Z",
            close_time="2025-11-01T17:00:00Z",
            status="ended",
            modified_by=self.position.modified_by,
        )
        stale_contestant = Contestant.objects.create(
            name="Old Candidate", manifesto="Vote for me.", position=self.position, election=other_election
        )
        session = self.client.session
        session["vote_picks"] = {str(self.position.pk): stale_contestant.pk}
        session.save()
        response = self.client.get(reverse("voting:wizard_review"))
        self.assertEqual(response.status_code, 404)


class ResultsArchiveTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="admin_voting6", password="pass12345")
        admin_profile = AdminProfile.objects.create(user=user, is_admin=True)
        self.published = Election.objects.create(
            session="2025/2026",
            start_time="2025-11-01T09:00:00Z",
            close_time="2025-11-01T17:00:00Z",
            status="ended",
            is_results_published=True,
            modified_by=admin_profile,
        )
        self.unpublished = Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            status="ended",
            is_results_published=False,
            modified_by=admin_profile,
        )

    def test_archive_lists_only_published_elections(self):
        response = self.client.get(reverse("voting:results_archive"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "2025/2026")
        self.assertNotContains(response, "2026/2027")

    def test_archive_orders_multiple_published_elections_most_recent_first(self):
        newer = Election.objects.create(
            session="2027/2028",
            start_time="2027-11-01T09:00:00Z",
            close_time="2027-11-01T17:00:00Z",
            status="ended",
            is_results_published=True,
            modified_by=self.published.modified_by,
        )
        response = self.client.get(reverse("voting:results_archive"))
        content = response.content.decode()
        self.assertLess(content.index("2027/2028"), content.index("2025/2026"))

    def test_archive_shows_empty_state_when_no_published_elections(self):
        self.published.is_results_published = False
        self.published.save()
        self.unpublished.is_results_published = False
        self.unpublished.save()
        response = self.client.get(reverse("voting:results_archive"))
        self.assertContains(response, "No published election results yet.")
