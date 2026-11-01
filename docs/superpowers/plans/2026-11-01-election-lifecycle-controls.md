# Election Lifecycle Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the plan described in `docs/superpowers/specs/2026-11-01-election-lifecycle-controls-design.md`: one-click election status/publish action buttons on the admin Election list, real vote tallies on the admin Election Results view, and a navigation bar for the voting dashboard.

**Architecture:** Three new POST-only `View` subclasses in `admin_panel` (matching the app's existing `AdminRequiredMixin`-gated CBV style), one updated `DetailView` context method reusing the voting app's already-proven tally query, and one template-only change to `voting/base.html`. No new models, no new apps, no new dependencies.

**Tech Stack:** Same as the rest of the project — Django 6.1, Postgres (via docker-compose), Tailwind.

---

### Task 1: Election status action buttons

**Files:**
- Modify: `admin_panel/views.py`
- Modify: `admin_panel/urls.py`
- Modify: `admin_panel/templates/admin_panel/election_list.html`
- Modify: `admin_panel/tests.py`

- [ ] **Step 1: Write the failing tests**

Add to `admin_panel/tests.py`:

```python
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
```

- [ ] **Step 2: Run it and confirm it fails**

```bash
.venv/bin/python manage.py test admin_panel
```

Expected: `NoReverseMatch` — `admin_panel:election_start`/`election_end`/`election_publish_results` don't exist yet.

- [ ] **Step 3: Implement the views**

In `admin_panel/views.py`, update the imports at the top of the file — change:

```python
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView
```

to:

```python
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView, View
```

Add to the end of `admin_panel/views.py`:

```python
class ElectionStartView(AdminRequiredMixin, View):
    def post(self, request, pk):
        election = get_object_or_404(Election, pk=pk)
        if election.status != Election.STATUS_UPCOMING:
            messages.error(request, "This election must be upcoming to start voting.")
            return redirect("admin_panel:election_list")
        election.status = Election.STATUS_ONGOING
        election.modified_by = request.user.adminprofile
        election.save()
        return redirect("admin_panel:election_list")


class ElectionEndView(AdminRequiredMixin, View):
    def post(self, request, pk):
        election = get_object_or_404(Election, pk=pk)
        if election.status != Election.STATUS_ONGOING:
            messages.error(request, "This election must be ongoing to end voting.")
            return redirect("admin_panel:election_list")
        election.status = Election.STATUS_ENDED
        election.modified_by = request.user.adminprofile
        election.save()
        return redirect("admin_panel:election_list")


class ElectionPublishResultsView(AdminRequiredMixin, View):
    def post(self, request, pk):
        election = get_object_or_404(Election, pk=pk)
        if election.status != Election.STATUS_ENDED or election.is_results_published:
            messages.error(request, "This election must be ended and not yet published to publish results.")
            return redirect("admin_panel:election_list")
        election.is_results_published = True
        election.modified_by = request.user.adminprofile
        election.save()
        return redirect("admin_panel:election_list")
```

Using Django's base `View` class (rather than a function view) means any HTTP method other than `post` — including `GET` — automatically gets a `405 Method Not Allowed` response for free, satisfying the "POST-only" requirement without needing a separate `@require_POST` decorator; this matches the CBV-based style every other `admin_panel` view already uses.

- [ ] **Step 4: Wire the URLs**

In `admin_panel/urls.py`, add these three lines after the `elections/<int:pk>/results/` line:

```python
    path("elections/<int:pk>/start/", views.ElectionStartView.as_view(), name="election_start"),
    path("elections/<int:pk>/end/", views.ElectionEndView.as_view(), name="election_end"),
    path(
        "elections/<int:pk>/publish-results/",
        views.ElectionPublishResultsView.as_view(),
        name="election_publish_results",
    ),
```

- [ ] **Step 5: Add the action buttons to the list template**

In `admin_panel/templates/admin_panel/election_list.html`, replace:

```html
                <td class="py-2 text-right">
                    <a href="{% url 'admin_panel:election_update' election.pk %}" class="text-brand-purple hover:underline">Edit</a>
                    &middot;
                    <a href="{% url 'admin_panel:election_results' election.pk %}" class="text-brand-purple hover:underline">Results</a>
                </td>
```

with:

```html
                <td class="py-2 text-right">
                    <a href="{% url 'admin_panel:election_update' election.pk %}" class="text-brand-purple hover:underline">Edit</a>
                    &middot;
                    <a href="{% url 'admin_panel:election_results' election.pk %}" class="text-brand-purple hover:underline">Results</a>
                    {% if election.status == "upcoming" %}
                        &middot;
                        <form method="post" action="{% url 'admin_panel:election_start' election.pk %}" class="inline" onsubmit="return confirm('Start voting for {{ election.session }}?');">
                            {% csrf_token %}
                            <button type="submit" class="text-brand-purple hover:underline">Start Voting</button>
                        </form>
                    {% elif election.status == "ongoing" %}
                        &middot;
                        <form method="post" action="{% url 'admin_panel:election_end' election.pk %}" class="inline" onsubmit="return confirm('End voting for {{ election.session }}?');">
                            {% csrf_token %}
                            <button type="submit" class="text-brand-purple hover:underline">End Voting</button>
                        </form>
                    {% elif election.status == "ended" and not election.is_results_published %}
                        &middot;
                        <form method="post" action="{% url 'admin_panel:election_publish_results' election.pk %}" class="inline" onsubmit="return confirm('Publish results for {{ election.session }}? This makes them publicly visible.');">
                            {% csrf_token %}
                            <button type="submit" class="text-brand-purple hover:underline">Publish Result</button>
                        </form>
                    {% endif %}
                </td>
```

- [ ] **Step 6: Run the tests and confirm they pass**

```bash
.venv/bin/python manage.py test admin_panel
```

Expected: `OK` (31 tests — 22 existing plus these 9 new).

- [ ] **Step 7: Commit**

```bash
git add admin_panel
git commit -m "Add one-click election status/publish action buttons"
```

---

### Task 2: Real vote tallies on the admin Election Results view

**Files:**
- Modify: `admin_panel/views.py`
- Modify: `admin_panel/templates/admin_panel/election_results.html`
- Modify: `admin_panel/tests.py`

- [ ] **Step 1: Write the failing test**

Add to `ElectionResultsViewTests` in `admin_panel/tests.py` (after `test_results_view_shows_contestants_by_position`):

```python
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
```

Add the needed imports to the top of `admin_panel/tests.py` — change:

```python
from elections.models import Contestant, Election, Position
from executives.models import Executive
```

to:

```python
from elections.models import Contestant, Election, Position
from executives.models import Executive
from voting.models import Student, Vote
```

- [ ] **Step 2: Run it and confirm it fails**

```bash
.venv/bin/python manage.py test admin_panel
```

Expected: fails — the current `election_results.html` shows ballot composition only (contestant names, no vote counts), so the rendered page doesn't contain "1 vote".

- [ ] **Step 3: Update the view**

In `admin_panel/views.py`, add `Count` to the Django imports — change:

```python
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib import messages
```

to:

```python
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib import messages
from django.db.models import Count
```

Replace the `ElectionResultsView` class with:

```python
class ElectionResultsView(AdminRequiredMixin, DetailView):
    model = Election
    template_name = "admin_panel/election_results.html"
    context_object_name = "election"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["tallies"] = (
            Contestant.objects.filter(election=self.object)
            .select_related("position")
            .annotate(vote_count=Count("votes"))
            .order_by("position__title", "position_id", "-vote_count")
        )
        return context
```

This is the exact query and ordering already proven correct in `voting.views.results_view` (including the `position_id` secondary sort that keeps Django's `{% regroup %}` safe even if two positions ever share a title) — reused here rather than re-derived, so the admin and public results views can never disagree about how ties/ordering are handled.

- [ ] **Step 4: Update the template**

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
            <li class="flex justify-between border-b border-brand-black/10 py-2">
                <span>{{ contestant.name }}{% if contestant.alias %} ({{ contestant.alias }}){% endif %}</span>
                <span class="font-display text-brand-purple">{{ contestant.vote_count }} vote{{ contestant.vote_count|pluralize }}</span>
            </li>
        {% endfor %}
    </ul>
{% empty %}
    <p>No contestants have been added for this election yet.</p>
{% endfor %}
{% endblock %}
```

The old "ballot composition only... vote tallies will appear here once the voting system is live" note is removed — it's stale now that the voting system is live.

- [ ] **Step 5: Run the tests and confirm they pass**

```bash
.venv/bin/python manage.py test admin_panel
```

Expected: `OK` (32 tests — 31 existing plus this new one). The pre-existing `test_results_view_shows_contestants_by_position` still passes unchanged — it only asserts on contestant name and position title, both of which still render.

- [ ] **Step 6: Commit**

```bash
git add admin_panel
git commit -m "Show real vote tallies on the admin Election Results view"
```

---

### Task 3: Voting dashboard navigation bar

**Files:**
- Modify: `voting/templates/voting/base.html`
- Modify: `voting/tests.py`

- [ ] **Step 1: Write the failing tests**

Add to `voting/tests.py`:

```python
class VotingNavTests(TestCase):
    def test_nav_includes_vote_link(self):
        response = self.client.get(reverse("voting:login"))
        self.assertContains(response, reverse("voting:vote_entry"))

    def test_nav_includes_results_link(self):
        response = self.client.get(reverse("voting:login"))
        self.assertContains(response, reverse("voting:results"))

    def test_nav_includes_past_results_link(self):
        response = self.client.get(reverse("voting:login"))
        self.assertContains(response, reverse("voting:results_archive"))

    def test_nav_includes_public_site_link(self):
        response = self.client.get(reverse("voting:login"))
        self.assertContains(response, reverse("core:home"))
```

- [ ] **Step 2: Run it and confirm it fails**

```bash
.venv/bin/python manage.py test voting
```

Expected: all 4 new tests fail — `voting/base.html` currently has no nav bar at all, so none of these URLs appear on the rendered login page.

- [ ] **Step 3: Add the nav bar**

In `voting/templates/voting/base.html`, replace:

```html
    <header class="flex items-center justify-between px-6 py-4 border-b border-brand-black/10">
        <div class="flex items-center gap-3">
            <img src="{% static 'image/ift_logo.jpeg' %}" alt="Department of Information Technology logo" class="h-12 w-12 rounded-full object-cover">
            <img src="{% static 'image/naifts_logo.jpeg' %}" alt="NAIFT logo" class="h-12 w-12 rounded-full object-cover">
            <span class="font-display text-xl text-brand-purple">NAIFT Voting</span>
        </div>
        {% if request.session.student_id %}
        <form method="post" action="{% url 'voting:logout' %}">
            {% csrf_token %}
            <button type="submit" class="hover:text-brand-purple">Logout</button>
        </form>
        {% endif %}
    </header>
```

with:

```html
    <header class="flex items-center justify-between px-6 py-4 border-b border-brand-black/10 flex-wrap gap-4">
        <div class="flex items-center gap-3">
            <img src="{% static 'image/ift_logo.jpeg' %}" alt="Department of Information Technology logo" class="h-12 w-12 rounded-full object-cover">
            <img src="{% static 'image/naifts_logo.jpeg' %}" alt="NAIFT logo" class="h-12 w-12 rounded-full object-cover">
            <span class="font-display text-xl text-brand-purple">NAIFT Voting</span>
        </div>
        <nav class="flex items-center gap-6 font-body flex-wrap">
            <a href="{% url 'voting:vote_entry' %}" class="hover:text-brand-purple">Vote</a>
            <a href="{% url 'voting:results' %}" class="hover:text-brand-purple">Results</a>
            <a href="{% url 'voting:results_archive' %}" class="hover:text-brand-purple">Past Results</a>
            <a href="{% url 'core:home' %}" class="hover:text-brand-purple">Public Site</a>
            {% if request.session.student_id %}
            <form method="post" action="{% url 'voting:logout' %}" class="inline">
                {% csrf_token %}
                <button type="submit" class="hover:text-brand-purple">Logout</button>
            </form>
            {% endif %}
        </nav>
    </header>
```

`flex-wrap` on both the header and the nav means the logos/title and the link group wrap onto their own rows on narrow screens instead of overflowing — this is new UI being built now, not a retrofit of the already-shipped public-site nav (which stays as it is).

- [ ] **Step 4: Run the tests and confirm they pass**

```bash
.venv/bin/python manage.py test voting
```

Expected: `OK` (42 tests — 38 existing plus these 4 new).

- [ ] **Step 5: Commit**

```bash
git add voting
git commit -m "Add navigation bar to the voting dashboard"
```

---

### Task 4: Final verification

**Files:** none (verification only)

- [ ] **Step 1: Run the entire test suite**

```bash
.venv/bin/python manage.py test
```

Expected: `OK` (95 tests total — 8 in `core`, 3 in `executives`, 10 in `elections`, 32 in `admin_panel`, 42 in `voting`).

- [ ] **Step 2: Run Django's system check**

```bash
.venv/bin/python manage.py check
```

Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 3: Manual smoke test**

No automated test substitutes for actually clicking the buttons in a browser.

1. Ensure Postgres is running: `docker compose up -d db`.
2. Start the Tailwind watcher: `.venv/bin/python manage.py tailwind start` (or `tailwind build` once for a static check).
3. Start the dev server: `.venv/bin/python manage.py runserver`.
4. Log into `/dashboard/` as an admin. Create a Position, an Election (status `upcoming`), and a Contestant for that position/election.
5. On the Elections list, confirm the row shows a "Start Voting" button; click it, confirm the browser's `confirm()` dialog appears, accept it, and confirm the status updates to "Ongoing" and the button is now "End Voting".
6. Click "End Voting", confirm the dialog, confirm status becomes "Ended" and the button is now "Publish Result".
7. Click "Publish Result", confirm the dialog, confirm `Results Published?` becomes "Yes" and no further action button appears for that row.
8. Visit that election's admin Results page — confirm it shows real vote counts (seed a vote via the student voting flow first if you want a non-zero count) instead of the old "ballot composition only" message.
9. Visit `/vote/` (or any voting-dashboard page) — confirm the new nav bar shows Vote / Results / Past Results / Public Site, and that each link goes to the right place. Resize the browser narrow and confirm the header wraps instead of overflowing.

- [ ] **Step 4: Stop services**

```bash
lsof -ti:8000 -sTCP:LISTEN | xargs -r kill
```

(Leave Postgres running via `docker compose` — shared infrastructure.)

---

## Self-Review Notes

- **Spec coverage:** all three parts of `2026-11-01-election-lifecycle-controls-design.md` map directly to a task — status/publish action buttons (Task 1), real admin results tallies (Task 2), voting nav bar (Task 3). The spec's testing section is covered 1:1: each transition succeeds only from its valid starting state and sets `modified_by` (Task 1's 8 action tests); displayed tallies match real `Vote` counts (Task 2); all four nav links are present and resolve (Task 3's 4 tests).
- **Type/name consistency:** `Election.STATUS_UPCOMING`/`STATUS_ONGOING`/`STATUS_ENDED` (defined in `elections/models.py`, already used throughout the project) are referenced identically in all three new views. URL names (`election_start`, `election_end`, `election_publish_results`) are consistent between `urls.py`, the views' own `reverse`-free internal naming, and the template's `{% url %}` tags. The `tallies`/`position_id` ordering pattern in Task 2 is copied verbatim from the already-proven `voting.views.results_view`, not re-derived — eliminating any risk of the two views silently disagreeing on tie-breaking.
- **No placeholders:** every step has complete, runnable code. Task 4's arithmetic walk-through (81 baseline + 14 new = 95) is shown explicitly rather than just asserting a number, consistent with past plans in this project where an unexplained total turned out to be wrong — the explicit baseline here was re-confirmed directly against the running test suite before writing this plan.
