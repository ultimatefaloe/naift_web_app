# Print Result Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an admin-only "Print Result" action that opens a formatted, standalone printable document of an election's full results (NAIFT + department logos, association/committee header, per-position tally with winners marked).

**Architecture:** A new `AdminRequiredMixin`-gated `DetailView` (`ElectionResultsPrintView`) at `elections/<pk>/results/print/`, server-side gated to only published elections (`Election.objects.filter(is_results_published=True)` — a 404, not just a hidden button, for unpublished ones). It reuses the same tally query already used by `ElectionResultsView`/`voting.views.results_view`/`DashboardView`. The template is a standalone HTML document (no `{% extends %}`, no admin nav/chrome) with its own inline print-friendly CSS and an on-page "Print" button (`window.print()`) that's hidden via `@media print` so it never appears in the actual printed output.

**Tech Stack:** Django 6.1 views/templates, browser-native print/Save-as-PDF (no new PDF library).

---

## Context for the implementer

- Repo: `/home/ultimate/Desktop/UltimateIntelliForge.org/naift_web_app`, branch `dev` (already checked out — continue on it).
- Spec: `docs/superpowers/specs/2026-11-04-print-result-design.md` (read it before starting).
- Postgres runs via docker-compose. Verify with `docker ps` first; if the daemon isn't reachable, run `systemctl --user start docker-desktop` then `docker compose up -d db`, and poll `docker ps` until the db container shows `(healthy)`.
- Full test suite currently has **183 tests, 17 known pre-existing failures** — verified by actually running `.venv/bin/python manage.py test` immediately before writing this plan. These 17 failures are caused by a large, unrelated, uncommitted template redesign happening concurrently elsewhere in this repo (not part of this plan, not something to fix): `core.tests.HomeMarqueeTests` (2), `executives.tests.CurrentExecutiveViewTests` (2), `admin_panel.tests.AdminFormBackLinkTests` (5), `admin_panel.tests.AdminNavTests.test_nav_includes_public_site_link` (1), `admin_panel.tests.ElectionActionViewTests.test_election_list_shows_start_button_for_upcoming_election` (1), `admin_panel.tests.ElectionCRUDTests.test_update_form_prepopulates_existing_datetimes` (1), `admin_panel.tests.ElectionResultsViewTests.test_results_view_shows_vote_tally` (1), `voting.tests.ResultsViewTests` (2), `voting.tests.WizardStepEditModeTests` (2). If this set has grown further by the time you run the suite, that's expected (the redesign is ongoing) — do NOT attempt to fix any of them. Just confirm no NEW failures appear beyond whatever the current set is, and that your own new tests pass.
- `admin_panel/views.py` already imports everything this plan needs: `Count, F, ProtectedError, Q` (from `django.db.models`), `Contestant, Election, Position` (from `elections.models`), `mark_winners` (from `elections.results`), `DetailView` (from `django.views.generic`), `AdminRequiredMixin`. No new imports are needed anywhere in this plan.
- `admin_panel/tests.py` already imports `User`, `AdminProfile`, `Election`, `Position`, `Contestant`, `Student`, `Vote`, `TestCase`, `reverse` — no new imports needed.
- Static logo files already exist: `static/image/naifts_logo.jpeg` (NAIFT logo) and `static/image/ift_logo.jpeg` (Department of Information Technology logo) — both already used elsewhere in the app (`voting/base.html`, `core/base.html`).
- Current `admin_panel/views.py::ElectionResultsView` (for reference — do not modify its own logic, only `election_results.html`'s template in Task 2):
  ```python
  class ElectionResultsView(AdminRequiredMixin, DetailView):
      model = Election
      template_name = "admin_panel/election_results.html"
      context_object_name = "election"

      def get_context_data(self, **kwargs):
          context = super().get_context_data(**kwargs)
          context["tallies"] = mark_winners(
              Contestant.objects.filter(election=self.object)
              .select_related("position")
              .annotate(vote_count=Count("votes", filter=Q(votes__election=F("election"))))
              .order_by("position__title", "position_id", "-vote_count")
          )
          return context
  ```
- Out of scope: any change to the public voting results page; a server-generated downloadable PDF file; any signature/approval workflow; making the print view reachable before results are published.

---

### Task 1: `ElectionResultsPrintView` — new view, URL, and standalone print template

**Files:**
- Modify: `admin_panel/views.py` (new `ElectionResultsPrintView`)
- Modify: `admin_panel/urls.py` (1 new route)
- Create: `admin_panel/templates/admin_panel/election_results_print.html`
- Test: `admin_panel/tests.py` (new class `ElectionResultsPrintViewTests`, appended at the end of the file)

- [ ] **Step 1: Write the failing tests**

Append to `admin_panel/tests.py`:

```python
class ElectionResultsPrintViewTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username="admin_print_results", password="pass12345")
        self.admin_profile = AdminProfile.objects.create(user=self.admin_user, is_admin=True)
        self.client.force_login(self.admin_user)
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
            first_name="John", last_name="Smith", matric_number="2026/1/00001CF", level="300"
        )
        Vote.objects.create(
            student=student, election=self.election, position=self.position, contestant=self.contestant
        )

    def test_returns_200_for_published_election(self):
        response = self.client.get(reverse("admin_panel:election_results_print", args=[self.election.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin_panel/election_results_print.html")

    def test_returns_404_for_unpublished_election(self):
        self.election.is_results_published = False
        self.election.save()
        response = self.client.get(reverse("admin_panel:election_results_print", args=[self.election.pk]))
        self.assertEqual(response.status_code, 404)

    def test_returns_404_for_nonexistent_election(self):
        response = self.client.get(reverse("admin_panel:election_results_print", args=[999999]))
        self.assertEqual(response.status_code, 404)

    def test_shows_formatted_header_content(self):
        response = self.client.get(reverse("admin_panel:election_results_print", args=[self.election.pk]))
        self.assertContains(response, "Nigerian Association of Information Technology Students")
        self.assertContains(response, "Electoral Committee (ELECOM)")
        self.assertContains(response, "Result from the Electoral Committee")

    def test_shows_real_tally_data(self):
        response = self.client.get(reverse("admin_panel:election_results_print", args=[self.election.pk]))
        self.assertContains(response, "President")
        self.assertContains(response, "Jane Doe")
        self.assertContains(response, "Winner")

    def test_does_not_extend_admin_base_template(self):
        response = self.client.get(reverse("admin_panel:election_results_print", args=[self.election.pk]))
        # admin_panel/base.html's header always renders a Logout form for an
        # authenticated admin — its absence here proves this page is genuinely
        # standalone, not accidentally extending the admin chrome.
        self.assertNotContains(response, "Logout")
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
.venv/bin/python manage.py test admin_panel.tests.ElectionResultsPrintViewTests -v 2
```

Expected: all 6 FAIL — `reverse("admin_panel:election_results_print", ...)` raises `NoReverseMatch`, since neither the view, URL, nor template exist yet.

- [ ] **Step 3: Add `ElectionResultsPrintView`**

In `admin_panel/views.py`, add this class anywhere after `ElectionResultsView`:

```python
class ElectionResultsPrintView(AdminRequiredMixin, DetailView):
    model = Election
    template_name = "admin_panel/election_results_print.html"
    context_object_name = "election"

    def get_queryset(self):
        return Election.objects.filter(is_results_published=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["tallies"] = mark_winners(
            Contestant.objects.filter(election=self.object)
            .select_related("position")
            .annotate(vote_count=Count("votes", filter=Q(votes__election=F("election"))))
            .order_by("position__title", "position_id", "-vote_count")
        )
        return context
```

(`get_queryset` filtering to `is_results_published=True` is what makes an unpublished or nonexistent election's print URL 404 — Django's `DetailView.get_object()` calls `get_object_or_404`-equivalent logic against this queryset.)

- [ ] **Step 4: Add the URL route**

In `admin_panel/urls.py`, add this route right after the existing `election_results` route:

```python
    path(
        "elections/<int:pk>/results/print/",
        views.ElectionResultsPrintView.as_view(),
        name="election_results_print",
    ),
```

- [ ] **Step 5: Create the standalone print template**

```html
{% load static %}
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{{ election.session }} Results · NAIFT ELECOM</title>
    <style>
        body {
            font-family: Georgia, 'Times New Roman', serif;
            color: #111;
            max-width: 800px;
            margin: 0 auto;
            padding: 2rem;
        }
        .header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            border-bottom: 3px double #111;
            padding-bottom: 1rem;
            margin-bottom: 1.5rem;
        }
        .header img {
            height: 72px;
            width: 72px;
            object-fit: cover;
            border-radius: 50%;
        }
        .header-text {
            flex: 1;
            text-align: center;
        }
        .header-text p {
            margin: 0.15rem 0;
        }
        .header-text .org-name {
            font-size: 1.1rem;
            font-weight: bold;
        }
        .header-text .committee-name {
            font-size: 1rem;
        }
        .header-text .tagline {
            font-size: 0.9rem;
            font-style: italic;
        }
        h1.doc-title {
            text-align: center;
            font-size: 1.3rem;
            margin: 1.5rem 0;
            text-decoration: underline;
        }
        .position-section {
            margin-bottom: 1.5rem;
        }
        .position-title {
            font-size: 1.1rem;
            font-weight: bold;
            border-bottom: 1px solid #111;
            margin-bottom: 0.5rem;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            text-align: left;
            padding: 0.4rem 0.5rem;
            border-bottom: 1px solid #ccc;
        }
        .winner-row {
            font-weight: bold;
        }
        .print-button {
            display: block;
            margin: 0 auto 2rem;
            padding: 0.5rem 1.5rem;
            font-size: 1rem;
            cursor: pointer;
        }
        @media print {
            .print-button {
                display: none;
            }
        }
    </style>
</head>
<body>
    <button type="button" class="print-button" onclick="window.print()">Print</button>

    <div class="header">
        <img src="{% static 'image/naifts_logo.jpeg' %}" alt="NAIFT logo">
        <div class="header-text">
            <p class="org-name">Nigerian Association of Information Technology Students</p>
            <p class="committee-name">Electoral Committee (ELECOM)</p>
            <p class="tagline">Result from the Electoral Committee</p>
        </div>
        <img src="{% static 'image/ift_logo.jpeg' %}" alt="Department of Information Technology logo">
    </div>

    <h1 class="doc-title">{{ election.session }} Election Results</h1>

    {% regroup tallies by position as position_list %}
    {% for position in position_list %}
        <div class="position-section">
            <p class="position-title">{{ position.grouper }}</p>
            <table>
                <thead>
                    <tr>
                        <th>Candidate</th>
                        <th>Votes</th>
                    </tr>
                </thead>
                <tbody>
                    {% for contestant in position.list %}
                        <tr class="{% if contestant.is_winner %}winner-row{% endif %}">
                            <td>
                                {{ contestant.name }}{% if contestant.alias %} ({{ contestant.alias }}){% endif %}
                                {% if contestant.is_winner %} &mdash; Winner{% endif %}
                            </td>
                            <td>{{ contestant.vote_count }}</td>
                        </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    {% empty %}
        <p>No contestants have been added for this election yet.</p>
    {% endfor %}
</body>
</html>
```

- [ ] **Step 6: Run the tests to verify they pass**

```bash
.venv/bin/python manage.py test admin_panel.tests.ElectionResultsPrintViewTests -v 2
```

Expected: all 6 pass.

- [ ] **Step 7: Run the full `admin_panel` app test suite**

```bash
.venv/bin/python manage.py test admin_panel -v 2
```

Expected: your 6 new tests pass. Report the exact pass/fail breakdown — the known pre-existing failures listed in "Context for the implementer" above should be the only other ones present (same names, no new ones).

- [ ] **Step 8: Commit**

```bash
git add admin_panel/views.py admin_panel/urls.py admin_panel/templates/admin_panel/election_results_print.html admin_panel/tests.py
git commit -m "Add standalone Print Result view for published election results"
```

---

### Task 2: "Print Result" link on the admin Election Results page

**Files:**
- Modify: `admin_panel/templates/admin_panel/election_results.html`
- Test: `admin_panel/tests.py` (add to the existing `ElectionResultsViewTests` class)

- [ ] **Step 1: Write the failing tests**

Add to the existing `ElectionResultsViewTests` class in `admin_panel/tests.py` (after its last existing test):

```python
    def test_results_view_shows_print_link_when_published(self):
        self.election.is_results_published = True
        self.election.save()
        response = self.client.get(reverse("admin_panel:election_results", args=[self.election.pk]))
        self.assertContains(
            response, f'href="{reverse("admin_panel:election_results_print", args=[self.election.pk])}"'
        )

    def test_results_view_hides_print_link_when_not_published(self):
        response = self.client.get(reverse("admin_panel:election_results", args=[self.election.pk]))
        self.assertNotContains(response, "Print Result")
```

(`ElectionResultsViewTests.setUp` creates `self.election` without setting `is_results_published`, which defaults to `False` — so the second test's election is unpublished by default, correctly exercising the "hidden" case.)

- [ ] **Step 2: Run the tests to verify they fail**

```bash
.venv/bin/python manage.py test admin_panel.tests.ElectionResultsViewTests -v 2
```

Expected: `test_results_view_shows_print_link_when_published` FAILS (no such link exists yet). `test_results_view_hides_print_link_when_not_published` PASSES already (vacuously — there's no "Print Result" text anywhere yet, which happens to be correct for this specific case, but it becomes a meaningful test once the link exists after Step 3 — confirm it's STILL passing after your change, not just before).

- [ ] **Step 3: Add the link to `election_results.html`**

In `admin_panel/templates/admin_panel/election_results.html`, find this block (inside `.page-header__sub`):

```html
            {% if election.is_results_published %}
                <a href="{% url 'voting:results_detail' election.pk %}" class="text-brand-purple hover:underline">
                    View public results →
                </a>
            {% else %}
                <span class="text-neutral-500">Not yet published to the public site.</span>
            {% endif %}
```

Add the new link right after the existing "View public results →" link, inside the same `{% if election.is_results_published %}` branch:

```html
            {% if election.is_results_published %}
                <a href="{% url 'voting:results_detail' election.pk %}" class="text-brand-purple hover:underline">
                    View public results →
                </a>
                <a href="{% url 'admin_panel:election_results_print' election.pk %}" target="_blank" class="text-brand-purple hover:underline">
                    Print Result →
                </a>
            {% else %}
                <span class="text-neutral-500">Not yet published to the public site.</span>
            {% endif %}
```

(Everything else in this template stays exactly as it already is — this is the only change.)

- [ ] **Step 4: Run the full `admin_panel` app test suite**

```bash
.venv/bin/python manage.py test admin_panel -v 2
```

Expected: `OK` for your 8 new tests total across both tasks (the 2 from this task, plus Task 1's 6). Report the exact pass/fail breakdown — same known pre-existing failures only, no new ones.

- [ ] **Step 5: Commit**

```bash
git add admin_panel/templates/admin_panel/election_results.html admin_panel/tests.py
git commit -m "Add Print Result link to the admin Election Results page"
```

---

### Task 3: Final verification

**Files:** none (verification only)

- [ ] **Step 1: Run the entire test suite**

```bash
.venv/bin/python manage.py test
```

Expected: 191 tests total (the pre-existing 183, plus these 8 new tests), with only the known pre-existing failures present (same names as listed in "Context for the implementer" — report the actual current set, since the concurrent redesign may have grown or shrunk it since this plan was written; just confirm no NEW failures exist beyond whatever that set currently is).

- [ ] **Step 2: Run Django's system check**

```bash
.venv/bin/python manage.py check
```

Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 3: Manual smoke test**

No automated test substitutes for actually looking at the printed output in a browser.

1. Ensure Postgres is running: `docker compose up -d db`.
2. Start the Tailwind watcher: `.venv/bin/python manage.py tailwind start` (or `tailwind build` once for a static check) — note the print template itself doesn't use Tailwind, but the admin Election Results page it links from does.
3. Start the dev server: `.venv/bin/python manage.py runserver`.
4. Log into the admin dashboard, create an election with at least one contested position, cast votes via the student flow, then End Voting and Publish Result.
5. Visit that election's admin Results page — confirm a "Print Result →" link now appears next to "View public results →".
6. Click it — confirm it opens in a new tab, shows the NAIFT logo on the left, department logo on the right, the 3 header lines centered between them, the election session as a title, and the full tally with the winner clearly marked.
7. Click the on-page "Print" button, open the browser's print preview — confirm the "Print" button itself does NOT appear in the preview, and the layout looks like a clean, formatted document (not a webpage with nav/sidebar).
8. Go back to an election whose results aren't published yet — confirm the "Print Result" link is absent from its admin Results page, and manually visiting the print URL for that election's pk returns a 404.

- [ ] **Step 4: Stop services**

```bash
lsof -ti:8000 -sTCP:LISTEN | xargs -r kill
```

(Leave Postgres running via `docker compose` — shared infrastructure.)

---

## Self-Review Notes

- **Spec coverage:** "New view" (server-side gated to published elections, reusing the proven tally query) → Task 1. "New template — standalone" (logos, 3-line header, body, hidden print button) → Task 1. "Trigger button on the existing results page" → Task 2. All of the spec's testing bullets map to a concrete test: 200/404-published/404-nonexistent (Task 1's first 3 tests); header content and real tally data present (Task 1's next 2 tests); standalone-not-extending-admin-chrome (Task 1's 6th test); print link shown/hidden tied to publish status (Task 2's 2 tests); tied/unopposed winner handling is inherited for free from the already-proven `mark_winners` helper, not re-tested here since no new winner-detection logic is introduced (as the spec explicitly notes).
- **Type/name consistency:** `ElectionResultsPrintView`, URL name `election_results_print`, and template path `admin_panel/election_results_print.html` are each defined once in Task 1 and referenced identically in Task 2 and Task 3 — no renamed variants.
- **No placeholders:** every step has complete, runnable code; the 191-test final count is the explicit sum (183 baseline + 6 Task-1 + 2 Task-2 tests), not an unexplained assertion.
