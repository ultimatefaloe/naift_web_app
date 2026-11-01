# Executive & Results Display Polish — Design Spec

**Date:** 2026-11-01
**Sub-project:** 3 of 5 in the post-launch improvements backlog (CLAUDE.md "Updates")

## Context

Builds on the already-shipped `executives` app (public Current Executive page) and both results views: `voting.views.results_view` (public) and `admin_panel.views.ElectionResultsView` (admin — gaining real vote tallies in sub-project 1 of this backlog, "Election Lifecycle Controls"). This sub-project covers two independent, mostly-visual changes bundled together because they're both small display polish: showing past executives (currently entirely hidden from the public site) and marking the winning contestant on results pages.

## Scope

- Public Executive page: add a "Past Executives" section (grayscale, grouped by session, labeled) below the existing "Current Executive" section.
- A "Winner" badge on the highest-vote contestant per position, on both the public voting results page and the admin Election Results view.

Out of scope: any change to how executives are created/edited in the admin dashboard (already shipped, unaffected), any change to the underlying vote-tallying query itself (already correct, from sub-project 1 of this backlog and the original voting-dashboard build).

## Architecture

### Executive page — Current + Past sections

`executives.views.CurrentExecutiveView` (a `ListView`) is extended to also provide a `past` queryset in context: `Executive.objects.filter(is_current=False).order_by("-session")`. The `current` queryset (`is_current=True`) is unchanged.

`executives/templates/executives/current.html` gains a second section below the existing "Current Executive" one:
- Heading: "Past Executives"
- `{% regroup past by session as past_session_list %}`, same pattern already used for the current section
- Each executive card renders with Tailwind's `grayscale` filter class, and the section/group heading reads "Past Executive — {{ session }}" to make the distinction from the current section unambiguous at a glance.
- If there are no past executives, that section doesn't render at all (no empty-state clutter on a brand-new department site).

### Winner badge — shared helper, no new query

Both results views already build a `tallies` queryset: `Contestant` objects annotated with `vote_count`, ordered by `position__title, position_id, -vote_count` (this exact query and ordering is already proven correct — see the voting-dashboard build, and sub-project 1 of this backlog applies the same pattern to the admin view). Because of that ordering, the highest-vote contestant in each position group is already first.

A new shared helper, `elections/results.py::mark_winners(tallies)`:

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

This lives in the `elections` app (both `voting` and `admin_panel` already depend on it, so this doesn't introduce new cross-app coupling) and does a single pass over data both views already have in memory — no additional database query.

Both `voting.views.results_view` and `admin_panel.views.ElectionResultsView` call `mark_winners(tallies)` before passing `tallies` to their templates. Both `results.html` (public) and `election_results.html` (admin) render a small "Winner" badge/label next to a contestant's name when `contestant.is_winner` is true.

## Testing

- Executive page: current executives render exactly as before (regression); past executives render in a separate, grayscale, session-grouped section labeled "Past Executive"; a department with zero past-executive records shows no empty "Past Executives" section at all.
- `mark_winners`: a single contestant in a position (unopposed) is marked winner regardless of vote count, including zero; a contestant with strictly more votes than everyone else in their position is marked winner; an exact tie for the highest count in a position results in no one marked winner; multiple positions in one `tallies` list are evaluated independently of each other.
- Both results views: the winner badge appears only on the correct contestant's card/row, verified against a mix of a clear-winner position and a tied position in the same election.
