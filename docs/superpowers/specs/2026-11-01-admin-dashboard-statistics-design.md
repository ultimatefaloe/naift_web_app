# Admin Dashboard Statistics — Design Spec

**Date:** 2026-11-01
**Sub-project:** 4 of 5 in the post-launch improvements backlog (CLAUDE.md "Updates")

## Context

Builds on the already-shipped `admin_panel.views.DashboardView` (currently 4 static stat cards: position/contestant/executive counts, current-election status text) and the `elections`/`executives` apps. CLAUDE.md asks for a live chart of the currently-ongoing election's voting, broken down per position/contestant, plus a summary of the current Executive on the same dashboard.

## Scope

- A per-position bar chart (Chart.js, via CDN) of live vote counts for whichever `Election` currently has `status = ongoing`. No chart at all (replaced by a short message) when no election is ongoing.
- A small "Current Executive" summary widget on the dashboard, independent of election state.
- Unopposed positions render as a single-bar chart — no special-casing needed, same principle already proven for the winner-badge logic in sub-project 3 of this backlog.

Out of scope: auto-refreshing/live-polling the chart (snapshot on page load/reload only, per explicit decision below); any change to the existing 4 stat cards; any change to how `Election`/`Executive`/`Contestant` data is created or edited elsewhere in the admin dashboard.

## Architecture

### Ongoing-election lookup and tallies

`DashboardView.get_context_data` gains:

```python
ongoing_election = Election.objects.filter(status=Election.STATUS_ONGOING).order_by("-id").first()
```

This is the same "ongoing, not just non-ended" lookup already used by `voting.views.get_ongoing_election()` — deliberately not reusing the dashboard's existing `current_election` stat-card lookup, since that one includes `upcoming` elections too (fine for a status label, wrong for "live voting chart," which should only appear while voting is actually open).

When `ongoing_election` is `None`, the chart section doesn't render at all; the template shows a short "No voting currently in progress" message in its place.

When present, tallies are computed exactly as the existing results views already do:

```python
Contestant.objects.filter(election=ongoing_election)
    .select_related("position")
    .annotate(vote_count=Count("votes"))
    .order_by("position__title", "position_id", "-vote_count")
```

This is grouped by position in the view (not the template) and passed to the template as a Python structure, serialized to JSON per-position via Django's built-in `{{ value|json_script:"id" }}` template tag — the safe, standard way to hand server data to a small inline script, avoiding any hand-rolled JSON/HTML escaping.

### Current Executive widget

```python
current_executives = Executive.objects.filter(is_current=True)
```

Added to the same `get_context_data`, entirely independent of election state — this widget renders regardless of whether there's an ongoing election.

### Chart rendering

Chart.js is loaded via CDN in `admin_panel/templates/admin_panel/dashboard.html`, following the exact pattern already established for AOS in `core/templates/core/base.html` — a pinned version with a verified `integrity`/`crossorigin` SRI hash (computed and checked against the actual downloaded file at implementation time, not guessed, the same way AOS's hash was verified during the public-website sub-project).

One `<canvas>` element per position, each paired with a small inline `<script>` block that reads that position's `json_script`-embedded data and initializes a Chart.js bar chart: contestant names on the x-axis, live vote counts as bar heights. An unopposed position (one contestant) produces a chart with exactly one bar — no conditional logic needed in the view or template to special-case it, since Chart.js renders a single-category bar chart the same way it renders a multi-category one.

## Testing

- No ongoing election (none exists, or the only elections are `upcoming`/`ended`): dashboard renders with no chart section and the "No voting currently in progress" message; the Current Executive widget still renders.
- Ongoing election with a contested position (2+ contestants): chart data matches real `Vote` row counts for that position.
- Ongoing election with an unopposed position: renders without error as a single-bar chart.
- Current Executive widget shows exactly the `is_current=True` `Executive` records, regardless of whether an election is ongoing, upcoming, or ended.
