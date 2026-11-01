# Admin Dashboard Statistics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show a live, per-position vote-count chart for the currently-ongoing election on the admin dashboard, plus an always-visible Current Executive summary widget.

**Architecture:** `DashboardView.get_context_data` gains an `ongoing_election` lookup (status `ongoing` specifically, not just non-ended) and, when one exists, groups the already-proven tally query into a `chart_positions` list — one dict per position, each holding contestant names/vote counts ready for `{{ ...|json_script:... }}`. The template loads Chart.js from a CDN with a verified SRI hash, renders one `<canvas>` + inline init script per position, and shows a short fallback message when no election is ongoing. A separate, independent `current_executives` context variable drives a Current Executive widget that renders regardless of election state.

**Tech Stack:** Django 6.1 views/templates, Chart.js 4.4.1 (CDN), `{{ value|json_script:"id" }}` for safe server→script data handoff.

---

## Context for the implementer

- Repo: `/home/ultimate/Desktop/UltimateIntelliForge.org/naift_web_app`, branch `dev` (already checked out — continue on it).
- Spec: `docs/superpowers/specs/2026-11-01-admin-dashboard-statistics-design.md` (read it before starting).
- Postgres runs via docker-compose. Verify with `docker ps` first; if the daemon isn't reachable, run `systemctl --user start docker-desktop` then `docker compose up -d db`, and poll `docker ps` until the db container shows `(healthy)`.
- Full test suite currently has **119 passing tests** (core=8, executives=6, elections=16, admin_panel=35, voting=54) — verified by actually running `.venv/bin/python manage.py test` immediately before writing this plan.
- The Chart.js CDN URL and SRI hash below were verified by actually downloading the file and computing its SHA-512 hash locally, then cross-checking it against cdnjs's own published API metadata (`https://api.cdnjs.com/libraries/Chart.js/4.4.1`) — both matched exactly. Do not substitute a different version or guess a hash.
- Current `admin_panel/views.py::DashboardView`:

  ```python
  class DashboardView(AdminRequiredMixin, TemplateView):
      template_name = "admin_panel/dashboard.html"

      def get_context_data(self, **kwargs):
          context = super().get_context_data(**kwargs)
          context["position_count"] = Position.objects.count()
          context["contestant_count"] = Contestant.objects.count()
          context["executive_count"] = Executive.objects.count()
          context["current_election"] = (
              Election.objects.exclude(status=Election.STATUS_ENDED).order_by("-id").first()
          )
          return context
  ```

  `Executive`, `Contestant`, `Election`, `Position`, and `Count` (from `django.db.models`) are already imported at the top of `admin_panel/views.py` — no new imports needed for Task 1.

- Current `admin_panel/templates/admin_panel/dashboard.html`:

  ```html
  {% extends "admin_panel/base.html" %}

  {% block title %}Dashboard · NAIFT Admin{% endblock %}

  {% block content %}
  <h1 class="font-display text-3xl text-brand-purple mb-8">Dashboard</h1>

  <div class="grid sm:grid-cols-2 md:grid-cols-4 gap-6 mb-10">
      <div class="border border-brand-purple/20 rounded-lg p-5 text-center">
          <p class="text-3xl font-display text-brand-purple">{{ position_count }}</p>
          <p>Positions</p>
      </div>
      <div class="border border-brand-purple/20 rounded-lg p-5 text-center">
          <p class="text-3xl font-display text-brand-purple">{{ contestant_count }}</p>
          <p>Contestants</p>
      </div>
      <div class="border border-brand-purple/20 rounded-lg p-5 text-center">
          <p class="text-3xl font-display text-brand-purple">{{ executive_count }}</p>
          <p>Executives</p>
      </div>
      <div class="border border-brand-purple/20 rounded-lg p-5 text-center">
          <p class="text-3xl font-display text-brand-purple">{% if current_election %}{{ current_election.get_status_display }}{% else %}None{% endif %}</p>
          <p>Current Election</p>
      </div>
  </div>
  {% endblock %}
  ```

- `admin_panel/tests.py` already imports `Contestant`, `Election`, `Position` (from `elections.models`), `Executive` (from `executives.models`), `Student`, `Vote` (from `voting.models`), and `AdminProfile` — no new imports needed for either test task.
- Out of scope: auto-refreshing/polling the chart (snapshot on page load only), any change to the existing 4 stat cards, any change to how `Election`/`Executive`/`Contestant` data is created or edited elsewhere.

---

### Task 1: Dashboard view — ongoing-election tallies and Current Executive context

**Files:**
- Modify: `admin_panel/views.py` (the `DashboardView` class)
- Test: `admin_panel/tests.py` (new class `DashboardStatisticsTests`, appended after the existing `DashboardAccessTests` class)

- [ ] **Step 1: Write the failing tests**

Add this new test class to `admin_panel/tests.py`, directly after `DashboardAccessTests`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
.venv/bin/python manage.py test admin_panel.tests.DashboardStatisticsTests -v 2
```

Expected: all 6 tests FAIL with `KeyError: 'ongoing_election'` / `KeyError: 'chart_positions'` / `KeyError: 'current_executives'` — none of these context keys exist yet.

- [ ] **Step 3: Implement the context additions**

Replace `DashboardView` in `admin_panel/views.py` with:

```python
class DashboardView(AdminRequiredMixin, TemplateView):
    template_name = "admin_panel/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["position_count"] = Position.objects.count()
        context["contestant_count"] = Contestant.objects.count()
        context["executive_count"] = Executive.objects.count()
        context["current_election"] = (
            Election.objects.exclude(status=Election.STATUS_ENDED).order_by("-id").first()
        )
        context["current_executives"] = Executive.objects.filter(is_current=True)

        ongoing_election = Election.objects.filter(status=Election.STATUS_ONGOING).order_by("-id").first()
        context["ongoing_election"] = ongoing_election
        chart_positions = []
        if ongoing_election is not None:
            tallies = (
                Contestant.objects.filter(election=ongoing_election)
                .select_related("position")
                .annotate(vote_count=Count("votes"))
                .order_by("position__title", "position_id", "-vote_count")
            )
            for contestant in tallies:
                if not chart_positions or chart_positions[-1]["position_id"] != contestant.position_id:
                    chart_positions.append(
                        {
                            "position_id": contestant.position_id,
                            "position_title": contestant.position.title,
                            "element_id": f"position-{contestant.position_id}-data",
                            "data": {"labels": [], "votes": []},
                        }
                    )
                chart_positions[-1]["data"]["labels"].append(contestant.name)
                chart_positions[-1]["data"]["votes"].append(contestant.vote_count)
        context["chart_positions"] = chart_positions
        return context
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
.venv/bin/python manage.py test admin_panel.tests.DashboardStatisticsTests -v 2
```

Expected: all 6 pass.

- [ ] **Step 5: Run the full `admin_panel` app test suite**

```bash
.venv/bin/python manage.py test admin_panel -v 2
```

Expected: `OK`, 41 tests (the pre-existing 35, plus these 6 new tests).

- [ ] **Step 6: Commit**

```bash
git add admin_panel/views.py admin_panel/tests.py
git commit -m "Add ongoing-election tallies and Current Executive context to the dashboard"
```

---

### Task 2: Dashboard template — live chart and Current Executive widget

**Files:**
- Modify: `admin_panel/templates/admin_panel/dashboard.html`
- Test: `admin_panel/tests.py` (new class `DashboardChartRenderingTests`, appended after `DashboardStatisticsTests`)

- [ ] **Step 1: Write the failing tests**

Add this new test class to `admin_panel/tests.py`, directly after `DashboardStatisticsTests`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
.venv/bin/python manage.py test admin_panel.tests.DashboardChartRenderingTests -v 2
```

Expected: `test_no_ongoing_election_shows_message_and_no_canvas` FAILS (no "No voting currently in progress" text exists yet — `assertNotContains(response, "<canvas")` passes vacuously, which is fine since there's genuinely no canvas anywhere yet). `test_ongoing_election_renders_canvas_per_position` FAILS (no canvas elements exist). `test_current_executive_widget_renders_executive_names` FAILS (no Current Executive section exists yet).

- [ ] **Step 3: Replace the dashboard template**

Replace the contents of `admin_panel/templates/admin_panel/dashboard.html` with:

```html
{% extends "admin_panel/base.html" %}

{% block title %}Dashboard · NAIFT Admin{% endblock %}

{% block content %}
<h1 class="font-display text-3xl text-brand-purple mb-8">Dashboard</h1>

<div class="grid sm:grid-cols-2 md:grid-cols-4 gap-6 mb-10">
    <div class="border border-brand-purple/20 rounded-lg p-5 text-center">
        <p class="text-3xl font-display text-brand-purple">{{ position_count }}</p>
        <p>Positions</p>
    </div>
    <div class="border border-brand-purple/20 rounded-lg p-5 text-center">
        <p class="text-3xl font-display text-brand-purple">{{ contestant_count }}</p>
        <p>Contestants</p>
    </div>
    <div class="border border-brand-purple/20 rounded-lg p-5 text-center">
        <p class="text-3xl font-display text-brand-purple">{{ executive_count }}</p>
        <p>Executives</p>
    </div>
    <div class="border border-brand-purple/20 rounded-lg p-5 text-center">
        <p class="text-3xl font-display text-brand-purple">{% if current_election %}{{ current_election.get_status_display }}{% else %}None{% endif %}</p>
        <p>Current Election</p>
    </div>
</div>

<h2 class="font-display text-2xl text-brand-black mb-4">Live Voting</h2>
{% if ongoing_election %}
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js" integrity="sha512-CQBWl4fJHWbryGE+Pc7UAxWMUMNMWzWxF4SQo9CgkJIN1kx6djDQZjh3Y8SZ1d+6I+1zze6Z7kHXO7q3UyZAWw==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>
    {% for position in chart_positions %}
        <div class="border border-brand-purple/20 rounded-lg p-5 mb-6">
            <h3 class="font-display text-lg text-brand-black mb-3">{{ position.position_title }}</h3>
            <canvas id="chart-{{ position.position_id }}" height="120"></canvas>
            {{ position.data|json_script:position.element_id }}
        </div>
        <script>
            (function () {
                var data = JSON.parse(document.getElementById("{{ position.element_id }}").textContent);
                new Chart(document.getElementById("chart-{{ position.position_id }}"), {
                    type: "bar",
                    data: {
                        labels: data.labels,
                        datasets: [{ label: "Votes", data: data.votes, backgroundColor: "#4C1D95" }],
                    },
                    options: { scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } },
                });
            })();
        </script>
    {% endfor %}
{% else %}
    <p class="text-lg mb-10">No voting currently in progress.</p>
{% endif %}

<h2 class="font-display text-2xl text-brand-black mb-4 mt-4">Current Executive</h2>
{% if current_executives %}
    <div class="grid sm:grid-cols-2 md:grid-cols-3 gap-4 mb-10">
        {% for executive in current_executives %}
            <div class="border border-brand-purple/20 rounded-lg p-4 text-center">
                <p class="font-display text-brand-black">{{ executive.name }}</p>
                <p class="text-brand-purple text-sm">{{ executive.position }}</p>
            </div>
        {% endfor %}
    </div>
{% else %}
    <p class="text-lg mb-10">No current executive has been published yet.</p>
{% endif %}
{% endblock %}
```

- [ ] **Step 4: Run the full `admin_panel` app test suite**

```bash
.venv/bin/python manage.py test admin_panel -v 2
```

Expected: `OK`, 44 tests (the pre-existing 41 from Task 1, plus these 3 new tests).

- [ ] **Step 5: Commit**

```bash
git add admin_panel/templates/admin_panel/dashboard.html admin_panel/tests.py
git commit -m "Render live per-position vote chart and Current Executive widget on the dashboard"
```

---

### Task 3: Final verification

**Files:** none (verification only)

- [ ] **Step 1: Run the entire test suite**

```bash
.venv/bin/python manage.py test
```

Expected: `OK` (127 tests total — 8 in `core`, 6 in `executives`, 16 in `elections`, 44 in `admin_panel`, 54 in `voting`).

- [ ] **Step 2: Run Django's system check**

```bash
.venv/bin/python manage.py check
```

Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 3: Manual smoke test**

No automated test substitutes for actually looking at a rendered chart in a browser.

1. Ensure Postgres is running: `docker compose up -d db`.
2. Start the Tailwind watcher: `.venv/bin/python manage.py tailwind start` (or `tailwind build` once for a static check).
3. Start the dev server: `.venv/bin/python manage.py runserver`.
4. Log into the admin dashboard with no ongoing election — confirm the dashboard shows "No voting currently in progress" and no chart canvases, while the 4 stat cards and Current Executive widget (if any current executives exist) still render.
5. Create an `ongoing` Election with one contested position (2+ contestants) and one unopposed position, and cast a few votes via the student voting flow.
6. Reload the dashboard — confirm a bar chart renders for each position: the contested one shows a bar per contestant with correct heights, the unopposed one shows a single bar.
7. Cast another vote, then reload the dashboard again — confirm the chart reflects the new count (snapshot-on-reload, no live polling expected).
8. Confirm the Current Executive widget shows exactly the `is_current=True` Executive records, unaffected by the election's status.
9. Open the browser's network tab and confirm the Chart.js script loads successfully (no SRI/integrity mismatch error in the console).

- [ ] **Step 4: Stop services**

```bash
lsof -ti:8000 -sTCP:LISTEN | xargs -r kill
```

(Leave Postgres running via `docker compose` — shared infrastructure.)

---

## Self-Review Notes

- **Spec coverage:** "Ongoing-election lookup and tallies" and "Chart rendering" → Task 1 (context data) + Task 2 (template/CDN/canvas). "Current Executive widget" → both tasks (context in Task 1, rendering in Task 2). "Unopposed positions render as a single-bar chart — no special-casing needed" is proven by `test_ongoing_election_with_unopposed_position_has_single_bar` (Task 1) and `test_ongoing_election_renders_canvas_per_position`'s multi-position check (Task 2) — the grouping loop in `DashboardView` naturally produces a 1-item `labels`/`votes` list for an unopposed position without any conditional branch. All of the spec's testing bullets map to a concrete test: no-ongoing-election shows no chart + message (`test_no_ongoing_election_has_no_chart_positions`, `test_no_ongoing_election_shows_message_and_no_canvas`); contested position tallies match real `Vote` counts (`test_ongoing_election_with_contested_position_has_correct_tallies`); unopposed renders without error (`test_ongoing_election_with_unopposed_position_has_single_bar`); Current Executive widget shows exactly `is_current=True` records regardless of election state (`test_current_executive_widget_shows_only_current_executives`, `test_current_executive_widget_present_regardless_of_election_state`, `test_current_executive_widget_renders_executive_names`).
- **Type/name consistency:** `ongoing_election`, `chart_positions`, `current_executives` context keys are defined once in Task 1 and referenced identically in Task 2's template. Each `chart_positions` entry's keys (`position_id`, `position_title`, `element_id`, `data`) are used consistently between the view (Task 1) and template (Task 2) — no renamed or mismatched keys.
- **No placeholders:** every step has complete, runnable code; the CDN integrity hash was verified by actual computation and cross-check (documented above), not guessed; the 127-test final count is the explicit sum (119 baseline + 6 Task-1 + 3 Task-2 tests), not an unexplained assertion.
