# Navigation & Cohesion Pass — Design Spec

**Date:** 2026-11-01
**Sub-project:** 5 of 5 in the post-launch improvements backlog (CLAUDE.md "Updates")

## Context

The final sub-project in this backlog, intentionally built last so there's more already in place to connect. Builds on all already-shipped `admin_panel` CRUD views/templates and the cross-zone links sub-project 1 of this backlog already adds (voting dashboard → public site). Addresses CLAUDE.md's "back button on all detail pages" request plus the broader "app feels scattered, hard to navigate" complaint, narrowed down to three concrete, confirmed pain points.

## Scope

1. Back links on every admin add/edit form and the Election Results view (confirm-delete pages already have an equivalent "Cancel" link — unchanged).
2. Optional election/position filtering on the Contestant list, with cross-links from Election and Position list rows, so admin CRUD stops feeling like disconnected silos.
3. Two cross-zone links: admin → public site home, and admin's Election Results → that election's public results page (only when published).

Out of scope: any redesign of the three separate base layouts (`core`, `admin_panel`, `voting`) themselves — they remain visually/structurally distinct by design (different logo pairings, different audiences); any change to list views' existing columns/actions beyond adding the links described here; breadcrumb trails beyond a single "back to list" link (not requested, would be meaningfully more UI to design and test than what CLAUDE.md actually asked for).

## Architecture

### 1. Back links

A consistent small link — `← Back to {List Name}` — placed immediately above the page's `<h1>`, added to:
- `admin_panel/templates/admin_panel/position_form.html` → `{% url 'admin_panel:position_list' %}`
- `admin_panel/templates/admin_panel/contestant_form.html` → `{% url 'admin_panel:contestant_list' %}`
- `admin_panel/templates/admin_panel/executive_form.html` → `{% url 'admin_panel:executive_list' %}`
- `admin_panel/templates/admin_panel/election_form.html` → `{% url 'admin_panel:election_list' %}`
- `admin_panel/templates/admin_panel/election_results.html` → `{% url 'admin_panel:election_list' %}`

Same `text-brand-purple hover:underline` styling already used for other inline links in this app, for visual consistency — not a new design element.

### 2. Contestant list filtering + cross-links

`admin_panel.views.ContestantListView.get_queryset` is extended to read optional `election`/`position` query parameters:

```python
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

(Adding `select_related` here is a small, directly-related efficiency fix since the list template already displays both `contestant.position` and `contestant.election` per row — already flagged as a minor N+1 in earlier code review, worth closing while this view is being touched anyway.)

Both filters are independently optional and combinable; omitting both preserves today's unfiltered behavior exactly (existing tests for the unfiltered list keep passing unchanged).

`election_list.html`'s row actions gain a "Contestants" link to `{% url 'admin_panel:contestant_list' %}?election={{ election.pk }}`. `position_list.html`'s row actions gain the same, linking to `?position={{ position.pk }}`.

### 3. Cross-zone links

- `admin_panel/templates/admin_panel/base.html`'s header nav gains a link to `{% url 'core:home' %}` ("Public Site"), alongside the existing Dashboard/Positions/Contestants/Executives/Elections/Logout links.
- `election_results.html` gains a "View Public Results" link to `{% url 'voting:results_detail' election.pk %}`, rendered only `{% if election.is_results_published %}` — since the public results view 404s on an unpublished election's `pk`, showing this link before publishing would be a dead end, not a shortcut.

## Testing

- Each of the 5 templates listed in "Back links" renders a link that resolves to the correct list URL.
- `ContestantListView`: no query params → unfiltered (regression); `?election=X` → only that election's contestants; `?position=X` → only that position's; both together → the intersection.
- `election_list.html` and `position_list.html` rows link to the correctly-filtered contestant list URL for that specific election/position.
- Admin nav's "Public Site" link resolves to `core:home`.
- "View Public Results" link is present and correct when `is_results_published=True`, and absent when `False`.
