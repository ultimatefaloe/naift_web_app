# Vote Integrity, Election-Status Visibility & Student Management — Design Spec

**Date:** 2026-11-03
**Scope:** Single combined spec covering 4 related backlog items from CLAUDE.md's "Update" section (deliberately bundled into one spec per explicit direction, rather than split into separate sub-project specs as prior backlog rounds were).

## Context

This is the second post-launch backlog round for the NAIFT election app, following the first 5-item round (Election Lifecycle Controls, Vote Edit Flow, Executive & Results Display Polish, Admin Dashboard Statistics, Navigation & Cohesion Pass), all already shipped on `dev`. CLAUDE.md's "Update" section now lists 5 items; investigation during brainstorming found:
- One item (student CSV management) is genuinely new — no web UI exists today, only a CLI `seed_students` command.
- One item (confirm dialog → modal) is a UI upgrade to the already-shipped Election Lifecycle Controls action buttons.
- Three items (vote carryover, results-page election-awareness, voting-link visibility) are all facets of the same underlying gap: nothing in this app currently varies what's shown/counted based on `Election.status` in the way the business actually needs.

A real, confirmed data-integrity bug was found during investigation (see Section 1) — not just a UX polish item.

## Section 1: Vote-carryover bug fix

### The bug

`Contestant.election` is an editable field on `ContestantUpdateView` (`fields = ["name", "alias", "manifesto", "position", "election", "photo"]`). If an admin "re-elects" the same person for a new session by **editing** an existing Contestant row's `election` field (pointing it at the new `Election`) rather than creating a fresh Contestant, every vote-tally query in the app silently over-counts: they all do `Count("votes")` on the Contestant with no election filter, so the count includes every `Vote` ever cast for that Contestant row — including votes from the *previous* election it belonged to.

Confirmed affected call sites (all three build the same unfiltered annotation):
- `voting/views.py::results_view`
- `admin_panel/views.py::ElectionResultsView.get_context_data`
- `admin_panel/views.py::DashboardView.get_context_data` (the live chart's tally loop)

### Fix — two parts

**1. Query fix (corrects the problem immediately, including already-corrupted data):**

Change the annotation in all three call sites from:
```python
.annotate(vote_count=Count("votes"))
```
to:
```python
.annotate(vote_count=Count("votes", filter=Q(votes__election=F("election"))))
```
This counts only votes whose `Vote.election` matches the Contestant's own current `election` — correct regardless of whether a Contestant's `election` was ever reassigned, and correct for the normal case too (since `Vote.contestant`/`Vote.election` are always consistent for contestants created normally).

**2. Root-cause prevention (stops this from recurring):**

Remove `"election"` from `ContestantUpdateView.fields`, so a Contestant's election becomes fixed at creation time — editing a Contestant can change their name/alias/manifesto/position/photo, but never which election they belong to. This forces the correct admin workflow (create a new Contestant row for a new election) rather than allowing the data-corrupting reassignment at all. `ContestantCreateView` is unaffected — `election` remains settable at creation.

### Testing

- A Contestant reassigned to a new election (simulating pre-existing corrupted data) shows a vote count reflecting only that new election's votes, not the old election's.
- `ContestantUpdateView`'s form no longer includes an `election` field; POSTing an `election` value to the update endpoint has no effect on the Contestant's actual `election`.
- Regression: normal single-election Contestants (the overwhelming majority of real data) still tally correctly — existing tally tests must keep passing unchanged.

## Section 2: Election-status-driven visibility

### Architecture — a context processor, not per-view duplication

A new context processor, `elections/context_processors.py::election_status(request)`, registered once in `web/settings.py`'s `TEMPLATES[0]['OPTIONS']['context_processors']` list (alongside the existing Django built-ins) — this makes its output available in **every** template render, across `core`, `voting`, and `admin_panel`, without any view needing to compute or pass it explicitly:

```python
def election_status(request):
    return {
        "voting_is_open": Election.objects.filter(status=Election.STATUS_ONGOING).exists(),
    }
```

(Only `voting_is_open` is needed as a new global flag — "is there a published election" is already answered per-page by each results view's own context, so no second global flag is introduced.)

### Where it's used

**Public site** (`core/templates/core/base.html`, `core/templates/core/home.html`):
- Desktop nav's "Vote" button, the mobile-drawer's "Vote Now" footer button, and the homepage hero/marquee "Vote now" CTAs all render only `{% if voting_is_open %}`.
- When no election is ongoing (whether `upcoming` or `ended`), these elements are simply omitted — no disabled/placeholder state, no explanatory text in their place. This matches the approved behavior: the only visible change when voting isn't open is the absence of these elements.

**Student dashboard** (`voting/templates/voting/base.html`, desktop + mobile nav):
- The "Vote" nav link (in both the desktop nav and the mobile drawer list) renders only `{% if voting_is_open %}`. "Results" and "Past Results" links are unaffected — they already have their own independent availability logic (published-results-only).

**Admin panel is explicitly unaffected**: `admin_panel/templates/admin_panel/base.html`'s nav is unchanged — admins need full access to Positions/Contestants/Elections/etc. regardless of election status, so `voting_is_open` is never checked there.

**Results page** (`voting/templates/voting/results_not_published.html`):
- Gains a conditional block: when `voting_is_open` is true, replace the generic "Check back once the election results have been published." message with "An election is currently open for voting." plus a link to `voting:login`. When `voting_is_open` is false, the existing generic message is unchanged.

### Testing

- Context processor returns `voting_is_open=True` only when an `Election` with `status=ongoing` exists; `False` for `upcoming`-only, `ended`-only, or no-elections-at-all states.
- Public home page: Vote nav link, mobile "Vote Now" button, and hero/marquee CTAs are all present when ongoing, all absent otherwise (both `upcoming` and `ended` cases).
- Student dashboard: Vote nav link (desktop + mobile) follows the same presence/absence rule; Results/Past Results links are unaffected regardless of `voting_is_open`.
- Results-not-published page: shows the "election currently open" message + login link when ongoing; shows the original generic message when not.

## Section 3: Confirm dialogs → styled modal

### Architecture

Replace the three native `onsubmit="return confirm(...)"` dialogs in `admin_panel/templates/admin_panel/election_list.html` (Start Voting / End Voting / Publish Result) with one shared, reusable confirmation modal built on the native HTML `<dialog>` element — supported in all modern browsers, requires no new JS library/CDN dependency, and matches this project's existing lightweight vanilla-JS pattern (the mobile nav drawer script).

One `<dialog id="confirm-modal">` lives once in `election_list.html`, styled with the existing Tailwind brand classes (purple/white, matching the rest of the admin panel — not browser-default chrome). Each of the 3 action buttons becomes a plain `<button type="button" data-confirm-message="..." data-confirm-form="...">` (no longer submitting directly); a small shared script (`admin_panel/templates/admin_panel/_confirm_modal_script.html`, mirroring the existing `_mobile_menu_script.html` pattern) listens for clicks on any `[data-confirm-form]` button, populates the dialog's message text, opens it via `showModal()`, and on confirm, submits the named form (looked up by its `id`, matched against the button's `data-confirm-form` value); Cancel just calls `close()`.

The 3 existing `<form>` elements (for `election_start`/`election_end`/`election_publish_results`) are unchanged structurally (still real `<form method="post">` with `{% csrf_token %}`) — only their trigger button changes from `type="submit"` with an inline `onsubmit` to `type="button"` wired to the shared modal.

### Testing

- Each of the 3 action buttons opens the modal with its own correct message text (reusing the existing `election.session|escapejs`-escaped text already proven safe from the earlier XSS fix in this same file).
- Confirming submits the correct underlying form (verified by checking the resulting `Election.status`/`is_results_published` change, same assertions the existing `ElectionActionViewTests` already make — this is a presentation-layer change only, the POST endpoints and their server-side validation are completely unchanged).
- Cancel closes the dialog without submitting (no state change).

## Section 4: Student Management admin page

### Architecture

A new CRUD section in `admin_panel`, modeled on the existing Position/Contestant/Election list+form patterns:

- **`StudentListView`** (`ListView`): paginated via Django's built-in `paginate_by = 25` (consistent with introducing pagination for the first time in this app — no other list view paginates yet, since none has needed it before now), with optional query-param filters:
  - `?matric_number=` — case-insensitive partial match (`icontains`) against `matric_number`.
  - `?level=` — exact match against the `level` choices.
  - `?sort=` — `asc`/`desc` toggle for alphabetical-by-name ordering (default: ascending by `last_name, first_name`).
- **`StudentCreateView`** / **`StudentUpdateView`**: standard `CreateView`/`UpdateView`, fields `first_name`, `last_name`, `matric_number`, `level` — no `modified_by`/audit trail (consistent with the original voting-dashboard design decision that `Student` wasn't in-scope for DB-enforced audit, same as `Contestant`/`Executive`).
- **`StudentDeleteView`**: standard confirm-delete view, but overrides `form_valid` (or `post`) to catch `django.db.models.ProtectedError` (raised by `Vote.student`'s `on_delete=PROTECT` when the student has already voted) and re-render the confirm page with an error message instead of letting it propagate as an uncaught 500.
- **CSV bulk upload**: a form on the `StudentListView` page (file input + submit), posting to a new `StudentCSVUploadView`. Reuses the existing `seed_students` management command's row-processing logic — that logic is extracted into a shared function, `voting/csv_import.py::import_students(rows)`, returning a summary (`created`, `updated`, `skipped` counts plus per-row skip reasons). Both `seed_students` (CLI) and `StudentCSVUploadView` (web) call this same function, so there is exactly one implementation of "match by matric number, create or update name/level, validate via `clean_fields()`, skip and report malformed rows" — not two.
  - On an existing-student match (by `matric_number`), only `first_name`/`last_name`/`level` are updated; `matric_number` itself is never modified by the importer (it's the match key).
  - After upload, the page shows the same create/update/skip summary the CLI command already reports via `self.stdout`/`self.stderr`.

### Testing

- List view: pagination works (page 2 shows the next page of results, not a duplicate of page 1); each filter (`matric_number`, `level`) narrows results correctly; combining filters intersects correctly; sort toggles ascending/descending alphabetical order.
- Create/Update: standard CRUD round-trip (create persists, update persists, both redirect to the list).
- Delete: a student with no votes deletes successfully; a student with an existing `Vote` is NOT deleted and the response shows a friendly error (no 500, no traceback).
- CSV upload: a new matric number creates a new `Student`; an existing matric number updates only name/level (matric number itself unchanged even if the CSV row's matric-number column differs — match is still by the original stored value, since that's the row Django's ORM looks up); a malformed row (bad matric-number format, missing column) is skipped and reported, not a crash; the created/updated/skipped counts shown on the page match the actual DB changes.
- `import_students` is tested once, directly, independent of both call sites (CLI and web), then both `seed_students`'s existing tests and new `StudentCSVUploadView` tests confirm each caller gets the same correct behavior from the shared function.

## Out of scope

- Any change to how `Position`/`Election`/`Executive` CRUD works (only `Contestant`'s editable-fields list changes, per Section 1).
- Pagination for any other existing list view (Position/Contestant/Election) — only the new Student list gets it, since it's the first list view in this app likely to have enough real-world rows to need it (a department's full student roster vs. a handful of positions/contestants/elections).
- Any change to the `Election.STATUS_*` enum itself or how status transitions are validated — Section 2 only *reads* `status`, it doesn't change how/when it's set.
- A "Clear filter" UI affordance on the Contestant list (noted as a possible follow-up in the previous backlog round's code review) — not requested here, not added.
