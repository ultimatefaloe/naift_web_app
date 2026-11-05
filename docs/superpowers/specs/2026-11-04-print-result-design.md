# Print Result — Design Spec

**Date:** 2026-11-04

## Context

The admin Election Results page (`admin_panel/views.py::ElectionResultsView`, `admin_panel/templates/admin_panel/election_results.html`) already shows the full vote tally per position, with winners marked (`contestant.is_winner`, via the existing `elections/results.py::mark_winners` helper). This feature adds a "Print Result" action, available only on that admin page (not the public voting results page), that produces a formatted, official-looking printable document of the same results — suitable for physically posting or archiving.

## Scope

- A "Print Result" button on the admin Election Results page, visible only once `election.is_results_published` is `True`.
- A new, standalone print view/template showing the full tally per position with winners marked, under a formatted header (NAIFT logo, department logo, association/committee name lines).
- Printing itself is handled by the browser's native print dialog (which also covers "Save as PDF") — no new PDF-generation library is introduced.

Out of scope: any change to the public voting results page; a server-generated downloadable PDF file (the browser's print-to-PDF already covers this); a signature/approval workflow for the printed document; printing before results are published.

## Architecture

### New view

`admin_panel/views.py` gains `ElectionResultsPrintView`, an `AdminRequiredMixin`-gated `DetailView` (or plain `View`), at a new URL `elections/<int:pk>/results/print/` (name: `election_results_print`):

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

`get_queryset` filtering to `is_results_published=True` means visiting this URL for an election whose results aren't published yet 404s — the same enforcement point used elsewhere in this app for "don't allow reaching a page before its precondition holds" (e.g. the public results view's own `is_results_published=True` filter). This is a server-side gate, not just a hidden button — a direct URL visit can't bypass it.

The tally query is the same one used by `ElectionResultsView`, `voting.views.results_view`, and `admin_panel.views.DashboardView` — all four now share the identical `Count("votes", filter=Q(votes__election=F("election")))` pattern (the vote-carryover fix from the previous sub-project). This is the 4th near-identical copy of this query; still not extracted into a shared helper, consistent with this codebase's existing "duplicated but cross-referenced" convention for this exact query (see the "Kept in sync with ..." comments already on the other three).

### New template — standalone, not extending `admin_panel/base.html`

`admin_panel/templates/admin_panel/election_results_print.html` is a complete, self-contained `<html>` document — it does **not** `{% extends %}` any existing base template, so none of the admin nav/sidebar/chrome renders. This keeps the printed output clean without fighting admin styling via media queries.

Structure:

1. **Header** — a 3-column row: NAIFT logo (`{% static 'image/naifts_logo.jpeg' %}`) on the left, department logo (`{% static 'image/ift_logo.jpeg' %}`) on the right, and centered between them:
   ```
   Nigerian Association of Information Technology Students
   Electoral Committee (ELECOM)
   Result from the Electoral Committee
   ```
2. **Document title** — the election's session (e.g. "2026/2027 Election Results").
3. **Body** — identical structure/data to the existing admin results page: `{% regroup tallies by position %}`, each position as a heading, each contestant listed with their vote count, winner visually marked (e.g. bold + "(Winner)" label — plain enough to survive black-and-white printing, since the existing page's purple-tinted winner background won't read well on a printer).
4. **On-page-only "Print" button** — calls `window.print()`, hidden via `@media print { display: none; }` so it never appears in the actual printed/PDF output.

### Trigger button on the existing results page

`election_results.html` gains, inside the existing `{% if election.is_results_published %}` block (where "View public results →" already lives), a second link:

```html
<a href="{% url 'admin_panel:election_results_print' election.pk %}" target="_blank" class="text-brand-purple hover:underline">
    Print Result →
</a>
```

`target="_blank"` opens the print view in a new tab, so the admin doesn't lose their place on the main results page.

## Testing

- `ElectionResultsPrintView` returns 200 and renders the print template for a published election; returns 404 for an unpublished one, and 404 for a nonexistent pk.
- The rendered print page contains both logo images, the 3 header lines (NAIFT full name, ELECOM full meaning, the "Result from the Electoral Committee" line), the election's session, and the real tally data (position titles, contestant names, vote counts, winner marking) — verified against actual `Vote` rows, not just that the page renders.
- The print page does NOT extend `admin_panel/base.html` (no admin nav/sidebar markup present in the response).
- The existing admin Election Results page shows the "Print Result" link only when `is_results_published=True`, and the link's `href` resolves to the correct election's print URL; the link is absent when not yet published.
- A tied position (no winner) and an unopposed position (automatic winner) both render correctly on the print page, reusing the already-proven `mark_winners` semantics — no new winner-detection logic is introduced by this feature.
