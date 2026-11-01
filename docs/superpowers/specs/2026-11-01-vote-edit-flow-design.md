# Vote Edit Flow — Design Spec

**Date:** 2026-11-01
**Sub-project:** 2 of 5 in the post-launch improvements backlog (CLAUDE.md "Updates")

## Context

Builds on the already-shipped `voting` app (student login, vote wizard, review/submit, results). Currently, once a student has clicked through all positions and reached the Review page, there is no way back — the review list is plain text, and `wizard_step`'s form has only a single "Next" button with no indication of a prior pick. CLAUDE.md asks for the ability to revise a selection from the Review page before final submission.

## Scope

- Review page: each position entry becomes a link back to that position's wizard step.
- Wizard step: when revisited in this way, shows the student's current pick pre-selected, and replaces the single "Next" button with Previous / Next / Submit.
- First-pass voting (a student who hasn't yet reached Review) is completely unchanged.

Out of scope: changing the atomic vote-submission logic itself (still lives exclusively in `wizard_review`), allowing edits after a vote has already been submitted (the existing "You Have Voted" lockout is untouched and correct), any change to the eligibility gate in `vote_entry`.

## Architecture

### Deriving edit mode (no new flag)

`wizard_step` is only ever reachable with every position already holding a session pick in one specific way: the student clicked a position link from the Review page (first-pass voting always lands on the *first unanswered* position, by construction of `vote_entry`'s routing — so by definition, if all positions already have picks, this visit didn't come from the normal forward flow). This means edit mode can be derived purely from existing session state, with no new flag to keep in sync:

```python
positions = list(Position.objects.filter(contestants__election=election).distinct().order_by("title"))
picks = request.session.get("vote_picks", {})
is_edit_mode = bool(positions) and all(str(p.id) in picks for p in positions)
```

When `is_edit_mode` is `True`, the view also computes:
- `current_pick_id` — `picks.get(str(position.id))`, used to pre-check the matching radio button.
- `previous_position` / `next_position` — the adjacent entries in `positions` relative to the current one (by index in the same `title`-ordered list `vote_entry` already uses), `None` at either boundary.

### Multi-action form

The wizard step's form gets three named submit buttons instead of one, present only in edit mode:

```html
<button type="submit" name="nav" value="previous">Previous</button>  {# hidden if no previous_position #}
<button type="submit" name="nav" value="next">Next</button>          {# hidden if no next_position #}
<button type="submit" name="nav" value="submit">Submit</button>      {# always shown in edit mode #}
```

Whichever button is clicked is read from `request.POST.get("nav")`. In all three cases, the view first saves the (possibly changed) `contestant` pick into `session["vote_picks"]` exactly as it already does today — only the post-save redirect target changes:

- `nav == "previous"` → redirect to `voting:wizard_step` for `previous_position`
- `nav == "next"` → redirect to `voting:wizard_step` for `next_position`
- `nav == "submit"` → redirect to `voting:wizard_review`

Outside edit mode (first-pass voting), the form is unchanged — a single "Next" button, POST saves the pick and redirects to `voting:vote_entry` exactly as today, which continues to route to the next unanswered position or to Review once complete. This existing, already-reviewed code path is untouched.

### Review page becomes clickable

In `wizard_review.html`, each position entry is wrapped in a link to `{% url 'voting:wizard_step' contestant.position.pk %}`, landing the student back on that step — which, per the derivation above, will automatically render in edit mode since all positions still hold picks at that point.

### Submission stays single-sourced

"Submit" from an edit-mode wizard step does not write any `Vote` rows itself — it saves the current pick and navigates to `wizard_review`, where the existing atomic, fully-validated submission logic (completeness check, cross-election constraint, single transaction) remains the only code path that ever creates a `Vote`. This was an explicit design decision to avoid duplicating that already carefully-built and reviewed logic across two views.

## Testing

- First-pass voting (not yet in edit mode): existing behavior and existing tests are unaffected — single "Next" button, routes through `vote_entry` as today.
- Edit mode triggers correctly: visiting a `wizard_step` URL directly when all positions already have picks renders Previous/Next/Submit; the radio input matching the student's current pick for that position is pre-checked.
- Previous/Next correctly navigate to the adjacent position and persist whatever pick was selected on the page being left (including if it was changed).
- Previous is absent on the first position in the ordered list; Next is absent on the last.
- Submit (from an edit-mode step) saves the current pick and redirects to `wizard_review`, which still shows the updated full selection — not a direct vote write.
- Clicking a position link from `wizard_review` lands on that position's `wizard_step` in edit mode (not first-pass mode).
