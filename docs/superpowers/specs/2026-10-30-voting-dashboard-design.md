# Voting Dashboard — Design Spec

**Date:** 2026-10-30
**Sub-project:** 3 of 3 (Public website → Admin panel → Voting dashboard)

## Context

This is the final sub-project, building on:
- [2026-10-30-public-website-foundation-design.md](./2026-10-30-public-website-foundation-design.md) — `core` app, `executives` app
- [2026-10-30-admin-panel-design.md](./2026-10-30-admin-panel-design.md) — `elections` app (`Position`, `Election`, `Contestant`), `admin_panel` app

This sub-project adds student login, the voting flow, and the results pages.

## Scope

- `Student` model (pre-seeded by admin, no self-registration)
- Session-based student login (first name + matric number, no password)
- `Vote` model with DB-level one-vote-per-position-per-election enforcement
- Vote wizard (one position per step, final review/submit)
- "You have voted" and "no active election" states
- Public results page (current election) and past-elections archive by session/year

Out of scope: admin-side manual vote-count editing (confirmed out of scope in sub-project 2), self-registration, password-based auth.

## Architecture & Data Model

### New `voting` app

- **`Student`**
  - `first_name` (CharField)
  - `last_name` (CharField)
  - `matric_number` (CharField, validated by regex `^\d{4}/\d+/\d+CF$`, e.g. `2022/1/90976CF`)
  - `level` (CharField with choices: 100, 200, 300, 400, 500)
  - Pre-seeded by admin via a management command or CSV import — no public self-registration path.

- **`Vote`**
  - `student` (FK → `Student`)
  - `election` (FK → `elections.Election`)
  - `position` (FK → `elections.Position`)
  - `contestant` (FK → `elections.Contestant`) — who the student voted for
  - `voted_at` (auto_now_add)
  - `unique_together = ("student", "election", "position")` — the DB-level mechanism that makes a second vote for the same position in the same election impossible, regardless of application logic.

### Login
- No password. Student submits first name + matric number; matched against `Student` records.
- On a match, `Student.id` is stored in the session.
- A `student_required` decorator/mixin gates voting-related views. The results pages remain public (no login required), per your decision that published results are public information.

### Voting eligibility gate
- The vote wizard is reachable only when the latest `Election.status == "ongoing"`.
- If there's no ongoing election, the student sees a distinct "no active election" message (not the same as "you have voted").
- If `Vote` rows already exist for `(student, current election)`, the wizard is replaced by a "You have voted" page instead.

### Vote wizard
- Steps through each `Position` (showing that position's `Contestant`s for the current election) one at a time.
- Unopposed positions (single contestant) are still shown as a confirm-your-choice step — no special-casing, consistent behavior across all positions.
- Picks are held in the session only as the student moves through steps — nothing is written to the database yet.
- A final review/submit step writes all `Vote` rows for the election in a single database transaction. Only this final submission is a "real" vote; abandoning the wizard beforehand leaves no record and the student can freely resume or restart later.

### Results
- Public, no login required.
- Defaults to the latest `Election` with `is_results_published = True`; shows per-contestant vote tallies grouped by position.
- A past-elections archive page lists other published `Election` sessions by session/year, each linking to its own results view.
- Hidden entirely (or shows "not yet published") while `is_results_published = False`.

## Pages

- **Login** — first name + matric number form.
- **Vote wizard** — one page per position (contestant cards/radio choices) + a final review/submit page.
- **"You have voted"** — shown in place of the wizard once `Vote` rows exist for the student's current election.
- **"No active election"** — shown when the latest `Election.status != "ongoing"`.
- **Results** — tally for the current published election, per position/contestant.
- **Past results archive** — list of previously published elections by session/year, linking to each one's results view.

## Logos

Per CLAUDE.md, the voting dashboard uses a different logo pairing from the public site: `ift_logo.jpeg` + `naifts_logo.jpeg` in the header (the public site instead uses `ift_logo.jpeg` + `fut.jpeg`, per sub-project 1's spec).

## Testing

- `Student.matric_number` regex validation: correctly formatted matric numbers are accepted; malformed ones are rejected.
- Login: a correct first-name + matric-number pair logs the student in; a mismatched pair is rejected.
- `Vote` uniqueness: a second attempt to create a `Vote` for the same `(student, election, position)` raises `IntegrityError`, confirming the DB-level one-vote guarantee actually holds.
- Wizard: picks held in session are not persisted to `Vote` until the final submit step; abandoning the wizard mid-way leaves zero `Vote` rows for that student/election.
- Eligibility gating: the vote wizard is inaccessible when `Election.status != "ongoing"`; the "You have voted" page renders correctly once `Vote` rows exist for the student's current election.
- Results: tally numbers displayed match the underlying `Vote` row counts; the results page is hidden until `Election.is_results_published = True`; the archive page lists only published past elections.

## Future enhancements (explicitly not built in any of the three sub-projects)

- Admin manual override/editing of vote counts
- Student self-registration
- Password-based or multi-factor student authentication
