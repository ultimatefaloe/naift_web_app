# Election Lifecycle Controls — Design Spec

**Date:** 2026-11-01
**Sub-project:** 1 of 5 in the post-launch improvements backlog (CLAUDE.md "Updates")

## Context

All three original sub-projects (public website, admin panel, voting dashboard) are built, reviewed, and merged onto `dev`. CLAUDE.md now lists a backlog of follow-up improvements spanning several independent areas. This spec covers the first, highest-priority piece: making election status changes and result publishing a direct, one-click action instead of requiring the generic edit form, and giving the voting dashboard proper navigation (including to results, which currently has no nav entry point at all).

The rest of the backlog — vote edit flow, admin dashboard statistics, Executive/results display polish, and a navigation/cohesion pass — are separate sub-projects, each to be brainstormed and planned on their own.

## Scope

- Status-transition action buttons on the admin Election list page: "Start Voting" (upcoming → ongoing), "End Voting" (ongoing → ended), "Publish Result" (sets `is_results_published = True`).
- Update the admin Election Results view to show real per-contestant vote tallies (it currently only shows ballot composition, with a note that tallies aren't available — that note is now stale since the voting system is live).
- Add a real navigation bar to the voting dashboard's base layout: Vote, Results, Past Results, and a link back to the public site.

Out of scope (deferred to later sub-projects): backward status transitions (reverting ongoing → upcoming, etc. — still possible via the existing Edit form), winner-highlighting on any results view, the vote-edit-before-submit flow, admin dashboard charts, Executive page display changes, and the broader "app feels scattered" navigation work.

## Architecture

### Status-transition views (`admin_panel`)

Three new POST-only views, one per action, consistent with this app's existing one-view-per-action style (e.g. `PositionCreateView`/`PositionUpdateView` are already separate, not a generic parameterized form):

- `election_start(request, pk)` — only succeeds if `election.status == Election.STATUS_UPCOMING`; sets `status = STATUS_ONGOING`.
- `election_end(request, pk)` — only succeeds if `election.status == Election.STATUS_ONGOING`; sets `status = STATUS_ENDED`.
- `election_publish_results(request, pk)` — only succeeds if `election.status == Election.STATUS_ENDED` and `is_results_published` is currently `False`; sets `is_results_published = True`.

Each view validates the election's current state server-side before transitioning (so a stale page, double-submit, or direct POST can't force an invalid jump — e.g. starting an already-ended election), sets `modified_by = request.user.adminprofile` (required by the existing DB-level `NOT NULL` constraint on `Election.modified_by`), and redirects back to `admin_panel:election_list`. All three are gated by the existing `AdminRequiredMixin` pattern.

`election_list.html` gains a row-level action button per election, showing whichever single action is valid for that row's current `status`/`is_results_published` combination (at most one of: Start Voting / End Voting / Publish Result / nothing further if already published). Each button is a small `<form method="post">` with an inline `onsubmit="return confirm('...')"` guard, since these are real state changes visible to students.

Backward transitions (e.g. undoing an accidental "Start Voting") are explicitly not given buttons — an admin who needs to revert still uses the existing Edit form's status dropdown, which remains unchanged.

### Admin Election Results view — real tallies

`ElectionResultsView`/`election_results.html` (in `admin_panel`) is updated to compute tallies the same way the public voting results page already does:

```python
Contestant.objects.filter(election=election)
    .select_related("position")
    .annotate(vote_count=Count("votes"))
    .order_by("position__title", "position_id", "-vote_count")
```

(The `position_id` secondary sort is the same ordering-safety fix already proven necessary and correct in the voting app's `results_view`, to keep Django's `{% regroup %}` safe even if two positions ever share a title.) The old "ballot composition only, tallies not live yet" placeholder copy is removed, replaced with the actual vote counts per contestant. Winner-highlighting is explicitly deferred — see Out of Scope.

### Voting dashboard navigation

`voting/templates/voting/base.html`'s header currently has no nav bar at all — only a conditional Logout button when a student is logged in. This adds a real nav, present on every voting-dashboard page:

- **Vote** → `voting:vote_entry` (redirects to login if not authenticated, which is the correct existing behavior)
- **Results** → `voting:results`
- **Past Results** → `voting:results_archive`
- **a link back to the public site** → `core:home`

Built with Tailwind flex-wrap so it doesn't break on small screens — this is new UI being built now, not a retrofit of the already-shipped public-site nav (which is out of scope here).

## Testing

- `election_start`/`election_end`/`election_publish_results`: each succeeds only from its valid starting state and is rejected (no-op, or a clear error — not a silent state change) from any other state; each sets `modified_by` correctly; each redirects to the election list.
- Admin Election Results view: displayed vote counts match real `Vote` row counts for a seeded election (mirrors the existing test pattern already proven for the public results page).
- Voting nav: all four links are present and resolve correctly on a rendered voting-dashboard page.
