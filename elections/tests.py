from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.db.models import Count, ProtectedError
from django.test import TestCase

from admin_panel.models import AdminProfile
from .models import Position, Election, Contestant
from voting.models import Student, Vote

from .results import mark_winners


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


class ContestantModelTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="admin3", password="pass12345")
        admin_profile = AdminProfile.objects.create(user=user, is_admin=True)
        self.position = Position.objects.create(title="President", modified_by=admin_profile)
        self.election = Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            modified_by=admin_profile,
        )

    def test_string_representation(self):
        contestant = Contestant.objects.create(
            name="Jane Doe",
            alias="JD",
            manifesto="Vote for progress.",
            position=self.position,
            election=self.election,
        )
        self.assertEqual(str(contestant), "Jane Doe (President)")

    def test_save_without_position_raises_integrity_error(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Contestant.objects.create(
                    name="Jane Doe",
                    manifesto="Vote for progress.",
                    election=self.election,
                )

    def test_save_without_election_raises_integrity_error(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Contestant.objects.create(
                    name="Jane Doe",
                    manifesto="Vote for progress.",
                    position=self.position,
                )


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

    def test_deleting_admin_profile_with_election_is_protected(self):
        Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            modified_by=self.admin_profile,
        )
        with self.assertRaises(ProtectedError):
            self.admin_profile.delete()


class MarkWinnersTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="admin_markwinners", password="pass12345")
        self.admin_profile = AdminProfile.objects.create(user=user, is_admin=True)
        self.election = Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            status="ended",
            modified_by=self.admin_profile,
        )

    def _tallies(self):
        return (
            Contestant.objects.filter(election=self.election)
            .select_related("position")
            .annotate(vote_count=Count("votes"))
            .order_by("position__title", "position_id", "-vote_count")
        )

    def test_unopposed_contestant_wins_regardless_of_vote_count(self):
        position = Position.objects.create(title="President", modified_by=self.admin_profile)
        Contestant.objects.create(
            name="Jane Doe", manifesto="Vote for me.", position=position, election=self.election
        )
        tallies = mark_winners(self._tallies())
        self.assertTrue(tallies[0].is_winner)

    def test_contestant_with_strictly_more_votes_wins(self):
        position = Position.objects.create(title="President", modified_by=self.admin_profile)
        winner = Contestant.objects.create(
            name="Jane Doe", manifesto="Vote for me.", position=position, election=self.election
        )
        loser = Contestant.objects.create(
            name="John Roe", manifesto="Vote for me too.", position=position, election=self.election
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
        Vote.objects.create(student=student1, election=self.election, position=position, contestant=winner)
        Vote.objects.create(student=student2, election=self.election, position=position, contestant=winner)
        Vote.objects.create(student=student3, election=self.election, position=position, contestant=loser)
        tallies = mark_winners(self._tallies())
        self.assertTrue(tallies[0].is_winner)
        self.assertFalse(tallies[1].is_winner)

    def test_exact_tie_marks_no_winner(self):
        position = Position.objects.create(title="President", modified_by=self.admin_profile)
        contestant_a = Contestant.objects.create(
            name="Jane Doe", manifesto="Vote for me.", position=position, election=self.election
        )
        contestant_b = Contestant.objects.create(
            name="John Roe", manifesto="Vote for me too.", position=position, election=self.election
        )
        student1 = Student.objects.create(
            first_name="A", last_name="One", matric_number="2026/1/00001CF", level="300"
        )
        student2 = Student.objects.create(
            first_name="B", last_name="Two", matric_number="2026/1/00002CF", level="300"
        )
        Vote.objects.create(student=student1, election=self.election, position=position, contestant=contestant_a)
        Vote.objects.create(student=student2, election=self.election, position=position, contestant=contestant_b)
        tallies = mark_winners(self._tallies())
        self.assertFalse(tallies[0].is_winner)
        self.assertFalse(tallies[1].is_winner)

    def test_multiple_positions_evaluated_independently(self):
        position_a = Position.objects.create(title="President", modified_by=self.admin_profile)
        position_b = Position.objects.create(title="Secretary", modified_by=self.admin_profile)
        contestant_a = Contestant.objects.create(
            name="Jane Doe", manifesto="Vote for me.", position=position_a, election=self.election
        )
        contestant_b1 = Contestant.objects.create(
            name="John Roe", manifesto="Vote for me.", position=position_b, election=self.election
        )
        contestant_b2 = Contestant.objects.create(
            name="Amina Bello", manifesto="Vote for me too.", position=position_b, election=self.election
        )
        student1 = Student.objects.create(
            first_name="A", last_name="One", matric_number="2026/1/00001CF", level="300"
        )
        Vote.objects.create(student=student1, election=self.election, position=position_b, contestant=contestant_b1)
        tallies = mark_winners(self._tallies())
        by_id = {t.pk: t for t in tallies}
        self.assertTrue(by_id[contestant_a.pk].is_winner)
        self.assertTrue(by_id[contestant_b1.pk].is_winner)
        self.assertFalse(by_id[contestant_b2.pk].is_winner)
