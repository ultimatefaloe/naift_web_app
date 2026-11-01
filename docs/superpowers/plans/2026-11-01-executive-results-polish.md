# Executive & Results Display Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show past executives on the public Executive page, and mark the winning contestant per position on both results views.

**Architecture:** A single shared helper, `elections/results.py::mark_winners(tallies)`, does one in-memory pass over the already-ordered tally queryset both results views already build (`position__title, position_id, -vote_count`), setting a `.is_winner` attribute per contestant — no new query, no new model field. Both `voting.views.results_view` and `admin_panel.views.ElectionResultsView` call it before rendering; both templates render a small badge when `contestant.is_winner`. The Executive page gains a second, independent context variable (`past`) and a grayscale, session-grouped section in its template — no changes to how executives are created/edited.

**Tech Stack:** Django 6.1 views/templates, existing `tallies` annotated queryset pattern, `{% regroup %}`.

---

## Context for the implementer

- Repo: `/home/ultimate/Desktop/UltimateIntelliForge.org/naift_web_app`, branch `dev` (already checked out — continue on it).
- Spec: `docs/superpowers/specs/2026-11-01-executive-results-polish-design.md` (read it before starting).
- Postgres runs via docker-compose. Verify with `docker ps` first; if the daemon isn't reachable, run `systemctl --user start docker-desktop` then `docker compose up -d db`, and poll `docker ps` until the db container shows `(healthy)`.
- Full test suite currently has **104 passing tests** (core=8, executives=3, elections=10, admin_panel=32, voting=51) — verified by actually running `.venv/bin/python manage.py test` immediately before writing this plan.
- The `tallies` queryset (`Contestant` objects annotated with `vote_count`, ordered by `position__title, position_id, -vote_count`) already exists identically in `voting/views.py::results_view` and `admin_panel/views.py::ElectionResultsView` — both already carry a cross-reference comment pointing at each other. Do not change the query itself in this plan; only wrap it with `mark_winners(...)`.
- Out of scope: any change to how executives are created/edited in the admin dashboard; any change to the underlying vote-tallying query.

---

### Task 1: `mark_winners` helper in the `elections` app

**Files:**
- Create: `elections/results.py`
- Test: `elections/tests.py` (new class `MarkWinnersTests`, appended at the end of the file)

- [ ] **Step 1: Write the failing tests**

Add these imports to the top of `elections/tests.py` — merge into the existing import lines rather than duplicating:

```python
from django.db.models import Count, ProtectedError
```

(replacing the existing `from django.db.models import ProtectedError` line), and add two new import lines right after the existing `from .models import Position, Election, Contestant` line:

```python
from voting.models import Student, Vote

from .results import mark_winners
```

Then append this test class at the end of `elections/tests.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
.venv/bin/python manage.py test elections.tests.MarkWinnersTests -v 2
```

Expected: `ModuleNotFoundError` / `ImportError` — `elections/results.py` doesn't exist yet.

- [ ] **Step 3: Create `elections/results.py`**

```python
def mark_winners(tallies):
    """Sets `.is_winner` on each item of an already-ordered tallies list/queryset
    (ordered by position__title, position_id, -vote_count). True only for a
    group's first contestant when their vote_count strictly exceeds the
    second-place count in that same position group — so an unopposed
    contestant (no second place to compare against) always wins, and an exact
    tie for first marks no one, rather than guessing a false winner."""
    tallies = list(tallies)
    for contestant in tallies:
        contestant.is_winner = False
    i = 0
    while i < len(tallies):
        j = i
        while j < len(tallies) and tallies[j].position_id == tallies[i].position_id:
            j += 1
        group = tallies[i:j]
        if group and (len(group) == 1 or group[0].vote_count > group[1].vote_count):
            group[0].is_winner = True
        i = j
    return tallies
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
.venv/bin/python manage.py test elections -v 2
```

Expected: `OK`, 14 tests (the pre-existing 10, plus these 4 new tests).

- [ ] **Step 5: Commit**

```bash
git add elections/results.py elections/tests.py
git commit -m "Add mark_winners helper for per-position winner detection"
```

---

### Task 2: Winner badge on the public voting results page

**Files:**
- Modify: `voting/views.py` (the `results_view` function)
- Modify: `voting/templates/voting/results.html`
- Test: `voting/tests.py` (add to the existing `ResultsViewTests` class)

- [ ] **Step 1: Write the failing tests**

Add these two tests inside the existing `ResultsViewTests` class, after `test_results_shows_vote_tally`:

```python
    def test_results_shows_winner_badge_for_unopposed_contestant(self):
        response = self.client.get(reverse("voting:results"))
        self.assertContains(response, "Winner")

    def test_results_shows_no_winner_badge_for_tied_position(self):
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
        response = self.client.get(reverse("voting:results"))
        # setUp's "Jane Doe" (unopposed in "President") still wins — exactly
        # one "Winner" badge, even though this tied "Secretary" position has none.
        self.assertContains(response, "Winner", count=1)
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
.venv/bin/python manage.py test voting.tests.ResultsViewTests -v 2
```

Expected: both new tests FAIL — the template has no "Winner" text anywhere yet.

- [ ] **Step 3: Call `mark_winners` in the view**

In `voting/views.py`, add this import near the top, alongside the existing `from elections.models import Contestant, Election, Position` line:

```python
from elections.results import mark_winners
```

Then update `results_view` (the tally query stays identical — only wrap it):

```python
def results_view(request, pk=None):
    if pk:
        election = get_object_or_404(Election, pk=pk, is_results_published=True)
    else:
        election = Election.objects.filter(is_results_published=True).order_by("-id").first()
        if election is None:
            return render(request, "voting/results_not_published.html")
    # Kept in sync with admin_panel.views.ElectionResultsView's tally query —
    # update both if the ordering/annotation logic ever changes.
    tallies = mark_winners(
        Contestant.objects.filter(election=election)
        .select_related("position")
        .annotate(vote_count=Count("votes"))
        .order_by("position__title", "position_id", "-vote_count")
    )
    return render(request, "voting/results.html", {"election": election, "tallies": tallies})
```

- [ ] **Step 4: Add the winner badge to the template**

Replace the contents of `voting/templates/voting/results.html` with:

```html
{% extends "voting/base.html" %}

{% block title %}{{ election.session }} Results · NAIFT Voting{% endblock %}

{% block content %}
<h1 class="font-display text-3xl text-brand-purple mb-8">{{ election.session }} Results</h1>

{% regroup tallies by position as position_list %}
{% for position in position_list %}
    <h2 class="font-display text-2xl text-brand-black mb-3">{{ position.grouper }}</h2>
    <ul class="mb-8 space-y-2">
        {% for contestant in position.list %}
            <li class="flex justify-between items-center border-b border-brand-black/10 py-2">
                <span class="flex items-center gap-2">
                    {{ contestant.name }}{% if contestant.alias %} ({{ contestant.alias }}){% endif %}
                    {% if contestant.is_winner %}
                        <span class="text-xs font-display uppercase tracking-wide bg-brand-purple text-brand-white px-2 py-0.5 rounded-full">Winner</span>
                    {% endif %}
                </span>
                <span class="font-display text-brand-purple">{{ contestant.vote_count }} vote{{ contestant.vote_count|pluralize }}</span>
            </li>
        {% endfor %}
    </ul>
{% endfor %}
{% endblock %}
```

- [ ] **Step 5: Run the full `voting` app test suite**

```bash
.venv/bin/python manage.py test voting -v 2
```

Expected: `OK`, 53 tests (the pre-existing 51, plus these 2 new tests).

- [ ] **Step 6: Commit**

```bash
git add voting/views.py voting/templates/voting/results.html voting/tests.py
git commit -m "Show winner badge on the public voting results page"
```

---

### Task 3: Winner badge on the admin Election Results view

**Files:**
- Modify: `admin_panel/views.py` (the `ElectionResultsView` class)
- Modify: `admin_panel/templates/admin_panel/election_results.html`
- Test: `admin_panel/tests.py` (add to the existing `ElectionResultsViewTests` class)

- [ ] **Step 1: Write the failing tests**

Add these two tests inside the existing `ElectionResultsViewTests` class, after `test_results_view_shows_vote_tally`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
.venv/bin/python manage.py test admin_panel.tests.ElectionResultsViewTests -v 2
```

Expected: both new tests FAIL — the template has no "Winner" text anywhere yet.

- [ ] **Step 3: Call `mark_winners` in the view**

In `admin_panel/views.py`, add this import near the top, alongside the existing `from elections.models import Contestant, Election, Position` line:

```python
from elections.results import mark_winners
```

Then update `ElectionResultsView.get_context_data` (the tally query stays identical — only wrap it):

```python
class ElectionResultsView(AdminRequiredMixin, DetailView):
    model = Election
    template_name = "admin_panel/election_results.html"
    context_object_name = "election"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Kept in sync with voting.views.results_view's tally query — update
        # both if the ordering/annotation logic ever changes.
        context["tallies"] = mark_winners(
            Contestant.objects.filter(election=self.object)
            .select_related("position")
            .annotate(vote_count=Count("votes"))
            .order_by("position__title", "position_id", "-vote_count")
        )
        return context
```

- [ ] **Step 4: Add the winner badge to the template**

Replace the contents of `admin_panel/templates/admin_panel/election_results.html` with:

```html
{% extends "admin_panel/base.html" %}

{% block title %}{{ election.session }} Results · NAIFT Admin{% endblock %}

{% block content %}
<h1 class="font-display text-3xl text-brand-purple mb-2">{{ election.session }} Results</h1>
<p class="text-brand-black/70 mb-8">Status: {{ election.get_status_display }}.</p>

{% regroup tallies by position as position_list %}
{% for position in position_list %}
    <h2 class="font-display text-2xl text-brand-black mb-3">{{ position.grouper }}</h2>
    <ul class="mb-8 space-y-2">
        {% for contestant in position.list %}
            <li class="flex justify-between items-center border-b border-brand-black/10 py-2">
                <span class="flex items-center gap-2">
                    {{ contestant.name }}{% if contestant.alias %} ({{ contestant.alias }}){% endif %}
                    {% if contestant.is_winner %}
                        <span class="text-xs font-display uppercase tracking-wide bg-brand-purple text-brand-white px-2 py-0.5 rounded-full">Winner</span>
                    {% endif %}
                </span>
                <span class="font-display text-brand-purple">{{ contestant.vote_count }} vote{{ contestant.vote_count|pluralize }}</span>
            </li>
        {% endfor %}
    </ul>
{% empty %}
    <p>No contestants have been added for this election yet.</p>
{% endfor %}
{% endblock %}
```

- [ ] **Step 5: Run the full `admin_panel` app test suite**

```bash
.venv/bin/python manage.py test admin_panel -v 2
```

Expected: `OK`, 34 tests (the pre-existing 32, plus these 2 new tests).

- [ ] **Step 6: Commit**

```bash
git add admin_panel/views.py admin_panel/templates/admin_panel/election_results.html admin_panel/tests.py
git commit -m "Show winner badge on the admin Election Results view"
```

---

### Task 4: Past Executives section on the public Executive page

**Files:**
- Modify: `executives/views.py` (the `CurrentExecutiveView` class)
- Modify: `executives/templates/executives/current.html`
- Test: `executives/tests.py` (add to the existing `CurrentExecutiveViewTests` class)

- [ ] **Step 1: Write the failing tests**

Add these two tests inside the existing `CurrentExecutiveViewTests` class (after `test_only_current_executives_are_listed`):

```python
    def test_past_executives_render_grouped_and_grayscale(self):
        response = self.client.get(reverse("executives:current"))
        self.assertContains(response, "Past Executive — 2025/2026")
        self.assertContains(response, "John Smith")
        self.assertContains(response, "grayscale")

    def test_no_past_executives_shows_no_past_section(self):
        self.past.delete()
        response = self.client.get(reverse("executives:current"))
        self.assertNotContains(response, "Past Executives")
```

(`setUp` already creates `self.past` — an `is_current=False` Executive with `session="2025/2026"` — so these tests need no new fixtures.)

- [ ] **Step 2: Run the tests to verify they fail**

```bash
.venv/bin/python manage.py test executives.tests.CurrentExecutiveViewTests -v 2
```

Expected: both new tests FAIL — there's no Past Executives section in the template yet, so `test_past_executives_render_grouped_and_grayscale` fails on the missing content, and `test_no_past_executives_shows_no_past_section` fails too (there's no "Past Executives" text to be absent from in the first place — but `assertNotContains` passing vacuously would be a false pass; run it and confirm it's not accidentally green for the wrong reason by checking Step 2's actual output, not just trusting "FAIL" blindly).

- [ ] **Step 3: Add the `past` context variable**

Replace `executives/views.py` with:

```python
from django.views.generic import ListView

from .models import Executive


class CurrentExecutiveView(ListView):
    template_name = "executives/current.html"
    context_object_name = "executives"

    def get_queryset(self):
        return Executive.objects.filter(is_current=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["past"] = Executive.objects.filter(is_current=False).order_by("-session")
        return context
```

- [ ] **Step 4: Add the Past Executives section to the template**

Replace the contents of `executives/templates/executives/current.html` with:

```html
{% extends "core/base.html" %}
{% load static %}

{% block title %}Current Executive · NAIFT{% endblock %}

{% block content %}
<section class="px-6 py-16 max-w-5xl mx-auto" data-aos="fade-up">
    <img src="{% static 'image/executives-graduation.jpg' %}" alt="University graduation ceremony" class="w-full h-56 md:h-72 object-cover rounded-lg shadow-lg mb-8" data-aos="zoom-in">

    <h1 class="font-display text-4xl text-brand-purple mb-8">Current Executive</h1>

    {% regroup executives by session as session_list %}
    {% for session in session_list %}
        <h2 class="font-display text-2xl text-brand-black mb-4">{{ session.grouper }}</h2>
        <div class="grid sm:grid-cols-2 md:grid-cols-3 gap-6 mb-10">
            {% for executive in session.list %}
                <div class="border border-brand-purple/20 rounded-lg p-5 text-center" data-aos="fade-up">
                    {% if executive.photo %}
                        <img src="{{ executive.photo.url }}" alt="{{ executive.name }}" class="h-32 w-32 rounded-full object-cover mx-auto mb-3">
                    {% endif %}
                    <h3 class="font-display text-lg text-brand-black">{{ executive.name }}</h3>
                    <p class="text-brand-purple">{{ executive.position }}</p>
                </div>
            {% endfor %}
        </div>
    {% empty %}
        <p class="text-lg">No current executive has been published yet.</p>
    {% endfor %}

    {% if past %}
        <h2 class="font-display text-2xl text-brand-black mb-4 mt-12">Past Executives</h2>
        {% regroup past by session as past_session_list %}
        {% for session in past_session_list %}
            <h3 class="font-display text-xl text-brand-black/70 mb-4">Past Executive — {{ session.grouper }}</h3>
            <div class="grid sm:grid-cols-2 md:grid-cols-3 gap-6 mb-10">
                {% for executive in session.list %}
                    <div class="border border-brand-black/10 rounded-lg p-5 text-center grayscale" data-aos="fade-up">
                        {% if executive.photo %}
                            <img src="{{ executive.photo.url }}" alt="{{ executive.name }}" class="h-32 w-32 rounded-full object-cover mx-auto mb-3">
                        {% endif %}
                        <h3 class="font-display text-lg text-brand-black">{{ executive.name }}</h3>
                        <p class="text-brand-purple">{{ executive.position }}</p>
                    </div>
                {% endfor %}
            </div>
        {% endfor %}
    {% endif %}
</section>
{% endblock %}
```

- [ ] **Step 5: Run the full `executives` app test suite**

```bash
.venv/bin/python manage.py test executives -v 2
```

Expected: `OK`, 5 tests (the pre-existing 3, plus these 2 new tests).

- [ ] **Step 6: Commit**

```bash
git add executives/views.py executives/templates/executives/current.html executives/tests.py
git commit -m "Add grayscale Past Executives section to the public Executive page"
```

---

### Task 5: Final verification

**Files:** none (verification only)

- [ ] **Step 1: Run the entire test suite**

```bash
.venv/bin/python manage.py test
```

Expected: `OK` (114 tests total — 8 in `core`, 5 in `executives`, 14 in `elections`, 34 in `admin_panel`, 53 in `voting`).

- [ ] **Step 2: Run Django's system check**

```bash
.venv/bin/python manage.py check
```

Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 3: Manual smoke test**

No automated test substitutes for actually looking at this in a browser.

1. Ensure Postgres is running: `docker compose up -d db`.
2. Start the Tailwind watcher: `.venv/bin/python manage.py tailwind start` (or `tailwind build` once for a static check).
3. Start the dev server: `.venv/bin/python manage.py runserver`.
4. In the admin dashboard, create at least one `is_current=True` and one `is_current=False` Executive (different sessions).
5. Visit `/executives/` (or wherever `executives:current` is mounted) — confirm "Current Executive" renders as before, and a "Past Executives" section appears below it with grayscale cards, grouped by session, each group labeled "Past Executive — {session}".
6. Delete all past executives via the admin dashboard and reload — confirm the "Past Executives" heading disappears entirely (no empty-state clutter).
7. Create an election with one unopposed position and one contested (2+ contestant) position; cast enough votes to make one contestant a clear winner. Publish results.
8. Visit the public results page (`/vote/results/` or the specific election's results URL) — confirm the unopposed contestant shows a "Winner" badge, and the clear winner in the contested position shows one too, while the loser doesn't.
9. Visit the same election's admin Results page — confirm the identical winner badges appear there too.
10. Cast votes to produce an exact tie in another position, republish/recheck — confirm neither tied contestant shows a "Winner" badge, on both results pages.

- [ ] **Step 4: Stop services**

```bash
lsof -ti:8000 -sTCP:LISTEN | xargs -r kill
```

(Leave Postgres running via `docker compose` — shared infrastructure.)

---

## Self-Review Notes

- **Spec coverage:** "Executive page — Current + Past sections" → Task 4 (new `past` context variable, grayscale + session-grouped template section, empty-state suppression). "Winner badge — shared helper, no new query" → Task 1 (the `mark_winners` helper itself, tested in isolation against unopposed/strict-win/tie/multi-position scenarios) plus Tasks 2 and 3 (wiring it into each of the two existing results views/templates without touching the tally query). All of the spec's testing bullets map to a concrete test: current-executives regression is covered by the pre-existing `test_only_current_executives_are_listed` (untouched by this plan); past-executives grouped/grayscale/labeled by `test_past_executives_render_grouped_and_grayscale`; empty-state suppression by `test_no_past_executives_shows_no_past_section`; `mark_winners`'s four behaviors (unopposed/zero-vote win, strict win, exact tie, multi-position independence) each get their own test in Task 1; both results views' "mix of a clear-winner position and a tied position in the same election" bullet is covered by each view's paired `..._for_unopposed_contestant` / `..._for_tied_position` tests in Tasks 2 and 3.
- **Type/name consistency:** `mark_winners(tallies)` signature, the `.is_winner` attribute name, and the `position_id`-based grouping logic are defined once in Task 1 and referenced identically (never re-derived) by Tasks 2 and 3. The `past` context variable name and `grayscale` CSS class are used identically between Task 4's view and template steps.
- **No placeholders:** every step has complete, runnable code; the 114-test final count is the explicit sum (104 baseline + 4 Task-1 + 2 Task-2 + 2 Task-3 + 2 Task-4 tests), not an unexplained assertion.
