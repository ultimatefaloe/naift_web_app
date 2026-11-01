# Vote Edit Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a student revise a position's pick from the Review page before final submission, without touching the already-correct atomic vote-submission logic.

**Architecture:** `wizard_step`'s edit mode is derived purely from existing session state (no new flag): it's true exactly when every position for the ongoing election already has a session pick, which only happens once a student has reached Review and clicked back into a position. In edit mode the template swaps its single "Next" button for named Previous/Next/Submit buttons; the view reads `request.POST.get("nav")` to decide where to redirect after saving the (possibly changed) pick. The Review page's position entries become links back into this same view/URL.

**Tech Stack:** Django 6.1 views/templates, session-stored `vote_picks` dict, existing `voting` app test suite (`django.test.TestCase`).

---

## Context for the implementer

- Repo: `/home/ultimate/Desktop/UltimateIntelliForge.org/naift_web_app`, branch `dev` (already checked out — continue on it).
- Spec: `docs/superpowers/specs/2026-11-01-vote-edit-flow-design.md` (read it before starting — this plan implements it exactly).
- Postgres runs via docker-compose. Verify with `docker ps` first; if the daemon isn't reachable, run `systemctl --user start docker-desktop` then `docker compose up -d db`, and poll `docker ps` until the db container shows `(healthy)`.
- Full test suite currently has **95 passing tests** (core=8, executives=3, elections=10, admin_panel=32, voting=42) — this was verified by actually running `.venv/bin/python manage.py test` immediately before writing this plan, not assumed.
- Current `wizard_step` (in `voting/views.py`) only handles first-pass voting: GET renders the position's contestants with a single "Next" button; POST saves the picked contestant into `request.session["vote_picks"]` and redirects to `voting:vote_entry` (which routes to the next unanswered position, or to `voting:wizard_review` once complete). This first-pass behavior must remain completely unchanged — only new, edit-mode-only behavior is added alongside it.
- Current `wizard_review.html` renders each position's pick as plain (non-clickable) text inside a `<li>`.
- Out of scope (do not touch): the atomic vote-submission logic in `wizard_review` (still the only code path that writes `Vote` rows), the "You Have Voted" lockout, the eligibility gate in `vote_entry`.

---

### Task 1: Edit mode in `wizard_step` — pre-selected pick, Previous/Next/Submit, nav handling

**Files:**
- Modify: `voting/views.py:68-88` (the `wizard_step` function)
- Modify: `voting/templates/voting/wizard_step.html`
- Test: `voting/tests.py` (new class `WizardStepEditModeTests`, appended after the existing `WizardStepTests` class around line 277)

- [ ] **Step 1: Write the failing tests for edit-mode GET rendering**

Add this new test class to `voting/tests.py`, directly after the closing of `WizardStepTests` (after its last test, before `class ResultsViewTests`):

```python
class WizardStepEditModeTests(TestCase):
    def setUp(self):
        self.student = Student.objects.create(
            first_name="Jane", last_name="Doe", matric_number="2022/1/90976CF", level="300"
        )
        session = self.client.session
        session["student_id"] = self.student.id
        session.save()
        user = User.objects.create_user(username="admin_voting_edit", password="pass12345")
        admin_profile = AdminProfile.objects.create(user=user, is_admin=True)
        self.election = Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            status="ongoing",
            modified_by=admin_profile,
        )
        # Titles chosen so "President" sorts before "Secretary" — matches the
        # title-ordering wizard_step/vote_entry already use.
        self.position_a = Position.objects.create(title="President", modified_by=admin_profile)
        self.position_b = Position.objects.create(title="Secretary", modified_by=admin_profile)
        self.contestant_a = Contestant.objects.create(
            name="Jane Doe", manifesto="Vote for progress.", position=self.position_a, election=self.election
        )
        self.contestant_a2 = Contestant.objects.create(
            name="Amina Bello", manifesto="Vote for change.", position=self.position_a, election=self.election
        )
        self.contestant_b = Contestant.objects.create(
            name="John Roe", manifesto="Vote for stability.", position=self.position_b, election=self.election
        )
        # Every position already has a pick — this is what makes wizard_step
        # consider this an edit-mode visit rather than first-pass voting.
        session = self.client.session
        session["vote_picks"] = {
            str(self.position_a.pk): self.contestant_a.pk,
            str(self.position_b.pk): self.contestant_b.pk,
        }
        session.save()

    def test_wizard_step_in_edit_mode_preselects_current_pick(self):
        response = self.client.get(reverse("voting:wizard_step", args=[self.position_a.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'value="{self.contestant_a.pk}" required checked')
        self.assertNotContains(response, f'value="{self.contestant_a2.pk}" required checked')

    def test_first_position_in_edit_mode_has_no_previous_button(self):
        response = self.client.get(reverse("voting:wizard_step", args=[self.position_a.pk]))
        self.assertNotContains(response, 'name="nav" value="previous"')
        self.assertContains(response, 'name="nav" value="next"')
        self.assertContains(response, 'name="nav" value="submit"')

    def test_last_position_in_edit_mode_has_no_next_button(self):
        response = self.client.get(reverse("voting:wizard_step", args=[self.position_b.pk]))
        self.assertContains(response, 'name="nav" value="previous"')
        self.assertNotContains(response, 'name="nav" value="next"')
        self.assertContains(response, 'name="nav" value="submit"')

    def test_first_pass_voting_has_no_edit_mode_controls(self):
        # Drop one position's pick so the "every position already has a pick"
        # condition is false — this is what first-pass voting looks like.
        session = self.client.session
        session["vote_picks"] = {str(self.position_a.pk): self.contestant_a.pk}
        session.save()
        response = self.client.get(reverse("voting:wizard_step", args=[self.position_b.pk]))
        self.assertNotContains(response, 'name="nav"')
        self.assertContains(response, ">Next<")
```

- [ ] **Step 2: Run the new tests to verify they fail**

```bash
.venv/bin/python manage.py test voting.tests.WizardStepEditModeTests -v 2
```

Expected: `FAIL` — the current template has no `checked` logic, no `name="nav"` buttons at all, so `test_wizard_step_in_edit_mode_preselects_current_pick`, `test_first_position_in_edit_mode_has_no_previous_button`, and `test_last_position_in_edit_mode_has_no_next_button` fail; `test_first_pass_voting_has_no_edit_mode_controls` passes already (nothing to regress yet) — that's fine, it's there to lock in current behavior once the rest is built.

- [ ] **Step 3: Implement edit-mode detection and GET-side context in the view**

Replace the `wizard_step` function in `voting/views.py` (currently lines 68-88) with:

```python
@student_required
def wizard_step(request, position_id):
    election = get_ongoing_election()
    if election is None:
        return redirect("voting:vote_entry")
    if Vote.objects.filter(student=request.student, election=election).exists():
        return redirect("voting:vote_entry")
    position = get_object_or_404(Position, pk=position_id)
    contestants = position.contestants.filter(election=election)
    positions = list(Position.objects.filter(contestants__election=election).distinct().order_by("title"))
    picks = request.session.get("vote_picks", {})
    is_edit_mode = bool(positions) and all(str(p.id) in picks for p in positions)
    current_index = next((i for i, p in enumerate(positions) if p.id == position.id), None)

    if request.method == "POST":
        contestant_id = request.POST.get("contestant")
        try:
            contestant_id = int(contestant_id)
        except (TypeError, ValueError):
            raise Http404("Invalid contestant selection.")
        contestant = get_object_or_404(Contestant, pk=contestant_id, position=position, election=election)
        picks[str(position.id)] = contestant.id
        request.session["vote_picks"] = picks
        return redirect("voting:vote_entry")

    previous_position = positions[current_index - 1] if is_edit_mode and current_index else None
    next_position = (
        positions[current_index + 1]
        if is_edit_mode and current_index is not None and current_index < len(positions) - 1
        else None
    )
    return render(
        request,
        "voting/wizard_step.html",
        {
            "position": position,
            "contestants": contestants,
            "is_edit_mode": is_edit_mode,
            "current_pick_id": picks.get(str(position.id)),
            "previous_position": previous_position,
            "next_position": next_position,
        },
    )
```

(The POST branch is deliberately left exactly as it was today — nav handling is added in Step 5 below. This step only wires up GET-side edit-mode context so the template tests can pass.)

- [ ] **Step 4: Update the template to pre-select the current pick and show the right buttons**

Replace the contents of `voting/templates/voting/wizard_step.html` with:

```html
{% extends "voting/base.html" %}

{% block title %}{{ position.title }} · NAIFT Voting{% endblock %}

{% block content %}
<h1 class="font-display text-3xl text-brand-purple mb-8">{{ position.title }}</h1>

<form method="post" class="flex flex-col gap-4">
    {% csrf_token %}
    {% for contestant in contestants %}
        <label class="flex items-center gap-4 border border-brand-purple/20 rounded-lg p-4 cursor-pointer">
            <input type="radio" name="contestant" value="{{ contestant.pk }}" required{% if contestant.pk == current_pick_id %} checked{% endif %}>
            {% if contestant.photo %}
                <img src="{{ contestant.photo.url }}" alt="{{ contestant.name }}" class="h-16 w-16 rounded-full object-cover">
            {% endif %}
            <span>
                <span class="font-display text-lg">{{ contestant.name }}{% if contestant.alias %} ({{ contestant.alias }}){% endif %}</span>
                <span class="block text-sm text-brand-black/70">{{ contestant.manifesto }}</span>
            </span>
        </label>
    {% endfor %}
    {% if is_edit_mode %}
        <div class="flex gap-4">
            {% if previous_position %}
                <button type="submit" name="nav" value="previous" class="border border-brand-purple text-brand-purple px-4 py-2 rounded hover:bg-brand-purple/10">Previous</button>
            {% endif %}
            {% if next_position %}
                <button type="submit" name="nav" value="next" class="border border-brand-purple text-brand-purple px-4 py-2 rounded hover:bg-brand-purple/10">Next</button>
            {% endif %}
            <button type="submit" name="nav" value="submit" class="bg-brand-purple text-brand-white px-4 py-2 rounded hover:opacity-90">Submit</button>
        </div>
    {% else %}
        <button type="submit" class="bg-brand-purple text-brand-white px-4 py-2 rounded hover:opacity-90">Next</button>
    {% endif %}
</form>
{% endblock %}
```

- [ ] **Step 5: Run the tests again to verify the GET-side tests pass**

```bash
.venv/bin/python manage.py test voting.tests.WizardStepEditModeTests voting.tests.WizardStepTests -v 2
```

Expected: all pass. `WizardStepTests` (the pre-existing first-pass test class) must still pass unchanged — this proves the GET-side edit-mode work didn't regress first-pass voting.

- [ ] **Step 6: Write the failing tests for POST nav handling**

Add these three tests inside `WizardStepEditModeTests` (after `test_first_pass_voting_has_no_edit_mode_controls`):

```python
    def test_post_nav_next_saves_pick_and_redirects_to_next_position(self):
        response = self.client.post(
            reverse("voting:wizard_step", args=[self.position_a.pk]),
            {"contestant": self.contestant_a2.pk, "nav": "next"},
        )
        self.assertRedirects(
            response, reverse("voting:wizard_step", args=[self.position_b.pk]), fetch_redirect_response=False
        )
        self.assertEqual(self.client.session["vote_picks"][str(self.position_a.pk)], self.contestant_a2.pk)

    def test_post_nav_previous_saves_pick_and_redirects_to_previous_position(self):
        response = self.client.post(
            reverse("voting:wizard_step", args=[self.position_b.pk]),
            {"contestant": self.contestant_b.pk, "nav": "previous"},
        )
        self.assertRedirects(
            response, reverse("voting:wizard_step", args=[self.position_a.pk]), fetch_redirect_response=False
        )

    def test_post_nav_submit_saves_pick_and_redirects_to_review_without_voting(self):
        response = self.client.post(
            reverse("voting:wizard_step", args=[self.position_a.pk]),
            {"contestant": self.contestant_a2.pk, "nav": "submit"},
        )
        self.assertRedirects(response, reverse("voting:wizard_review"), fetch_redirect_response=False)
        self.assertEqual(self.client.session["vote_picks"][str(self.position_a.pk)], self.contestant_a2.pk)
        self.assertEqual(Vote.objects.count(), 0)
```

- [ ] **Step 7: Run the new tests to verify they fail**

```bash
.venv/bin/python manage.py test voting.tests.WizardStepEditModeTests -v 2
```

Expected: the three new `test_post_nav_*` tests `FAIL` — the POST branch always redirects to `voting:vote_entry` today, regardless of any `nav` value.

- [ ] **Step 8: Implement nav handling in the POST branch**

In `voting/views.py`, replace the POST branch inside `wizard_step` (the block added in Step 3) with:

```python
    if request.method == "POST":
        contestant_id = request.POST.get("contestant")
        try:
            contestant_id = int(contestant_id)
        except (TypeError, ValueError):
            raise Http404("Invalid contestant selection.")
        contestant = get_object_or_404(Contestant, pk=contestant_id, position=position, election=election)
        picks[str(position.id)] = contestant.id
        request.session["vote_picks"] = picks

        if is_edit_mode:
            nav = request.POST.get("nav")
            if nav == "previous" and current_index is not None and current_index > 0:
                return redirect("voting:wizard_step", position_id=positions[current_index - 1].id)
            if nav == "next" and current_index is not None and current_index < len(positions) - 1:
                return redirect("voting:wizard_step", position_id=positions[current_index + 1].id)
            return redirect("voting:wizard_review")

        return redirect("voting:vote_entry")
```

(Outside edit mode, behavior is byte-for-byte identical to before: save the pick, redirect to `voting:vote_entry`.)

- [ ] **Step 9: Run the full `voting` app test suite to verify everything passes**

```bash
.venv/bin/python manage.py test voting -v 2
```

Expected: `OK`, 49 tests (the pre-existing 42, plus the 7 new tests in `WizardStepEditModeTests`).

- [ ] **Step 10: Commit**

```bash
git add voting/views.py voting/templates/voting/wizard_step.html voting/tests.py
git commit -m "Add vote-edit mode to wizard_step: pre-selected pick, Previous/Next/Submit"
```

---

### Task 2: Make the Review page's position entries clickable

**Files:**
- Modify: `voting/templates/voting/wizard_review.html`
- Test: `voting/tests.py` (add to the existing `WizardReviewTests` class, and append a new small class after `WizardStepEditModeTests`)

- [ ] **Step 1: Write the failing tests**

Add this test inside the existing `WizardReviewTests` class (after `test_get_shows_selections`):

```python
    def test_review_page_links_to_each_positions_wizard_step(self):
        response = self.client.get(reverse("voting:wizard_review"))
        self.assertContains(
            response, f'href="{reverse("voting:wizard_step", args=[self.position.pk])}"'
        )
```

Add this test inside `WizardStepEditModeTests` (after `test_post_nav_submit_saves_pick_and_redirects_to_review_without_voting`) — it ties Task 1 and Task 2 together end-to-end, matching the spec's final testing requirement ("clicking a position link from `wizard_review` lands on that position's `wizard_step` in edit mode"):

```python
    def test_review_page_link_leads_to_wizard_step_in_edit_mode(self):
        review_response = self.client.get(reverse("voting:wizard_review"))
        self.assertContains(
            review_response, f'href="{reverse("voting:wizard_step", args=[self.position_a.pk])}"'
        )
        step_response = self.client.get(reverse("voting:wizard_step", args=[self.position_a.pk]))
        self.assertContains(step_response, 'name="nav" value="submit"')
```

- [ ] **Step 2: Run the new tests to verify they fail**

```bash
.venv/bin/python manage.py test voting.tests.WizardReviewTests.test_review_page_links_to_each_positions_wizard_step voting.tests.WizardStepEditModeTests.test_review_page_link_leads_to_wizard_step_in_edit_mode -v 2
```

Expected: `test_review_page_links_to_each_positions_wizard_step` fails (no `href` to `wizard_step` exists today). `test_review_page_link_leads_to_wizard_step_in_edit_mode` also fails at its first assertion for the same reason.

- [ ] **Step 3: Wrap each position entry in a link**

Replace the contents of `voting/templates/voting/wizard_review.html` with:

```html
{% extends "voting/base.html" %}

{% block title %}Review Your Vote · NAIFT Voting{% endblock %}

{% block content %}
<h1 class="font-display text-3xl text-brand-purple mb-8">Review Your Vote</h1>

<ul class="mb-8 space-y-3">
    {% for contestant in selections %}
        <li class="border border-brand-purple/20 rounded-lg p-4">
            <a href="{% url 'voting:wizard_step' contestant.position.pk %}" class="block hover:underline">
                <span class="font-display">{{ contestant.position.title }}:</span>
                {{ contestant.name }}{% if contestant.alias %} ({{ contestant.alias }}){% endif %}
            </a>
        </li>
    {% endfor %}
</ul>

<form method="post">
    {% csrf_token %}
    <button type="submit" class="bg-brand-purple text-brand-white px-4 py-2 rounded hover:opacity-90">Submit My Vote</button>
</form>
{% endblock %}
```

- [ ] **Step 4: Run the full `voting` app test suite to verify everything passes**

```bash
.venv/bin/python manage.py test voting -v 2
```

Expected: `OK`, 51 tests (49 from Task 1, plus the 2 new tests added in this task).

- [ ] **Step 5: Commit**

```bash
git add voting/templates/voting/wizard_review.html voting/tests.py
git commit -m "Make Review page position entries link back into edit mode"
```

---

### Task 3: Final verification

**Files:** none (verification only)

- [ ] **Step 1: Run the entire test suite**

```bash
.venv/bin/python manage.py test
```

Expected: `OK` (104 tests total — 8 in `core`, 3 in `executives`, 10 in `elections`, 32 in `admin_panel`, 51 in `voting`).

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
4. As an admin, create an ongoing Election with at least 2 Positions, each with 2+ Contestants.
5. Log in as a student (`/vote/login/`), vote through both positions to reach the Review page.
6. On Review, click one of the position entries — confirm it lands on that position's wizard step with the previously-picked contestant's radio already selected, and Previous/Next/Submit buttons visible instead of a single Next.
7. Change the selection and click "Next" (or "Previous" if on the last position) — confirm it saves and moves to the adjacent position, still in edit mode.
8. Click "Submit" from an edit-mode step — confirm it lands back on Review showing the updated pick, and that no vote has been recorded yet (visiting `/vote/` again should NOT show "You Have Voted").
9. Finally click "Submit My Vote" on Review — confirm the vote is recorded and `/vote/` now shows "You Have Voted".

- [ ] **Step 4: Stop services**

```bash
lsof -ti:8000 -sTCP:LISTEN | xargs -r kill
```

(Leave Postgres running via `docker compose` — shared infrastructure.)

---

## Self-Review Notes

- **Spec coverage:** "Deriving edit mode" and "Multi-action form" → Task 1 (is_edit_mode derivation, pre-selected pick, Previous/Next/Submit, nav handling). "Review page becomes clickable" → Task 2. "Submission stays single-sourced" required no new task — `wizard_review`'s atomic submission logic is untouched by both tasks, and Task 1's "submit" nav value only ever redirects to `wizard_review`, never writes a `Vote` itself (locked in by `test_post_nav_submit_saves_pick_and_redirects_to_review_without_voting`'s `Vote.objects.count() == 0` assertion). All six spec testing bullets map to a concrete test: first-pass unaffected (`test_first_pass_voting_has_no_edit_mode_controls` + the untouched `WizardStepTests` class), edit mode triggers correctly with pre-check (`test_wizard_step_in_edit_mode_preselects_current_pick`), Previous/Next persist adjacent navigation (`test_post_nav_next_...`, `test_post_nav_previous_...`), Previous/Next absence at boundaries (`test_first_position_...`, `test_last_position_...`), Submit saves-and-redirects without voting (`test_post_nav_submit_...`), and the review-link end-to-end path (`test_review_page_links_to_each_positions_wizard_step`, `test_review_page_link_leads_to_wizard_step_in_edit_mode`).
- **Type/name consistency:** `is_edit_mode`, `current_pick_id`, `previous_position`, `next_position` are named identically to the spec's own "Deriving edit mode" section and used identically between the view (Task 1, Step 3/8) and template (Task 1, Step 4). The `nav` POST key and its three values (`"previous"`/`"next"`/`"submit"`) match the spec's "Multi-action form" section exactly. `positions` is computed with the same `Position.objects.filter(contestants__election=election).distinct().order_by("title")` query `vote_entry` already uses, so index-based adjacency agrees with the ordering a student experiences during first-pass voting.
- **No placeholders:** every step has complete, runnable code; the 104-test final count is the explicit sum (95 baseline + 7 Task-1 tests + 2 Task-2 tests), not an unexplained assertion.
