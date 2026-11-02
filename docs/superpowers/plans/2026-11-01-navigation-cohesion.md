# Navigation & Cohesion Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce the "scattered, hard to navigate" feel of the admin panel: back links on every add/edit form, filterable+cross-linked Contestant/Position/Election lists, and two links bridging the admin and public zones.

**Architecture:** Three independent, purely additive changes layered onto already-shipped CRUD views/templates: (1) a consistent `← Back to {List}` link on 5 templates, (2) optional `?election=`/`?position=` query-param filtering on `ContestantListView` plus matching cross-links from the Election/Position list rows, (3) an admin-nav link to the public site and a conditional "View Public Results" link on the admin Election Results page. None of these change any existing CRUD/action logic or URL structure — only add links and one optional filter.

**Tech Stack:** Django 6.1 views/templates, existing Tailwind utility classes, query-string filtering on a `ListView`.

---

## Context for the implementer

- Repo: `/home/ultimate/Desktop/UltimateIntelliForge.org/naift_web_app`, branch `dev` (already checked out — continue on it).
- Spec: `docs/superpowers/specs/2026-11-01-navigation-cohesion-design.md` (read it before starting).
- Postgres runs via docker-compose. Verify with `docker ps` first; if the daemon isn't reachable, run `systemctl --user start docker-desktop` then `docker compose up -d db`, and poll `docker ps` until the db container shows `(healthy)`.
- Full test suite currently has **128 passing tests** (core=8, executives=6, elections=16, admin_panel=44, voting=54) — verified by actually running `.venv/bin/python manage.py test` immediately before writing this plan.
- `admin_panel/tests.py` already imports `User`, `SimpleUploadedFile`, `TestCase`, `override_settings`, `reverse`, `Contestant`, `Election`, `Position`, `Executive`, `Student`, `Vote`, `AdminProfile` — no new imports needed for any test task below.
- Confirm-delete pages (`position_confirm_delete.html` etc.) already have an equivalent "Cancel" link — leave them completely unchanged, they're explicitly out of scope.
- Out of scope: any redesign of the three separate base layouts (`core`, `admin_panel`, `voting`) themselves; any change to list views' existing columns/actions beyond the links described here; breadcrumb trails.

---

### Task 1: Back links on admin add/edit forms and the Election Results view

**Files:**
- Modify: `admin_panel/templates/admin_panel/position_form.html`
- Modify: `admin_panel/templates/admin_panel/contestant_form.html`
- Modify: `admin_panel/templates/admin_panel/executive_form.html`
- Modify: `admin_panel/templates/admin_panel/election_form.html`
- Modify: `admin_panel/templates/admin_panel/election_results.html`
- Test: `admin_panel/tests.py` (new class `AdminFormBackLinkTests`, appended after the existing `ElectionActionViewTests` class, at the end of the file)

- [ ] **Step 1: Write the failing tests**

Append this test class to the end of `admin_panel/tests.py`:

```python
class AdminFormBackLinkTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username="admin_backlinks", password="pass12345")
        self.admin_profile = AdminProfile.objects.create(user=self.admin_user, is_admin=True)
        self.client.force_login(self.admin_user)

    def test_position_form_links_back_to_position_list(self):
        response = self.client.get(reverse("admin_panel:position_create"))
        self.assertContains(response, f'href="{reverse("admin_panel:position_list")}"')

    def test_contestant_form_links_back_to_contestant_list(self):
        response = self.client.get(reverse("admin_panel:contestant_create"))
        self.assertContains(response, f'href="{reverse("admin_panel:contestant_list")}"')

    def test_executive_form_links_back_to_executive_list(self):
        response = self.client.get(reverse("admin_panel:executive_create"))
        self.assertContains(response, f'href="{reverse("admin_panel:executive_list")}"')

    def test_election_form_links_back_to_election_list(self):
        response = self.client.get(reverse("admin_panel:election_create"))
        self.assertContains(response, f'href="{reverse("admin_panel:election_list")}"')

    def test_election_results_links_back_to_election_list(self):
        election = Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            modified_by=self.admin_profile,
        )
        response = self.client.get(reverse("admin_panel:election_results", args=[election.pk]))
        self.assertContains(response, f'href="{reverse("admin_panel:election_list")}"')
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
.venv/bin/python manage.py test admin_panel.tests.AdminFormBackLinkTests -v 2
```

Expected: all 5 FAIL — none of the 5 templates has any back link yet.

- [ ] **Step 3: Add the back link to each of the 4 form templates**

Replace `admin_panel/templates/admin_panel/position_form.html` with:

```html
{% extends "admin_panel/base.html" %}

{% block title %}Position · NAIFT Admin{% endblock %}

{% block content %}
<a href="{% url 'admin_panel:position_list' %}" class="text-brand-purple hover:underline block mb-4">&larr; Back to Positions</a>
<h1 class="font-display text-3xl text-brand-purple mb-8">{% if object %}Edit{% else %}Add{% endif %} Position</h1>

<form method="post" class="flex flex-col gap-4 max-w-md">
    {% csrf_token %}
    {{ form.as_p }}
    <button type="submit" class="bg-brand-purple text-brand-white px-4 py-2 rounded hover:opacity-90">Save</button>
</form>
{% endblock %}
```

Replace `admin_panel/templates/admin_panel/contestant_form.html` with:

```html
{% extends "admin_panel/base.html" %}

{% block title %}Contestant · NAIFT Admin{% endblock %}

{% block content %}
<a href="{% url 'admin_panel:contestant_list' %}" class="text-brand-purple hover:underline block mb-4">&larr; Back to Contestants</a>
<h1 class="font-display text-3xl text-brand-purple mb-8">{% if object %}Edit{% else %}Add{% endif %} Contestant</h1>

<form method="post" enctype="multipart/form-data" class="flex flex-col gap-4 max-w-md">
    {% csrf_token %}
    {{ form.as_p }}
    <button type="submit" class="bg-brand-purple text-brand-white px-4 py-2 rounded hover:opacity-90">Save</button>
</form>
{% endblock %}
```

Replace `admin_panel/templates/admin_panel/executive_form.html` with:

```html
{% extends "admin_panel/base.html" %}

{% block title %}Executive · NAIFT Admin{% endblock %}

{% block content %}
<a href="{% url 'admin_panel:executive_list' %}" class="text-brand-purple hover:underline block mb-4">&larr; Back to Executives</a>
<h1 class="font-display text-3xl text-brand-purple mb-8">{% if object %}Edit{% else %}Add{% endif %} Executive</h1>

<form method="post" enctype="multipart/form-data" class="flex flex-col gap-4 max-w-md">
    {% csrf_token %}
    {{ form.as_p }}
    <button type="submit" class="bg-brand-purple text-brand-white px-4 py-2 rounded hover:opacity-90">Save</button>
</form>
{% endblock %}
```

Replace `admin_panel/templates/admin_panel/election_form.html` with:

```html
{% extends "admin_panel/base.html" %}

{% block title %}Election · NAIFT Admin{% endblock %}

{% block content %}
<a href="{% url 'admin_panel:election_list' %}" class="text-brand-purple hover:underline block mb-4">&larr; Back to Elections</a>
<h1 class="font-display text-3xl text-brand-purple mb-8">{% if object %}Edit{% else %}Add{% endif %} Election</h1>

<form method="post" class="flex flex-col gap-4 max-w-md">
    {% csrf_token %}
    {{ form.as_p }}
    <button type="submit" class="bg-brand-purple text-brand-white px-4 py-2 rounded hover:opacity-90">Save</button>
</form>
{% endblock %}
```

- [ ] **Step 4: Add the back link to the Election Results view**

In `admin_panel/templates/admin_panel/election_results.html`, add the back link immediately above the existing `<h1>` (leave everything else in the file exactly as-is):

```html
{% extends "admin_panel/base.html" %}

{% block title %}{{ election.session }} Results · NAIFT Admin{% endblock %}

{% block content %}
<a href="{% url 'admin_panel:election_list' %}" class="text-brand-purple hover:underline block mb-4">&larr; Back to Elections</a>
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

Expected: `OK`, 49 tests (the pre-existing 44, plus these 5 new tests).

- [ ] **Step 6: Commit**

```bash
git add admin_panel/templates/admin_panel/position_form.html admin_panel/templates/admin_panel/contestant_form.html admin_panel/templates/admin_panel/executive_form.html admin_panel/templates/admin_panel/election_form.html admin_panel/templates/admin_panel/election_results.html admin_panel/tests.py
git commit -m "Add back links to admin forms and the Election Results view"
```

---

### Task 2: Contestant list filtering and cross-links from Election/Position rows

**Files:**
- Modify: `admin_panel/views.py` (the `ContestantListView` class)
- Modify: `admin_panel/templates/admin_panel/election_list.html`
- Modify: `admin_panel/templates/admin_panel/position_list.html`
- Test: `admin_panel/tests.py` (new class `ContestantListFilterTests`, appended after `AdminFormBackLinkTests`)

Current `ContestantListView`:

```python
class ContestantListView(AdminRequiredMixin, ListView):
    model = Contestant
    template_name = "admin_panel/contestant_list.html"
    context_object_name = "contestants"
```

- [ ] **Step 1: Write the failing tests**

Append this test class to `admin_panel/tests.py`, after `AdminFormBackLinkTests`:

```python
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

    def test_election_list_links_to_filtered_contestants(self):
        response = self.client.get(reverse("admin_panel:election_list"))
        expected_url = reverse("admin_panel:contestant_list") + f"?election={self.election_a.pk}"
        self.assertContains(response, f'href="{expected_url}"')

    def test_position_list_links_to_filtered_contestants(self):
        response = self.client.get(reverse("admin_panel:position_list"))
        expected_url = reverse("admin_panel:contestant_list") + f"?position={self.position_a.pk}"
        self.assertContains(response, f'href="{expected_url}"')
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
.venv/bin/python manage.py test admin_panel.tests.ContestantListFilterTests -v 2
```

Expected: `test_no_filter_returns_all_contestants` PASSES already (unfiltered behavior is unchanged — this is the regression lock-in, not a new feature). The 3 filter tests and the 2 cross-link tests FAIL — `ContestantListView` ignores query params today, and neither `election_list.html` nor `position_list.html` has a "Contestants" link yet.

- [ ] **Step 3: Add query-param filtering to `ContestantListView`**

Replace `ContestantListView` in `admin_panel/views.py` with:

```python
class ContestantListView(AdminRequiredMixin, ListView):
    model = Contestant
    template_name = "admin_panel/contestant_list.html"
    context_object_name = "contestants"

    def get_queryset(self):
        queryset = Contestant.objects.select_related("position", "election")
        election_id = self.request.GET.get("election")
        position_id = self.request.GET.get("position")
        if election_id:
            queryset = queryset.filter(election_id=election_id)
        if position_id:
            queryset = queryset.filter(position_id=position_id)
        return queryset
```

(The added `select_related("position", "election")` closes a small, already-flagged N+1 — the list template already displays both `contestant.position` and `contestant.election` per row.)

- [ ] **Step 4: Run the filter tests to verify they pass**

```bash
.venv/bin/python manage.py test admin_panel.tests.ContestantListFilterTests -v 2
```

Expected: the 4 filter-logic tests now pass; the 2 cross-link tests still fail (templates not updated yet).

- [ ] **Step 5: Add the "Contestants" cross-link to `election_list.html`**

In `admin_panel/templates/admin_panel/election_list.html`, add a "Contestants" link into each row's actions cell, right after the existing "Results" link and before the status-action buttons:

```html
                <td class="py-2 text-right">
                    <a href="{% url 'admin_panel:election_update' election.pk %}" class="text-brand-purple hover:underline">Edit</a>
                    &middot;
                    <a href="{% url 'admin_panel:election_results' election.pk %}" class="text-brand-purple hover:underline">Results</a>
                    &middot;
                    <a href="{% url 'admin_panel:contestant_list' %}?election={{ election.pk }}" class="text-brand-purple hover:underline">Contestants</a>
                    {% if election.status == "upcoming" %}
```

(Everything from `{% if election.status == "upcoming" %}` onward — the 3 status-action buttons — stays exactly as it already is; only the new "Contestants" link is inserted above it.)

- [ ] **Step 6: Add the "Contestants" cross-link to `position_list.html`**

In `admin_panel/templates/admin_panel/position_list.html`, add a "Contestants" link into each row's actions cell, right after the existing "Edit" link and before "Delete":

```html
                <td class="py-2 text-right">
                    <a href="{% url 'admin_panel:position_update' position.pk %}" class="text-brand-purple hover:underline">Edit</a>
                    &middot;
                    <a href="{% url 'admin_panel:contestant_list' %}?position={{ position.pk }}" class="text-brand-purple hover:underline">Contestants</a>
                    &middot;
                    <a href="{% url 'admin_panel:position_delete' position.pk %}" class="text-brand-purple hover:underline">Delete</a>
                </td>
```

- [ ] **Step 7: Run the full `admin_panel` app test suite**

```bash
.venv/bin/python manage.py test admin_panel -v 2
```

Expected: `OK`, 55 tests (the pre-existing 49 from Task 1, plus these 6 new tests).

- [ ] **Step 8: Commit**

```bash
git add admin_panel/views.py admin_panel/templates/admin_panel/election_list.html admin_panel/templates/admin_panel/position_list.html admin_panel/tests.py
git commit -m "Add Contestant list filtering and cross-links from Election/Position rows"
```

---

### Task 3: Cross-zone links — admin to public site, and admin results to public results

**Files:**
- Modify: `admin_panel/templates/admin_panel/base.html` (the header `<nav>`)
- Modify: `admin_panel/templates/admin_panel/election_results.html`
- Test: `admin_panel/tests.py` (new classes `AdminNavTests`, appended after `ContestantListFilterTests`; and 2 new tests added to the existing `ElectionResultsViewTests` class)

- [ ] **Step 1: Write the failing tests**

Append this test class to `admin_panel/tests.py`, after `ContestantListFilterTests`:

```python
class AdminNavTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username="admin_nav", password="pass12345")
        AdminProfile.objects.create(user=self.admin_user, is_admin=True)
        self.client.force_login(self.admin_user)

    def test_nav_includes_public_site_link(self):
        response = self.client.get(reverse("admin_panel:dashboard"))
        self.assertContains(response, f'href="{reverse("core:home")}"')
```

Add these two tests inside the existing `ElectionResultsViewTests` class (after `test_results_view_shows_winner_badge_on_correct_contestant_in_contested_position`):

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
.venv/bin/python manage.py test admin_panel.tests.AdminNavTests admin_panel.tests.ElectionResultsViewTests -v 2
```

Expected: `test_nav_includes_public_site_link` FAILS (no such link in the nav yet). `test_results_view_shows_public_results_link_when_published` FAILS (no such link in the template yet). `test_results_view_hides_public_results_link_when_not_published` PASSES already (vacuously — there's no "View Public Results" text anywhere yet, which happens to be correct for this specific case, but don't treat that as proof of anything until the link actually exists after Step 4).

- [ ] **Step 3: Add the Public Site link to the admin nav**

In `admin_panel/templates/admin_panel/base.html`, add a "Public Site" link into the header `<nav>`, right before the Logout form:

```html
        <nav class="flex items-center gap-6 font-body">
            <a href="{% url 'admin_panel:dashboard' %}" class="hover:text-brand-purple">Dashboard</a>
            <a href="{% url 'admin_panel:position_list' %}" class="hover:text-brand-purple">Positions</a>
            <a href="{% url 'admin_panel:contestant_list' %}" class="hover:text-brand-purple">Contestants</a>
            <a href="{% url 'admin_panel:executive_list' %}" class="hover:text-brand-purple">Executives</a>
            <a href="{% url 'admin_panel:election_list' %}" class="hover:text-brand-purple">Elections</a>
            <a href="{% url 'core:home' %}" class="hover:text-brand-purple">Public Site</a>
            <form method="post" action="{% url 'admin_panel:logout' %}" class="inline">
                {% csrf_token %}
                <button type="submit" class="hover:text-brand-purple">Logout</button>
            </form>
        </nav>
```

- [ ] **Step 4: Add the conditional "View Public Results" link**

In `admin_panel/templates/admin_panel/election_results.html`, add the link right after the existing "Status: ..." paragraph, before the `{% regroup %}` block:

```html
{% extends "admin_panel/base.html" %}

{% block title %}{{ election.session }} Results · NAIFT Admin{% endblock %}

{% block content %}
<a href="{% url 'admin_panel:election_list' %}" class="text-brand-purple hover:underline block mb-4">&larr; Back to Elections</a>
<h1 class="font-display text-3xl text-brand-purple mb-2">{{ election.session }} Results</h1>
<p class="text-brand-black/70 mb-2">Status: {{ election.get_status_display }}.</p>
{% if election.is_results_published %}
    <p class="mb-8"><a href="{% url 'voting:results_detail' election.pk %}" class="text-brand-purple hover:underline">View Public Results</a></p>
{% else %}
    <div class="mb-8"></div>
{% endif %}

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

(The `<p class="text-brand-black/70 mb-2">Status: ...` line's margin changed from `mb-8` to `mb-2` so the new conditional block owns the bottom spacing instead — either branch of the `{% if %}` ends in a `mb-8` wrapper, so total spacing above the position headings stays the same as before.)

- [ ] **Step 5: Run the full `admin_panel` app test suite**

```bash
.venv/bin/python manage.py test admin_panel -v 2
```

Expected: `OK`, 58 tests (the pre-existing 55 from Task 2, plus these 3 new tests).

- [ ] **Step 6: Commit**

```bash
git add admin_panel/templates/admin_panel/base.html admin_panel/templates/admin_panel/election_results.html admin_panel/tests.py
git commit -m "Add cross-zone links: admin nav to public site, results view to public results"
```

---

### Task 4: Final verification

**Files:** none (verification only)

- [ ] **Step 1: Run the entire test suite**

```bash
.venv/bin/python manage.py test
```

Expected: `OK` (142 tests total — 8 in `core`, 6 in `executives`, 16 in `elections`, 58 in `admin_panel`, 54 in `voting`).

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
4. Log into the admin dashboard. Click "Add Position" — confirm a "← Back to Positions" link appears above the form and returns to the list when clicked. Repeat for Contestants, Executives, Elections, and an existing Election's Results page.
5. On the Elections list, click "Contestants" on one election's row — confirm it lands on the Contestant list pre-filtered to only that election's contestants. On the Positions list, click "Contestants" on one position's row — confirm it's filtered to that position instead.
6. Confirm the admin nav now shows a "Public Site" link, and clicking it lands on the public home page.
7. Visit an election's Results page where `is_results_published` is `False` — confirm no "View Public Results" link appears. Publish results for that election (via the one-click action from the Elections list), revisit its Results page — confirm "View Public Results" now appears and links to the correct public results page.

- [ ] **Step 4: Stop services**

```bash
lsof -ti:8000 -sTCP:LISTEN | xargs -r kill
```

(Leave Postgres running via `docker compose` — shared infrastructure.)

---

## Self-Review Notes

- **Spec coverage:** "Back links" → Task 1 (all 5 listed templates, confirm-delete pages explicitly left untouched per spec). "Contestant list filtering + cross-links" → Task 2 (query-param filtering with the `select_related` efficiency fix called out in the spec, plus both list-row cross-links). "Cross-zone links" → Task 3 (admin nav → public site, and the conditional "View Public Results" link gated on `is_results_published` exactly as the spec requires — avoiding the dead-end 404 the spec explicitly warns about). All of the spec's testing bullets map to a concrete test: each of the 5 back-link templates resolves correctly (`AdminFormBackLinkTests`'s 5 tests); unfiltered regression + single/combined filters (`ContestantListFilterTests`'s first 4 tests); row-level cross-links from both Election and Position lists (`ContestantListFilterTests`'s last 2 tests); admin nav's Public Site link (`AdminNavTests`); "View Public Results" present only when published (`ElectionResultsViewTests`'s 2 new tests).
- **Type/name consistency:** `election_id`/`position_id` query-param names match exactly between the view (Task 2) and both list templates' link `?election=`/`?position=` query strings. The `&larr; Back to {List}` link styling (`text-brand-purple hover:underline block mb-4`) is applied identically across all 5 Task 1 templates — no divergent styling introduced.
- **No placeholders:** every step has complete, runnable code; the 142-test final count is the explicit sum (128 baseline + 5 Task-1 + 6 Task-2 + 3 Task-3 tests), not an unexplained assertion.
