# Vote Integrity, Election-Status Visibility & Student Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix a vote-carryover data-integrity bug, make the voting link and results page react to live election status, replace the three native `confirm()` dialogs with a styled modal, and add a full Student management page (CRUD + CSV bulk create-or-update).

**Architecture:** Four independent pieces sharing one spec: (1) a `filter=Q(votes__election=F("election"))` fix to every vote-tally query plus removing `election` from `ContestantUpdateView`'s editable fields; (2) a new Django context processor (`elections.context_processors.election_status`) registered once in `settings.py`, exposing `voting_is_open` to every template app-wide, driving conditional rendering in `core`/`voting` templates; (3) a native `<dialog>`-based confirm modal replacing the three inline `confirm()` calls in `election_list.html`; (4) a new `admin_panel` CRUD section for `Student`, with CSV import logic extracted into a shared `voting/csv_import.py` module used by both the existing `seed_students` CLI command and the new web upload view.

**Tech Stack:** Django 6.1 views/templates/context-processors, native HTML `<dialog>` + vanilla JS (no new library), Django's built-in `Paginator`.

---

## Context for the implementer

- Repo: `/home/ultimate/Desktop/UltimateIntelliForge.org/naift_web_app`, branch `dev` (already checked out — continue on it).
- Spec: `docs/superpowers/specs/2026-11-03-vote-integrity-visibility-student-crud-design.md` (read it before starting).
- Postgres runs via docker-compose. Verify with `docker ps` first; if the daemon isn't reachable, run `systemctl --user start docker-desktop` then `docker compose up -d db`, and poll `docker ps` until the db container shows `(healthy)`.
- Full test suite currently has **144 passing tests** (core=8, executives=6, elections=16, admin_panel=60, voting=54) — verified by actually running `.venv/bin/python manage.py test` immediately before writing this plan.
- `admin_panel/views.py` currently imports: `from django.db.models import Count`, `from elections.models import Contestant, Election, Position`, `from elections.results import mark_winners`, `from executives.models import Executive`. It does NOT yet import `Student`, `Vote`, `ProtectedError`, `F`, `Q`, or `csv` — these get added across this plan's tasks, each task adding only what it needs.
- `voting/views.py` currently imports `from django.db.models import Count` — needs `F`, `Q` added in Task 1.
- `admin_panel/tests.py` already imports `User`, `SimpleUploadedFile`, `TestCase`, `override_settings`, `reverse`, `Contestant`, `Election`, `Position`, `Executive`, `Student`, `Vote`, `AdminProfile` — no new imports needed there for any task in this plan.
- `voting/tests.py` already imports `os`, `tempfile`, `StringIO`, `User`, `ValidationError`, `CommandError`, `call_command`, `IntegrityError`, `transaction`, `TestCase`, `reverse`, `AdminProfile`, `Contestant`, `Election`, `Position`, `Student`, `Vote`.
- `core/tests.py` already imports `User`, `TestCase`, `reverse`, `AdminProfile`, `Election`.
- Out of scope: any change to Position/Election/Executive CRUD, pagination for any other list view, the `Election.STATUS_*` enum itself, a "Clear filter" UI for the Contestant list.

---

### Task 1: Vote-carryover fix

**Files:**
- Modify: `voting/views.py` (the `results_view` function's tally query)
- Modify: `admin_panel/views.py` (`ElectionResultsView`'s tally query, `DashboardView`'s chart tally query, `ContestantUpdateView.fields`)
- Test: `voting/tests.py` (add to `ResultsViewTests`), `admin_panel/tests.py` (add to `ElectionResultsViewTests`, `DashboardStatisticsTests`, `ContestantCRUDTests`)

- [ ] **Step 1: Write the failing tests**

Add to `ResultsViewTests` in `voting/tests.py` (after `test_results_shows_winner_badge_on_correct_contestant_in_contested_position`):

```python
    def test_results_tally_excludes_votes_from_a_different_election_even_if_contestant_was_reassigned(self):
        # Simulates a Contestant whose `election` was changed after votes were
        # already cast under its original election — the tally must only
        # count votes that belong to the contestant's CURRENT election, not
        # every vote it has ever received.
        other_election = Election.objects.create(
            session="2025/2026",
            start_time="2025-11-01T09:00:00Z",
            close_time="2025-11-01T17:00:00Z",
            status="ended",
            is_results_published=True,
            modified_by=self.admin_profile,
        )
        self.contestant.election = other_election
        self.contestant.save()
        response = self.client.get(reverse("voting:results_detail", args=[other_election.pk]))
        self.assertContains(response, "0 vote")
```

Add to `ElectionResultsViewTests` in `admin_panel/tests.py` (after `test_results_view_shows_public_results_link_when_published` — or wherever that class's last test currently is):

```python
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
```

Add to `DashboardStatisticsTests` in `admin_panel/tests.py` (after its last existing test):

```python
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
```

Add to `ContestantCRUDTests` in `admin_panel/tests.py` (after its last existing test):

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
.venv/bin/python manage.py test voting.tests.ResultsViewTests admin_panel.tests.ElectionResultsViewTests admin_panel.tests.DashboardStatisticsTests admin_panel.tests.ContestantCRUDTests -v 2
```

Expected: the 4 new tests FAIL. The reassignment tests fail because `vote_count`/the chart's votes list currently show `1`/`[1]` instead of `0`/`[0]` (the carryover bug). The `election`-ignored test fails because the current form DOES accept and apply the posted `election` value.

- [ ] **Step 3: Fix the tally queries**

In `voting/views.py`, add `F, Q` to the existing import line:

```python
from django.db.models import Count, F, Q
```

Then update `results_view`'s tally annotation (only the `.annotate(...)` line changes):

```python
    tallies = mark_winners(
        Contestant.objects.filter(election=election)
        .select_related("position")
        .annotate(vote_count=Count("votes", filter=Q(votes__election=F("election"))))
        .order_by("position__title", "position_id", "-vote_count")
    )
```

In `admin_panel/views.py`, add `F, Q` to the existing import line:

```python
from django.db.models import Count, F, Q
```

Then update `ElectionResultsView.get_context_data`'s tally annotation (only the `.annotate(...)` line changes):

```python
        context["tallies"] = mark_winners(
            Contestant.objects.filter(election=self.object)
            .select_related("position")
            .annotate(vote_count=Count("votes", filter=Q(votes__election=F("election"))))
            .order_by("position__title", "position_id", "-vote_count")
        )
```

And `DashboardView.get_context_data`'s chart tally annotation (only the `.annotate(...)` line changes):

```python
            tallies = (
                Contestant.objects.filter(election=ongoing_election)
                .select_related("position")
                .annotate(vote_count=Count("votes", filter=Q(votes__election=F("election"))))
                .order_by("position__title", "position_id", "-vote_count")
            )
```

- [ ] **Step 4: Remove `election` from `ContestantUpdateView`'s editable fields**

In `admin_panel/views.py`, change:

```python
class ContestantUpdateView(AdminRequiredMixin, UpdateView):
    model = Contestant
    fields = ["name", "alias", "manifesto", "position", "election", "photo"]
    template_name = "admin_panel/contestant_form.html"
    success_url = reverse_lazy("admin_panel:contestant_list")
```

to:

```python
class ContestantUpdateView(AdminRequiredMixin, UpdateView):
    model = Contestant
    fields = ["name", "alias", "manifesto", "position", "photo"]
    template_name = "admin_panel/contestant_form.html"
    success_url = reverse_lazy("admin_panel:contestant_list")
```

(`ContestantCreateView` is untouched — `election` remains settable at creation, which is the correct, only time it should ever be set.)

- [ ] **Step 5: Run the tests to verify they pass**

```bash
.venv/bin/python manage.py test voting admin_panel -v 2
```

Expected: `OK` for both apps. `voting` = 55 tests (54 + 1 new). `admin_panel` = 63 tests (60 + 3 new).

- [ ] **Step 6: Commit**

```bash
git add voting/views.py admin_panel/views.py voting/tests.py admin_panel/tests.py
git commit -m "Fix vote-carryover bug: scope tally counts to the contestant's current election"
```

---

### Task 2: Election-status context processor

**Files:**
- Create: `elections/context_processors.py`
- Modify: `web/settings.py` (register the new context processor)
- Test: `elections/tests.py` (new class `ElectionStatusContextProcessorTests`, appended at the end of the file)

- [ ] **Step 1: Write the failing tests**

Append to `elections/tests.py`:

```python
from .context_processors import election_status


class ElectionStatusContextProcessorTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="admin_election_status", password="pass12345")
        self.admin_profile = AdminProfile.objects.create(user=user, is_admin=True)

    def test_false_when_no_elections_exist(self):
        self.assertFalse(election_status(None)["voting_is_open"])

    def test_false_when_only_upcoming_election_exists(self):
        Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            status="upcoming",
            modified_by=self.admin_profile,
        )
        self.assertFalse(election_status(None)["voting_is_open"])

    def test_false_when_only_ended_election_exists(self):
        Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            status="ended",
            modified_by=self.admin_profile,
        )
        self.assertFalse(election_status(None)["voting_is_open"])

    def test_true_when_ongoing_election_exists(self):
        Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            status="ongoing",
            modified_by=self.admin_profile,
        )
        self.assertTrue(election_status(None)["voting_is_open"])
```

(Note: `election_status` doesn't actually use its `request` argument — it's required by Django's context-processor calling convention, but passing `None` directly in these unit tests is fine and avoids needing a real `HttpRequest`.)

- [ ] **Step 2: Run the tests to verify they fail**

```bash
.venv/bin/python manage.py test elections.tests.ElectionStatusContextProcessorTests -v 2
```

Expected: `ModuleNotFoundError` / `ImportError` — `elections/context_processors.py` doesn't exist yet.

- [ ] **Step 3: Create the context processor**

```python
from .models import Election


def election_status(request):
    return {
        "voting_is_open": Election.objects.filter(status=Election.STATUS_ONGOING).exists(),
    }
```

- [ ] **Step 4: Register it in settings**

In `web/settings.py`, find the `TEMPLATES` setting's `context_processors` list:

```python
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
```

Add the new processor as a 4th entry:

```python
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'elections.context_processors.election_status',
            ],
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
.venv/bin/python manage.py test elections -v 2
```

Expected: `OK`, 20 tests (the pre-existing 16, plus these 4 new tests).

- [ ] **Step 6: Commit**

```bash
git add elections/context_processors.py web/settings.py elections/tests.py
git commit -m "Add election_status context processor exposing voting_is_open app-wide"
```

---

### Task 3: Public site visibility (voting link tied to election status)

**Files:**
- Modify: `core/templates/core/base.html` (desktop nav "Vote" link, mobile drawer "Vote Now" footer button)
- Modify: `core/templates/core/home.html` (hero "Vote Now" button, aside "Cast your vote" card)
- Test: `core/tests.py` (new class `HomeVotingVisibilityTests`, appended at the end of the file)

- [ ] **Step 1: Write the failing tests**

Append to `core/tests.py`:

```python
class HomeVotingVisibilityTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="admin_voting_visibility", password="pass12345")
        self.admin_profile = AdminProfile.objects.create(user=user, is_admin=True)

    def test_vote_now_hero_button_hidden_when_no_ongoing_election(self):
        response = self.client.get(reverse("core:home"))
        self.assertNotContains(response, 'href="{}" class="btn btn-primary">Vote Now'.format(reverse("voting:login")))

    def test_vote_now_hero_button_shown_when_election_is_ongoing(self):
        Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            status="ongoing",
            modified_by=self.admin_profile,
        )
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, 'href="{}" class="btn btn-primary">Vote Now'.format(reverse("voting:login")))

    def test_nav_vote_link_hidden_when_no_ongoing_election(self):
        response = self.client.get(reverse("core:home"))
        self.assertNotContains(response, "cta-bounce")

    def test_nav_vote_link_shown_when_election_is_ongoing(self):
        Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            status="ongoing",
            modified_by=self.admin_profile,
        )
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, "cta-bounce")
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
.venv/bin/python manage.py test core.tests.HomeVotingVisibilityTests -v 2
```

Expected: the two "shown when ongoing" tests pass already (the links are currently unconditional, so they're always present) — that's fine, they lock in the positive case. The two "hidden when no ongoing election" tests FAIL, since nothing is conditional yet.

- [ ] **Step 3: Gate the desktop nav "Vote" link**

In `core/templates/core/base.html`, wrap the existing Vote link inside the desktop `<nav>`:

```html
                {% if voting_is_open %}
                <a href="{% url 'voting:login' %}"
                   class="cta-bounce ml-2 inline-flex items-center gap-1.5 bg-brand-purple px-4 py-2
                          text-sm font-semibold text-white transition-colors hover:bg-brand-purple-dark">
                    Vote <span aria-hidden="true">→</span>
                </a>
                {% endif %}
```

- [ ] **Step 4: Gate the mobile drawer's "Vote Now" footer button**

In the same file, find the mobile drawer's `<footer>` block (containing the standalone "Vote Now" link, near the bottom of the drawer markup) and wrap it:

```html
            {% if voting_is_open %}
            <footer class="border-t border-neutral-200 p-3">
                <a href="{% url 'voting:login' %}" class="btn btn-primary btn-block">
                    Vote Now <span aria-hidden="true">→</span>
                </a>
            </footer>
            {% endif %}
```

- [ ] **Step 5: Gate the homepage hero "Vote Now" button**

In `core/templates/core/home.html`, wrap only the "Vote Now" link (leave "Meet the Executive" untouched):

```html
        <div class="mt-10 flex flex-wrap gap-3">
            {% if voting_is_open %}
            <a href="{% url 'voting:login' %}" class="btn btn-primary">Vote Now</a>
            {% endif %}
            <a href="{% url 'executives:current' %}"
               class="inline-flex items-center gap-2 border border-white/40 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-white hover:text-brand-black">
                Meet the Executive →
            </a>
        </div>
```

- [ ] **Step 6: Gate the "Cast your vote" aside card**

In the same file, wrap only that one `<a>` card (leave "Results" and "Current executive" cards untouched):

```html
        <aside class="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
            {% if voting_is_open %}
            <a href="{% url 'voting:login' %}" class="card group block p-5 transition-shadow hover:shadow-hard">
                <p class="text-xs font-semibold uppercase tracking-wider text-brand-purple">Cast your vote</p>
                <p class="mt-2 font-display text-lg font-semibold text-brand-black group-hover:text-brand-purple">
                    Student login →
                </p>
            </a>
            {% endif %}
            <a href="{% url 'voting:results' %}" class="card group block p-5 transition-shadow hover:shadow-hard">
```

- [ ] **Step 7: Run the full `core` app test suite**

```bash
.venv/bin/python manage.py test core -v 2
```

Expected: `OK`, 12 tests (the pre-existing 8, plus these 4 new tests).

- [ ] **Step 8: Commit**

```bash
git add core/templates/core/base.html core/templates/core/home.html core/tests.py
git commit -m "Hide public-site voting CTAs when no election is currently ongoing"
```

---

### Task 4: Student-dashboard visibility and results-page election-awareness

**Files:**
- Modify: `voting/templates/voting/base.html` (desktop nav + mobile drawer "Vote" link)
- Modify: `voting/templates/voting/results_not_published.html`
- Test: `voting/tests.py` (replace one test in `VotingNavTests`, add to `ResultsViewTests`)

- [ ] **Step 1: Write the failing/replacement tests**

In `voting/tests.py`'s `VotingNavTests` class, **replace** the existing `test_nav_includes_vote_link` test (its premise — that the login page always shows a Vote link — is about to become false once the link is conditional) with these two:

```python
    def test_nav_hides_vote_link_when_no_ongoing_election(self):
        response = self.client.get(reverse("voting:login"))
        self.assertNotContains(response, f'href="{reverse("voting:vote_entry")}"')

    def test_nav_shows_vote_link_when_election_is_ongoing(self):
        user = User.objects.create_user(username="admin_voting_nav_ongoing", password="pass12345")
        admin_profile = AdminProfile.objects.create(user=user, is_admin=True)
        Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            status="ongoing",
            modified_by=admin_profile,
        )
        response = self.client.get(reverse("voting:login"))
        self.assertContains(response, f'href="{reverse("voting:vote_entry")}"')
```

(Leave `test_nav_includes_results_link`, `test_nav_includes_past_results_link`, `test_nav_includes_public_site_link` in the same class untouched — those links aren't becoming conditional.)

Add to the existing `ResultsViewTests` class (after `test_results_not_published_shows_fallback_page`):

```python
    def test_results_not_published_shows_ongoing_message_when_election_is_open(self):
        self.election.is_results_published = False
        self.election.status = "ongoing"
        self.election.save()
        response = self.client.get(reverse("voting:results"))
        self.assertContains(response, "An Election Is Currently Open")
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
.venv/bin/python manage.py test voting.tests.VotingNavTests voting.tests.ResultsViewTests -v 2
```

Expected: `test_nav_hides_vote_link_when_no_ongoing_election` FAILS (the link is currently unconditional, so it's present). `test_nav_shows_vote_link_when_election_is_ongoing` PASSES already (link is currently always present — that's fine, it locks in the positive case). `test_results_not_published_shows_ongoing_message_when_election_is_open` FAILS (no such message exists in the template yet).

- [ ] **Step 3: Gate the Vote link in `voting/base.html`**

In the desktop `<nav>`, wrap the existing Vote link:

```html
                {% if voting_is_open %}
                <a href="{% url 'voting:vote_entry' %}" class="nav-link"
                   {% if current == 'vote_entry' or current == 'wizard_step' or current == 'wizard_review' or current == 'voted' or current == 'no_election' %}aria-current="page"{% endif %}>Vote</a>
                {% endif %}
```

In the mobile drawer's `<ul>`, wrap the corresponding `<li>` (the one containing the "Vote" link — the first `<li>` in that list):

```html
                    {% if voting_is_open %}
                    <li>
                        <a href="{% url 'voting:vote_entry' %}"
                           class="flex items-center justify-between px-3 py-3 text-sm font-medium
                                  {% if current == 'vote_entry' or current == 'wizard_step' or current == 'wizard_review' or current == 'voted' or current == 'no_election' %}
                                      bg-brand-purple-soft text-brand-purple
                                  {% else %}
                                      text-neutral-700 hover:bg-neutral-100
                                  {% endif %}">
                            Vote <span aria-hidden="true">→</span>
                        </a>
                    </li>
                    {% endif %}
```

- [ ] **Step 4: Add the ongoing-election message to `results_not_published.html`**

Replace the contents of `voting/templates/voting/results_not_published.html` with:

```html
{% extends "voting/base.html" %}

{% block title %}Results Not Published · NAIFT Voting{% endblock %}

{% block content %}
<div class="mx-auto py-16 text-center">

    <div class="mx-auto mb-6 grid h-16 w-16 place-items-center bg-warning-soft text-warning">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="h-8 w-8">
            <rect x="5" y="11" width="14" height="10"/>
            <path d="M8 11V7a4 4 0 018 0v4"/>
        </svg>
    </div>

    {% if voting_is_open %}
        <h1 class="mb-3 font-display text-3xl font-semibold text-brand-black">An Election Is Currently Open</h1>
        <p class="text-base text-neutral-600">
            Voting is in progress. Results will be available once the election ends and are published.
        </p>
        <div class="mt-8 flex justify-center gap-3">
            <a href="{% url 'voting:login' %}" class="btn btn-primary">Vote Now</a>
            <a href="{% url 'voting:results_archive' %}" class="btn btn-outline">Past Results</a>
        </div>
    {% else %}
        <h1 class="mb-3 font-display text-3xl font-semibold text-brand-black">Results Not Yet Published</h1>
        <p class="text-base text-neutral-600">
            Check back once the election results have been published.
        </p>
        <div class="mt-8 flex justify-center gap-3">
            <a href="{% url 'voting:results_archive' %}" class="btn btn-outline">Past Results</a>
            <a href="{% url 'core:home' %}" class="btn btn-primary">Public Site</a>
        </div>
    {% endif %}
</div>
{% endblock %}
```

- [ ] **Step 5: Run the full `voting` app test suite**

```bash
.venv/bin/python manage.py test voting -v 2
```

Expected: `OK`, 57 tests (the pre-existing 55 from Task 1, plus these 2 net-new tests — `VotingNavTests` goes from 4 to 5 tests [one removed, two added], `ResultsViewTests` gains 1).

- [ ] **Step 6: Commit**

```bash
git add voting/templates/voting/base.html voting/templates/voting/results_not_published.html voting/tests.py
git commit -m "Gate the student-dashboard voting link and add ongoing-election awareness to the results page"
```

---

### Task 5: Confirm dialogs → styled modal

**Files:**
- Create: `admin_panel/templates/admin_panel/_confirm_modal_script.html`
- Modify: `admin_panel/templates/admin_panel/election_list.html`
- Test: `admin_panel/tests.py` (new class `ElectionActionModalTests`, appended at the end of the file)

- [ ] **Step 1: Write the failing tests**

Append to `admin_panel/tests.py`:

```python
class ElectionActionModalTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username="admin_action_modal", password="pass12345")
        self.admin_profile = AdminProfile.objects.create(user=self.admin_user, is_admin=True)
        self.client.force_login(self.admin_user)

    def test_start_voting_button_uses_modal_not_native_confirm(self):
        election = Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            status="upcoming",
            modified_by=self.admin_profile,
        )
        response = self.client.get(reverse("admin_panel:election_list"))
        self.assertNotContains(response, 'onsubmit="return confirm(')
        self.assertContains(response, f'data-confirm-form="election-start-{election.pk}"')

    def test_end_voting_button_uses_modal(self):
        election = Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            status="ongoing",
            modified_by=self.admin_profile,
        )
        response = self.client.get(reverse("admin_panel:election_list"))
        self.assertContains(response, f'data-confirm-form="election-end-{election.pk}"')

    def test_publish_result_button_uses_modal(self):
        election = Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            status="ended",
            modified_by=self.admin_profile,
        )
        response = self.client.get(reverse("admin_panel:election_list"))
        self.assertContains(response, f'data-confirm-form="election-publish-results-{election.pk}"')
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
.venv/bin/python manage.py test admin_panel.tests.ElectionActionModalTests -v 2
```

Expected: all 3 FAIL — the template still has the native `onsubmit="return confirm(...)"` dialogs and no `data-confirm-form` attributes yet.

- [ ] **Step 3: Create the shared modal script**

```html
<script>
document.addEventListener("DOMContentLoaded", function () {
    var modal = document.getElementById("confirm-modal");
    if (!modal) {
        return;
    }
    var messageEl = document.getElementById("confirm-modal-message");
    var pendingFormId = null;

    document.querySelectorAll("[data-confirm-form]").forEach(function (button) {
        button.addEventListener("click", function () {
            pendingFormId = button.getAttribute("data-confirm-form");
            messageEl.textContent = button.getAttribute("data-confirm-message");
            modal.showModal();
        });
    });

    modal.querySelector("[data-confirm-cancel]").addEventListener("click", function () {
        pendingFormId = null;
        modal.close();
    });

    modal.querySelector("[data-confirm-accept]").addEventListener("click", function () {
        if (pendingFormId) {
            document.getElementById(pendingFormId).submit();
        }
        modal.close();
    });
});
</script>
```

- [ ] **Step 4: Replace the 3 action buttons in `election_list.html`**

Replace the contents of `admin_panel/templates/admin_panel/election_list.html` with:

```html
{% extends "admin_panel/base.html" %}

{% block title %}Elections · NAIFT Admin{% endblock %}

{% block content %}
<div class="flex items-center justify-between mb-8">
    <h1 class="font-display text-3xl text-brand-purple">Elections</h1>
    <a href="{% url 'admin_panel:election_create' %}" class="bg-brand-purple text-brand-white px-4 py-2 rounded hover:opacity-90">Add Election</a>
</div>

<dialog id="confirm-modal" class="rounded-lg border border-brand-purple/20 p-6 max-w-sm w-full">
    <p id="confirm-modal-message" class="mb-6 text-brand-black"></p>
    <div class="flex justify-end gap-3">
        <button type="button" data-confirm-cancel class="text-brand-black/70 hover:underline">Cancel</button>
        <button type="button" data-confirm-accept class="bg-brand-purple text-brand-white px-4 py-2 rounded hover:opacity-90">Confirm</button>
    </div>
</dialog>

<table class="w-full text-left border-collapse">
    <thead>
        <tr class="border-b border-brand-black/10">
            <th class="py-2">Session</th>
            <th class="py-2">Status</th>
            <th class="py-2">Results Published?</th>
            <th class="py-2"></th>
        </tr>
    </thead>
    <tbody>
        {% for election in elections %}
            <tr class="border-b border-brand-black/10">
                <td class="py-2">{{ election.session }}</td>
                <td class="py-2">{{ election.get_status_display }}</td>
                <td class="py-2">{% if election.is_results_published %}Yes{% else %}No{% endif %}</td>
                <td class="py-2 text-right">
                    <a href="{% url 'admin_panel:election_update' election.pk %}" class="text-brand-purple hover:underline">Edit</a>
                    &middot;
                    <a href="{% url 'admin_panel:election_results' election.pk %}" class="text-brand-purple hover:underline">Results</a>
                    &middot;
                    <a href="{% url 'admin_panel:contestant_list' %}?election={{ election.pk }}" class="text-brand-purple hover:underline">Contestants</a>
                    {% if election.status == "upcoming" %}
                        &middot;
                        <form id="election-start-{{ election.pk }}" method="post" action="{% url 'admin_panel:election_start' election.pk %}" class="inline">
                            {% csrf_token %}
                        </form>
                        <button type="button"
                                data-confirm-form="election-start-{{ election.pk }}"
                                data-confirm-message="Start voting for {{ election.session|escapejs }}?"
                                class="text-brand-purple hover:underline">Start Voting</button>
                    {% elif election.status == "ongoing" %}
                        &middot;
                        <form id="election-end-{{ election.pk }}" method="post" action="{% url 'admin_panel:election_end' election.pk %}" class="inline">
                            {% csrf_token %}
                        </form>
                        <button type="button"
                                data-confirm-form="election-end-{{ election.pk }}"
                                data-confirm-message="End voting for {{ election.session|escapejs }}?"
                                class="text-brand-purple hover:underline">End Voting</button>
                    {% elif election.status == "ended" and not election.is_results_published %}
                        &middot;
                        <form id="election-publish-results-{{ election.pk }}" method="post" action="{% url 'admin_panel:election_publish_results' election.pk %}" class="inline">
                            {% csrf_token %}
                        </form>
                        <button type="button"
                                data-confirm-form="election-publish-results-{{ election.pk }}"
                                data-confirm-message="Publish results for {{ election.session|escapejs }}? This makes them publicly visible."
                                class="text-brand-purple hover:underline">Publish Result</button>
                    {% endif %}
                </td>
            </tr>
        {% empty %}
            <tr><td colspan="4" class="py-4">No elections yet.</td></tr>
        {% endfor %}
    </tbody>
</table>

{% include "admin_panel/_confirm_modal_script.html" %}
{% endblock %}
```

(The 3 `<form>` elements keep identical `method`/`action`/`{% csrf_token %}` to before — only their trigger changed from a `type="submit"` button with an inline `onsubmit` to a separate `type="button"` wired to the shared modal via `data-confirm-form`/`data-confirm-message`.)

- [ ] **Step 5: Run the full `admin_panel` app test suite**

```bash
.venv/bin/python manage.py test admin_panel -v 2
```

Expected: `OK`, 66 tests (the pre-existing 63 from Task 1, plus these 3 new tests). The pre-existing `ElectionActionViewTests` (9 tests, POSTing directly to the action URLs) must still pass unchanged — this is a presentation-layer-only change, the POST endpoints and their server-side validation are untouched.

- [ ] **Step 6: Commit**

```bash
git add admin_panel/templates/admin_panel/_confirm_modal_script.html admin_panel/templates/admin_panel/election_list.html admin_panel/tests.py
git commit -m "Replace native confirm() dialogs with a styled modal for election actions"
```

---

### Task 6: Shared CSV import helper + `seed_students` refactor

**Files:**
- Create: `voting/csv_import.py`
- Modify: `voting/management/commands/seed_students.py`
- Test: `voting/tests.py` (new class `ImportStudentsTests`; add to `SeedStudentsCommandTests`)

This task changes `seed_students`'s behavior: it currently only ever creates new students (re-running with corrected data for an existing matric number is silently a no-op — see its own `help` text). After this task, it also updates `first_name`/`last_name`/`level` on an existing match, matching the spec's requirement that both the CLI command and the new web upload (Task 8) share identical create-or-update logic. No existing test asserts the old create-only behavior, so this is a safe, intentional change — not a regression.

- [ ] **Step 1: Write the failing tests**

Append to `voting/tests.py` (after the end of `SeedStudentsCommandTests`, before `VotingNavTests`):

```python
class ImportStudentsTests(TestCase):
    def test_creates_new_student(self):
        result = import_students(
            [(2, {"first_name": "Jane", "last_name": "Doe", "matric_number": "2026/1/00001CF", "level": "300"})]
        )
        self.assertEqual(result["created"], 1)
        self.assertEqual(result["updated"], 0)
        self.assertEqual(result["skipped"], [])
        self.assertTrue(Student.objects.filter(matric_number="2026/1/00001CF", first_name="Jane").exists())

    def test_updates_existing_student_by_matric_number(self):
        Student.objects.create(first_name="Jane", last_name="Doe", matric_number="2026/1/00001CF", level="200")
        result = import_students(
            [(2, {"first_name": "Janet", "last_name": "Doe", "matric_number": "2026/1/00001CF", "level": "300"})]
        )
        self.assertEqual(result["created"], 0)
        self.assertEqual(result["updated"], 1)
        student = Student.objects.get(matric_number="2026/1/00001CF")
        self.assertEqual(student.first_name, "Janet")
        self.assertEqual(student.level, "300")

    def test_skips_malformed_matric_number(self):
        result = import_students(
            [(2, {"first_name": "Jane", "last_name": "Doe", "matric_number": "not-a-matric-number", "level": "300"})]
        )
        self.assertEqual(result["created"], 0)
        self.assertEqual(len(result["skipped"]), 1)
        self.assertEqual(result["skipped"][0][0], 2)

    def test_skips_row_with_missing_column(self):
        result = import_students(
            [(2, {"first_name": "Jane", "last_name": "Doe", "matric_number": "2026/1/00001CF"})]
        )
        self.assertEqual(result["created"], 0)
        self.assertEqual(len(result["skipped"]), 1)
```

Add this import near the top of `voting/tests.py`, alongside the existing `from .models import Student, Vote` line:

```python
from .csv_import import import_students
```

Add this test to the existing `SeedStudentsCommandTests` class (after `test_malformed_matric_number_is_skipped_and_reported`):

```python
    def test_rerunning_with_changed_data_updates_existing_student(self):
        csv_content = "first_name,last_name,matric_number,level\nJane,Doe,2022/1/90976CF,300\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            csv_path = f.name
        try:
            call_command("seed_students", csv_path, stdout=StringIO())
            updated_csv_content = "first_name,last_name,matric_number,level\nJanet,Doe,2022/1/90976CF,400\n"
            with open(csv_path, "w") as f:
                f.write(updated_csv_content)
            out = StringIO()
            call_command("seed_students", csv_path, stdout=out)
            student = Student.objects.get(matric_number="2022/1/90976CF")
            self.assertEqual(student.first_name, "Janet")
            self.assertEqual(student.level, "400")
            self.assertIn("updated 1 existing student", out.getvalue())
        finally:
            os.unlink(csv_path)
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
.venv/bin/python manage.py test voting.tests.ImportStudentsTests voting.tests.SeedStudentsCommandTests -v 2
```

Expected: `ImportStudentsTests` fails with `ModuleNotFoundError` — `voting/csv_import.py` doesn't exist yet. `test_rerunning_with_changed_data_updates_existing_student` fails — the current command's `get_or_create` silently no-ops on the second run, so `student.first_name` stays `"Jane"`, not `"Janet"`.

- [ ] **Step 3: Create `voting/csv_import.py`**

```python
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from .models import Student


def import_students(rows):
    """Create-or-update Student rows from an iterable of (row_number, row) pairs,
    where each `row` is a dict with first_name/last_name/matric_number/level keys
    (e.g. from `enumerate(csv.DictReader(f), start=2)`, matching a CSV's header
    being row 1). Existing students are matched by matric_number; only
    first_name/last_name/level are updated on an existing match — matric_number
    itself is never changed by this importer, since it's the match key.

    Returns {"created": int, "updated": int, "skipped": [(row_number, reason), ...]}.
    """
    created_count = 0
    updated_count = 0
    skipped = []
    for row_number, row in rows:
        try:
            first_name = row["first_name"].strip()
            last_name = row["last_name"].strip()
            matric_number = row["matric_number"].strip()
            level = row["level"].strip()
        except (KeyError, AttributeError) as exc:
            skipped.append((row_number, f"missing or blank column ({exc})"))
            continue

        candidate = Student(
            first_name=first_name, last_name=last_name, matric_number=matric_number, level=level
        )
        try:
            candidate.clean_fields()
        except ValidationError as exc:
            skipped.append((row_number, exc.messages[0]))
            continue

        try:
            existing = Student.objects.filter(matric_number=matric_number).first()
            if existing is not None:
                existing.first_name = first_name
                existing.last_name = last_name
                existing.level = level
                existing.save(update_fields=["first_name", "last_name", "level"])
                updated_count += 1
            else:
                Student.objects.create(
                    first_name=first_name, last_name=last_name, matric_number=matric_number, level=level
                )
                created_count += 1
        except IntegrityError as exc:
            skipped.append((row_number, str(exc)))
            continue
    return {"created": created_count, "updated": updated_count, "skipped": skipped}
```

- [ ] **Step 4: Refactor `seed_students` to use it**

Replace the contents of `voting/management/commands/seed_students.py` with:

```python
import csv

from django.core.management.base import BaseCommand, CommandError

from voting.csv_import import import_students


class Command(BaseCommand):
    help = (
        "Bulk-import students from a CSV file (columns: first_name,last_name,matric_number,level). "
        "Existing students are matched by matric_number and have their name/level updated; "
        "new matric numbers create new students."
    )

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str)

    def handle(self, *args, **options):
        csv_path = options["csv_path"]
        try:
            with open(csv_path, newline="", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)
                result = import_students(enumerate(reader, start=2))
        except FileNotFoundError:
            raise CommandError(f"CSV file not found: {csv_path}")
        for row_number, reason in result["skipped"]:
            self.stderr.write(f"Row {row_number}: {reason} — skipped.")
        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {result['created']} new student(s), "
                f"updated {result['updated']} existing student(s), "
                f"skipped {len(result['skipped'])} row(s)."
            )
        )
```

- [ ] **Step 5: Run the full `voting` app test suite**

```bash
.venv/bin/python manage.py test voting -v 2
```

Expected: `OK`, 62 tests (the pre-existing 57 from Task 4, plus 5 new: 4 in `ImportStudentsTests`, 1 in `SeedStudentsCommandTests`). The 3 pre-existing `SeedStudentsCommandTests` tests (`test_imports_students_from_csv`, `test_missing_csv_file_raises_command_error`, `test_missing_column_is_skipped_and_reported`, `test_malformed_matric_number_is_skipped_and_reported`) must all still pass — their assertions (`"Imported 1 new student"`, `"skipped 1 row"`, `"Row 2"`) are substrings of the new, longer summary message, so they still match.

- [ ] **Step 6: Commit**

```bash
git add voting/csv_import.py voting/management/commands/seed_students.py voting/tests.py
git commit -m "Extract shared create-or-update CSV import logic; seed_students now updates existing students"
```

---

### Task 7: Student management admin page (list, filter, pagination, create, update, delete)

**Files:**
- Modify: `admin_panel/views.py` (new `StudentListView`, `StudentCreateView`, `StudentUpdateView`, `StudentDeleteView`)
- Modify: `admin_panel/urls.py` (4 new routes)
- Modify: `admin_panel/templates/admin_panel/base.html` (nav gains a "Students" link)
- Create: `admin_panel/templates/admin_panel/student_list.html`
- Create: `admin_panel/templates/admin_panel/student_form.html`
- Create: `admin_panel/templates/admin_panel/student_confirm_delete.html`
- Test: `admin_panel/tests.py` (new classes `StudentCRUDTests`, `StudentListFilterTests`; add to existing `AdminNavTests`)

CSV upload is intentionally NOT part of this task — the list page built here has no upload form yet; Task 8 adds it on top of this already-working list page.

- [ ] **Step 1: Write the failing tests**

Append to `admin_panel/tests.py`:

```python
class StudentCRUDTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username="admin_student_crud", password="pass12345")
        self.admin_profile = AdminProfile.objects.create(user=self.admin_user, is_admin=True)
        self.client.force_login(self.admin_user)

    def test_list_view_returns_200(self):
        response = self.client.get(reverse("admin_panel:student_list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin_panel/student_list.html")

    def test_create_student(self):
        response = self.client.post(
            reverse("admin_panel:student_create"),
            {"first_name": "Jane", "last_name": "Doe", "matric_number": "2026/1/00001CF", "level": "300"},
        )
        self.assertRedirects(response, reverse("admin_panel:student_list"))
        self.assertTrue(Student.objects.filter(matric_number="2026/1/00001CF").exists())

    def test_update_student(self):
        student = Student.objects.create(
            first_name="Jane", last_name="Doe", matric_number="2026/1/00001CF", level="200"
        )
        response = self.client.post(
            reverse("admin_panel:student_update", args=[student.pk]),
            {"first_name": "Janet", "last_name": "Doe", "matric_number": "2026/1/00001CF", "level": "300"},
        )
        self.assertRedirects(response, reverse("admin_panel:student_list"))
        student.refresh_from_db()
        self.assertEqual(student.first_name, "Janet")
        self.assertEqual(student.level, "300")

    def test_delete_student_with_no_votes(self):
        student = Student.objects.create(
            first_name="Jane", last_name="Doe", matric_number="2026/1/00001CF", level="300"
        )
        response = self.client.post(reverse("admin_panel:student_delete", args=[student.pk]))
        self.assertRedirects(response, reverse("admin_panel:student_list"))
        self.assertFalse(Student.objects.filter(pk=student.pk).exists())

    def test_delete_protected_student_shows_friendly_error_instead_of_crashing(self):
        student = Student.objects.create(
            first_name="Jane", last_name="Doe", matric_number="2026/1/00001CF", level="300"
        )
        election = Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            modified_by=self.admin_profile,
        )
        position = Position.objects.create(title="President", modified_by=self.admin_profile)
        contestant = Contestant.objects.create(
            name="John Roe", manifesto="Vote for me.", position=position, election=election
        )
        Vote.objects.create(student=student, election=election, position=position, contestant=contestant)
        response = self.client.post(reverse("admin_panel:student_delete", args=[student.pk]), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Student.objects.filter(pk=student.pk).exists())
        self.assertContains(response, "cannot be deleted")


class StudentListFilterTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username="admin_student_filter", password="pass12345")
        AdminProfile.objects.create(user=self.admin_user, is_admin=True)
        self.client.force_login(self.admin_user)
        Student.objects.create(first_name="Amina", last_name="Bello", matric_number="2026/1/00001CF", level="300")
        Student.objects.create(first_name="John", last_name="Roe", matric_number="2026/1/00002CF", level="200")
        Student.objects.create(first_name="Zainab", last_name="Yusuf", matric_number="2026/1/00003CF", level="300")

    def test_no_filter_returns_all_students(self):
        response = self.client.get(reverse("admin_panel:student_list"))
        self.assertEqual(len(response.context["students"]), 3)

    def test_filter_by_matric_number(self):
        response = self.client.get(reverse("admin_panel:student_list"), {"matric_number": "00002"})
        students = list(response.context["students"])
        self.assertEqual(len(students), 1)
        self.assertEqual(students[0].matric_number, "2026/1/00002CF")

    def test_filter_by_level(self):
        response = self.client.get(reverse("admin_panel:student_list"), {"level": "300"})
        students = list(response.context["students"])
        self.assertEqual(len(students), 2)

    def test_sort_descending_reverses_alphabetical_order(self):
        response = self.client.get(reverse("admin_panel:student_list"), {"sort": "desc"})
        students = list(response.context["students"])
        self.assertEqual([s.last_name for s in students], ["Yusuf", "Roe", "Bello"])

    def test_pagination_splits_results_across_pages(self):
        for i in range(30):
            Student.objects.create(
                first_name=f"Student{i}",
                last_name=f"Surname{i:03d}",
                matric_number=f"2026/2/{i:05d}CF",
                level="100",
            )
        response_page1 = self.client.get(reverse("admin_panel:student_list"))
        response_page2 = self.client.get(reverse("admin_panel:student_list"), {"page": 2})
        self.assertEqual(len(response_page1.context["students"]), 25)
        self.assertTrue(len(response_page2.context["students"]) > 0)
        page1_pks = {s.pk for s in response_page1.context["students"]}
        page2_pks = {s.pk for s in response_page2.context["students"]}
        self.assertEqual(page1_pks & page2_pks, set())
```

Add this test to the existing `AdminNavTests` class (after `test_nav_includes_public_site_link`):

```python
    def test_nav_includes_students_link(self):
        response = self.client.get(reverse("admin_panel:dashboard"))
        self.assertContains(
            response, f'href="{reverse("admin_panel:student_list")}" class="hover:text-brand-purple">Students'
        )
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
.venv/bin/python manage.py test admin_panel.tests.StudentCRUDTests admin_panel.tests.StudentListFilterTests admin_panel.tests.AdminNavTests -v 2
```

Expected: all FAIL — `reverse("admin_panel:student_list")` etc. raise `NoReverseMatch`, since none of these URLs/views/templates exist yet.

- [ ] **Step 3: Add the Student views**

In `admin_panel/views.py`, add this import alongside the existing `from executives.models import Executive` line:

```python
from django.db.models import ProtectedError
from voting.models import Student
```

(Merge `ProtectedError` into the existing `from django.db.models import Count, F, Q` line from Task 1, rather than a separate import line — i.e. that line should now read `from django.db.models import Count, F, ProtectedError, Q`.)

Add these 4 view classes, anywhere after `ExecutiveDeleteView` and before `ElectionListView` (matching this file's existing grouping-by-model order):

```python
class StudentListView(AdminRequiredMixin, ListView):
    model = Student
    template_name = "admin_panel/student_list.html"
    context_object_name = "students"
    paginate_by = 25

    def get_queryset(self):
        queryset = Student.objects.all()
        matric_number = self.request.GET.get("matric_number")
        level = self.request.GET.get("level")
        sort = self.request.GET.get("sort", "asc")
        if matric_number:
            queryset = queryset.filter(matric_number__icontains=matric_number)
        if level:
            queryset = queryset.filter(level=level)
        order = ["last_name", "first_name"] if sort != "desc" else ["-last_name", "-first_name"]
        return queryset.order_by(*order)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["level_choices"] = Student.LEVEL_CHOICES
        context["current_matric_number"] = self.request.GET.get("matric_number", "")
        context["current_level"] = self.request.GET.get("level", "")
        context["current_sort"] = self.request.GET.get("sort", "asc")
        return context


class StudentCreateView(AdminRequiredMixin, CreateView):
    model = Student
    fields = ["first_name", "last_name", "matric_number", "level"]
    template_name = "admin_panel/student_form.html"
    success_url = reverse_lazy("admin_panel:student_list")


class StudentUpdateView(AdminRequiredMixin, UpdateView):
    model = Student
    fields = ["first_name", "last_name", "matric_number", "level"]
    template_name = "admin_panel/student_form.html"
    success_url = reverse_lazy("admin_panel:student_list")


class StudentDeleteView(AdminRequiredMixin, DeleteView):
    model = Student
    template_name = "admin_panel/student_confirm_delete.html"
    success_url = reverse_lazy("admin_panel:student_list")

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        try:
            self.object.delete()
        except ProtectedError:
            messages.error(request, f"{self.object} cannot be deleted because they have already voted.")
            return redirect("admin_panel:student_list")
        return redirect(self.get_success_url())
```

- [ ] **Step 4: Add the URL routes**

In `admin_panel/urls.py`, add these 4 routes after the `executives/...` block and before the `elections/...` block:

```python
    path("students/", views.StudentListView.as_view(), name="student_list"),
    path("students/add/", views.StudentCreateView.as_view(), name="student_create"),
    path("students/<int:pk>/edit/", views.StudentUpdateView.as_view(), name="student_update"),
    path("students/<int:pk>/delete/", views.StudentDeleteView.as_view(), name="student_delete"),
```

- [ ] **Step 5: Add the "Students" nav link**

In `admin_panel/templates/admin_panel/base.html`, add the link right after "Contestants" and before "Executives":

```html
            <a href="{% url 'admin_panel:contestant_list' %}" class="hover:text-brand-purple">Contestants</a>
            <a href="{% url 'admin_panel:student_list' %}" class="hover:text-brand-purple">Students</a>
            <a href="{% url 'admin_panel:executive_list' %}" class="hover:text-brand-purple">Executives</a>
```

- [ ] **Step 6: Create `student_list.html`**

```html
{% extends "admin_panel/base.html" %}

{% block title %}Students · NAIFT Admin{% endblock %}

{% block content %}
<div class="flex items-center justify-between mb-8">
    <h1 class="font-display text-3xl text-brand-purple">Students</h1>
    <a href="{% url 'admin_panel:student_create' %}" class="bg-brand-purple text-brand-white px-4 py-2 rounded hover:opacity-90">Add Student</a>
</div>

<form method="get" class="flex flex-wrap items-end gap-4 mb-6">
    <div>
        <label class="block text-sm text-brand-black/70 mb-1" for="id_matric_number">Matric Number</label>
        <input type="text" id="id_matric_number" name="matric_number" value="{{ current_matric_number }}" class="border border-brand-black/20 rounded px-3 py-2">
    </div>
    <div>
        <label class="block text-sm text-brand-black/70 mb-1" for="id_level">Level</label>
        <select id="id_level" name="level" class="border border-brand-black/20 rounded px-3 py-2">
            <option value="">All</option>
            {% for value, label in level_choices %}
                <option value="{{ value }}" {% if value == current_level %}selected{% endif %}>{{ label }}</option>
            {% endfor %}
        </select>
    </div>
    <input type="hidden" name="sort" value="{{ current_sort }}">
    <button type="submit" class="bg-brand-purple text-brand-white px-4 py-2 rounded hover:opacity-90">Filter</button>
</form>

<table class="w-full text-left border-collapse">
    <thead>
        <tr class="border-b border-brand-black/10">
            <th class="py-2">
                <a href="?matric_number={{ current_matric_number }}&level={{ current_level }}&sort={% if current_sort == 'desc' %}asc{% else %}desc{% endif %}" class="hover:underline">
                    Name {% if current_sort == "desc" %}&darr;{% else %}&uarr;{% endif %}
                </a>
            </th>
            <th class="py-2">Matric Number</th>
            <th class="py-2">Level</th>
            <th class="py-2"></th>
        </tr>
    </thead>
    <tbody>
        {% for student in students %}
            <tr class="border-b border-brand-black/10">
                <td class="py-2">{{ student.first_name }} {{ student.last_name }}</td>
                <td class="py-2">{{ student.matric_number }}</td>
                <td class="py-2">{{ student.get_level_display }}</td>
                <td class="py-2 text-right">
                    <a href="{% url 'admin_panel:student_update' student.pk %}" class="text-brand-purple hover:underline">Edit</a>
                    &middot;
                    <a href="{% url 'admin_panel:student_delete' student.pk %}" class="text-brand-purple hover:underline">Delete</a>
                </td>
            </tr>
        {% empty %}
            <tr><td colspan="4" class="py-4">No students yet.</td></tr>
        {% endfor %}
    </tbody>
</table>

{% if is_paginated %}
<div class="flex items-center justify-between mt-4">
    {% if page_obj.has_previous %}
        <a href="?matric_number={{ current_matric_number }}&level={{ current_level }}&sort={{ current_sort }}&page={{ page_obj.previous_page_number }}" class="text-brand-purple hover:underline">&larr; Previous</a>
    {% else %}
        <span></span>
    {% endif %}
    <span class="text-sm text-brand-black/70">Page {{ page_obj.number }} of {{ page_obj.paginator.num_pages }}</span>
    {% if page_obj.has_next %}
        <a href="?matric_number={{ current_matric_number }}&level={{ current_level }}&sort={{ current_sort }}&page={{ page_obj.next_page_number }}" class="text-brand-purple hover:underline">Next &rarr;</a>
    {% else %}
        <span></span>
    {% endif %}
</div>
{% endif %}
{% endblock %}
```

- [ ] **Step 7: Create `student_form.html`**

```html
{% extends "admin_panel/base.html" %}

{% block title %}Student · NAIFT Admin{% endblock %}

{% block content %}
<a href="{% url 'admin_panel:student_list' %}" class="text-brand-purple hover:underline block mb-4">&larr; Back to Students</a>
<h1 class="font-display text-3xl text-brand-purple mb-8">{% if object %}Edit{% else %}Add{% endif %} Student</h1>

<form method="post" class="flex flex-col gap-4 max-w-md">
    {% csrf_token %}
    {{ form.as_p }}
    <button type="submit" class="bg-brand-purple text-brand-white px-4 py-2 rounded hover:opacity-90">Save</button>
</form>
{% endblock %}
```

- [ ] **Step 8: Create `student_confirm_delete.html`**

```html
{% extends "admin_panel/base.html" %}

{% block title %}Delete Student · NAIFT Admin{% endblock %}

{% block content %}
<div class="mx-auto max-w-lg">
    <a href="{% url 'admin_panel:student_list' %}"
       class="mb-4 inline-block text-sm font-medium text-brand-purple hover:underline">
        ← Back to Students
    </a>

    <div class="danger-zone">
        <p class="text-xs font-semibold uppercase tracking-wider text-error">Destructive action</p>
        <h1 class="mt-2 font-display text-2xl font-semibold text-brand-black">
            Delete “{{ object }}”?
        </h1>
        <p class="mt-2 text-sm text-neutral-700">
            This will permanently remove the student. This action cannot be undone.
        </p>

        <form method="post" class="mt-6 flex flex-wrap items-center gap-3">
            {% csrf_token %}
            <button type="submit" class="btn btn-danger">Yes, delete</button>
            <a href="{% url 'admin_panel:student_list' %}" class="btn btn-ghost">Cancel</a>
        </form>
    </div>
</div>
{% endblock %}
```

- [ ] **Step 9: Run the full `admin_panel` app test suite**

```bash
.venv/bin/python manage.py test admin_panel -v 2
```

Expected: `OK`, 77 tests (the pre-existing 66 from Task 5, plus 11 new: 5 in `StudentCRUDTests`, 5 in `StudentListFilterTests`, 1 in `AdminNavTests`).

- [ ] **Step 10: Commit**

```bash
git add admin_panel/views.py admin_panel/urls.py admin_panel/templates/admin_panel/base.html admin_panel/templates/admin_panel/student_list.html admin_panel/templates/admin_panel/student_form.html admin_panel/templates/admin_panel/student_confirm_delete.html admin_panel/tests.py
git commit -m "Add Student management admin page: list with filters/pagination, create, update, delete"
```

---

### Task 8: Student CSV bulk upload (web)

**Files:**
- Modify: `admin_panel/views.py` (new `StudentCSVUploadView`)
- Modify: `admin_panel/urls.py` (1 new route)
- Modify: `admin_panel/templates/admin_panel/student_list.html` (add the upload form section)
- Test: `admin_panel/tests.py` (new class `StudentCSVUploadViewTests`)

- [ ] **Step 1: Write the failing tests**

Append to `admin_panel/tests.py`:

```python
class StudentCSVUploadViewTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username="admin_student_csv", password="pass12345")
        AdminProfile.objects.create(user=self.admin_user, is_admin=True)
        self.client.force_login(self.admin_user)

    def test_uploading_csv_creates_new_student(self):
        csv_content = b"first_name,last_name,matric_number,level\nJane,Doe,2026/1/00001CF,300\n"
        csv_file = SimpleUploadedFile("students.csv", csv_content, content_type="text/csv")
        response = self.client.post(
            reverse("admin_panel:student_csv_upload"), {"csv_file": csv_file}, follow=True
        )
        self.assertTrue(Student.objects.filter(matric_number="2026/1/00001CF").exists())
        self.assertContains(response, "Imported 1 new student")

    def test_uploading_csv_updates_existing_student(self):
        Student.objects.create(first_name="Jane", last_name="Doe", matric_number="2026/1/00001CF", level="200")
        csv_content = b"first_name,last_name,matric_number,level\nJanet,Doe,2026/1/00001CF,300\n"
        csv_file = SimpleUploadedFile("students.csv", csv_content, content_type="text/csv")
        response = self.client.post(
            reverse("admin_panel:student_csv_upload"), {"csv_file": csv_file}, follow=True
        )
        student = Student.objects.get(matric_number="2026/1/00001CF")
        self.assertEqual(student.first_name, "Janet")
        self.assertContains(response, "updated 1 existing student")

    def test_uploading_csv_with_malformed_row_reports_skip(self):
        csv_content = b"first_name,last_name,matric_number,level\nJane,Doe,not-a-matric-number,300\n"
        csv_file = SimpleUploadedFile("students.csv", csv_content, content_type="text/csv")
        response = self.client.post(
            reverse("admin_panel:student_csv_upload"), {"csv_file": csv_file}, follow=True
        )
        self.assertContains(response, "skipped 1 row")
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
.venv/bin/python manage.py test admin_panel.tests.StudentCSVUploadViewTests -v 2
```

Expected: all 3 FAIL — `reverse("admin_panel:student_csv_upload")` raises `NoReverseMatch`, since neither the view nor the URL exist yet.

- [ ] **Step 3: Add `StudentCSVUploadView`**

In `admin_panel/views.py`, add `import csv` at the very top of the file (alongside the other imports), and add this import alongside the existing `from voting.models import Student` line (added in Task 7):

```python
from voting.csv_import import import_students
```

Add the view class right after `StudentDeleteView`:

```python
class StudentCSVUploadView(AdminRequiredMixin, View):
    def post(self, request):
        csv_file = request.FILES.get("csv_file")
        if not csv_file:
            messages.error(request, "No CSV file was uploaded.")
            return redirect("admin_panel:student_list")
        decoded = csv_file.read().decode("utf-8").splitlines()
        reader = csv.DictReader(decoded)
        result = import_students(enumerate(reader, start=2))
        for row_number, reason in result["skipped"]:
            messages.error(request, f"Row {row_number}: {reason} — skipped.")
        messages.success(
            request,
            f"Imported {result['created']} new student(s), "
            f"updated {result['updated']} existing student(s), "
            f"skipped {len(result['skipped'])} row(s).",
        )
        return redirect("admin_panel:student_list")
```

- [ ] **Step 4: Add the URL route**

In `admin_panel/urls.py`, add this route right after `student_delete`:

```python
    path("students/upload-csv/", views.StudentCSVUploadView.as_view(), name="student_csv_upload"),
```

- [ ] **Step 5: Add the upload form to `student_list.html`**

In `admin_panel/templates/admin_panel/student_list.html`, add this section right before `{% endblock %}`:

```html

<div class="mt-10 border-t border-brand-black/10 pt-6">
    <h2 class="font-display text-xl text-brand-black mb-3">Bulk Import / Update via CSV</h2>
    <p class="text-sm text-brand-black/70 mb-3">
        Columns: first_name, last_name, matric_number, level. Existing students (matched by matric number)
        have their name and level updated; new matric numbers create new students.
    </p>
    <form method="post" action="{% url 'admin_panel:student_csv_upload' %}" enctype="multipart/form-data" class="flex items-end gap-4">
        {% csrf_token %}
        <input type="file" name="csv_file" accept=".csv" required class="border border-brand-black/20 rounded px-3 py-2">
        <button type="submit" class="bg-brand-purple text-brand-white px-4 py-2 rounded hover:opacity-90">Upload</button>
    </form>
</div>
```

- [ ] **Step 6: Run the full `admin_panel` app test suite**

```bash
.venv/bin/python manage.py test admin_panel -v 2
```

Expected: `OK`, 80 tests (the pre-existing 77 from Task 7, plus these 3 new tests).

- [ ] **Step 7: Commit**

```bash
git add admin_panel/views.py admin_panel/urls.py admin_panel/templates/admin_panel/student_list.html admin_panel/tests.py
git commit -m "Add Student CSV bulk upload (create-or-update) to the admin Students page"
```

---

### Task 9: Final verification

**Files:** none (verification only)

- [ ] **Step 1: Run the entire test suite**

```bash
.venv/bin/python manage.py test
```

Expected: `OK` (180 tests total — 12 in `core`, 6 in `executives`, 20 in `elections`, 80 in `admin_panel`, 62 in `voting`).

- [ ] **Step 2: Run Django's system check**

```bash
.venv/bin/python manage.py check
```

Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 3: Manual smoke test**

No automated test substitutes for actually clicking through this in a browser.

1. Ensure Postgres is running: `docker compose up -d db`.
2. Start the Tailwind watcher: `.venv/bin/python manage.py tailwind start` (or `tailwind build` once for a static check).
3. Start the dev server: `.venv/bin/python manage.py runserver`.
4. **Vote-carryover fix**: in the admin dashboard, create an Election + Position + Contestant, cast a vote for it via the student flow, confirm the vote count shows correctly. Then (simulating the original bug report) create a second Election and edit the existing Contestant — confirm the `election` field is no longer present on the edit form at all. Manually set `contestant.election` to the new election via the Django shell (`python manage.py shell`) to simulate already-corrupted data, then check that election's results/dashboard chart show 0 votes for that contestant, not the old count.
5. **Visibility**: with no ongoing election, confirm the public site's nav/hero/aside "Vote" elements and the student dashboard's "Vote" nav link are all absent, and the results page shows the generic "not yet published" message. Start an election (status → ongoing) — confirm all those elements now appear, and the results page (if not yet published) now shows "An Election Is Currently Open" instead. End the election — confirm the Vote elements disappear again.
6. **Modal**: on the admin Elections list, click Start Voting / End Voting / Publish Result — confirm each opens a styled in-page dialog (not the browser's native confirm popup), Cancel closes it with no change, Confirm submits and transitions the election's status as before.
7. **Student management**: visit the new Students page. Add a student manually, edit them, delete them. Create 30+ students and confirm pagination works. Filter by matric number and by level. Upload a CSV with one new matric number and one matching an existing student with changed name/level — confirm the new one is created, the existing one is updated (name/level only), and the summary message reports both correctly. Upload a CSV with a malformed row — confirm it's skipped and reported, not a crash. Try deleting a student who has already voted — confirm a friendly error, not a 500.

- [ ] **Step 4: Stop services**

```bash
lsof -ti:8000 -sTCP:LISTEN | xargs -r kill
```

(Leave Postgres running via `docker compose` — shared infrastructure.)

---

## Self-Review Notes

- **Spec coverage:** Section 1 (vote-carryover fix) → Task 1. Section 2 (election-status visibility) → Tasks 2, 3, 4 (context processor, then its two consumers: public site and student dashboard/results page). Section 3 (confirm → modal) → Task 5. Section 4 (student management) → Tasks 6, 7, 8 (shared import helper first, since both the existing CLI command and the new web view depend on it; then CRUD; then CSV upload layered on top of the already-working CRUD list page). Every testing bullet from the spec maps to a concrete test: carryover fix proven directly (Task 1's 3 reassignment tests) and its prevention proven too (`test_update_does_not_change_election`); context processor's 4 states (Task 2); public/student visibility in both states (Tasks 3, 4); results-page ongoing-awareness (Task 4); modal replacing native confirm with no behavior change to the underlying POST endpoints (Task 5); CSV create/update/skip semantics tested directly on the shared helper, then again through each of its two callers (Tasks 6, 8); Student CRUD + filter + pagination + protected-delete (Task 7).
- **Type/name consistency:** `voting_is_open` is defined once (Task 2) and referenced identically by every consuming template (Tasks 3, 4) — never renamed. `import_students(rows)`'s signature and return shape (`{"created", "updated", "skipped"}`) are defined once (Task 6) and consumed identically by both `seed_students` (Task 6) and `StudentCSVUploadView` (Task 8) — neither caller re-derives or duplicates the row-processing logic. The `data-confirm-form`/`data-confirm-message` attribute names and the 3 form `id` naming conventions (`election-start-{pk}`, `election-end-{pk}`, `election-publish-results-{pk}`) are defined once (Task 5) and used consistently between the template and the shared script.
- **No placeholders:** every step has complete, runnable code; the 180-test final count is the explicit sum of each task's stated per-app delta against the 144-test baseline, not an unexplained assertion.
