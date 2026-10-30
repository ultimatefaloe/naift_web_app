# Admin Panel — Design Spec

**Date:** 2026-10-30
**Sub-project:** 2 of 3 (Public website → Admin panel → Voting dashboard)

## Context

This builds on [2026-10-30-public-website-foundation-design.md](./2026-10-30-public-website-foundation-design.md), which already introduced the `core` app (public pages) and the `executives` app (`Executive` model, no CRUD UI yet). This sub-project adds the admin-facing dashboard and the shared election data model. It does not cover student login, voting, or the student-facing results page — that's sub-project 3.

## Scope

- Two-tier admin model: a single Django superuser (via the built-in `/admin/`) who can promote/demote other admins, and those other admins who use a custom-built dashboard
- `elections` app: `Position`, `Election`, `Contestant` models
- `admin_panel` app: `AdminProfile` model, custom login/auth, CRUD dashboard for Position/Contestant/Election/Executive
- Audit trail (required `modified_by` + `modified_at`) on `Position` and `Election` only
- Public homepage marquee driven by `Election.status` (touches sub-project 1's `core` app)

Out of scope: student accounts, voting, student-facing results page, past-election archive UI, manual vote-count editing.

## Architecture & Data Model

### Two-tier admin model
- The Django superuser is created the normal Django way (`createsuperuser`) and uses Django's built-in `/admin/` site only to manage `AdminProfile` records — i.e., to grant/revoke admin privileges on regular `User` accounts. No custom UI is built for this; it's infrequent and superuser-only.
- All other admins are regular `User` accounts (not Django `is_staff`/`is_superuser`) whose privilege is determined entirely by `AdminProfile.is_admin`.

### `elections` app (new)
Shared data layer, reusable by the voting dashboard in sub-project 3.

- **`Position`**
  - `title` (CharField) — e.g. "President". Global/reusable across election cycles — not tied to a specific `Election`.
  - `modified_by` (FK → `admin_panel.AdminProfile`, **required, no null/default**)
  - `modified_at` (auto_now)

- **`Election`** — represents one election cycle.
  - `session` (CharField) — e.g. "2026/2027"
  - `start_time`, `close_time` (DateTimeField) — display-only labels (shown in the marquee and dashboard); not used to gate access
  - `status` (CharField with choices: `upcoming`, `ongoing`, `ended`) — admin-set directly, the sole source of truth for voting access and marquee state. No time-based auto-transition logic anywhere, specifically to avoid server/client clock-drift bugs.
  - `is_results_published` (BooleanField, default `False`) — admin-set independently of `status`; controls when the student-facing results page (sub-project 3) shows this election's tally.
  - `modified_by` (FK → `admin_panel.AdminProfile`, **required, no null/default**)
  - `modified_at` (auto_now)

- **`Contestant`**
  - `name` (CharField)
  - `alias` (CharField) — "popularly known as"
  - `photo` (ImageField)
  - `manifesto` (TextField)
  - `position` (FK → `Position`)
  - `election` (FK → `Election`) — scopes each candidacy to exactly one cycle, so a student running in two different years gets two separate `Contestant` records, and historical results/candidate lists stay simple filters rather than requiring joins through `Vote`.

No audit trail on `Contestant` (not selected for audit scope).

### `admin_panel` app (new)
- **`AdminProfile`** — OneToOne → `User`, `is_admin` (BooleanField). Managed exclusively via Django's built-in `/admin/` by the superuser.
- Custom login/logout views, styled with the site's design system (not Django's default admin login).
- `admin_required` decorator/mixin: checks `request.user.is_authenticated and hasattr(request.user, 'adminprofile') and request.user.adminprofile.is_admin`. Applied to every dashboard view.
- CRUD dashboard views/templates for `Position`, `Contestant`, `Election`, and `Executive` (the latter from sub-project 1's `executives` app — CRUD was deliberately deferred there for this sub-project).

### Audit enforcement mechanism
`modified_by` on `Position` and `Election` is a non-nullable FK with no default value. Any attempt to save a row without a valid `AdminProfile` fails at the database constraint level (`IntegrityError`), not merely via application-level form validation. Every dashboard view in `admin_panel` is responsible for setting `modified_by = request.user.adminprofile` before calling `.save()`.

## Admin Dashboard Pages

- **Login** — custom page, gated by `admin_required` logic (rejects authenticated-but-non-admin users too).
- **Dashboard home** — overview: current election status, counts of positions/contestants/executives.
- **Positions** — list, create, edit, delete.
- **Contestants** — list, create, edit, delete; form includes a position dropdown and image upload.
- **Executives** — list, create, edit, delete (operates on sub-project 1's `Executive` model).
- **Election** — create/edit form (session, start/close time labels, status dropdown, results-published toggle); a read-only results view showing per-contestant vote tallies for the selected election (view-only — no manual count editing, per your decision that "manage result" means viewing the computed tally, not editing it).

## Election Marquee (public homepage integration)

Touches sub-project 1's `core` app (`HomeView` / `base.html`), since it depends on the `Election` model introduced in this sub-project:

- No `Election` record exists, or the most recent one has `status = ended` → marquee is hidden entirely.
- Most recent `Election.status = upcoming` → marquee/carousel shows an announcement with session, start time, and close time.
- Most recent `Election.status = ongoing` → marquee shows a live "Voting Ongoing" banner with a CTA (link to the future voting dashboard), replacing the "upcoming" announcement.
- Exactly one marquee state is shown at a time, driven by the most recent non-`ended` `Election` record.

## Testing

- `AdminProfile`/auth: a request from a user with `is_admin=False` (or no `AdminProfile` at all) is rejected by every dashboard view; a request from a true admin succeeds.
- `Position`/`Election`: a `.save()` attempt without `modified_by` raises `IntegrityError`, confirming the DB-level constraint actually holds (not just app-level validation).
- CRUD round-trips: create/edit/delete for Position, Contestant, Election, Executive via the dashboard views.
- Marquee: view-level tests asserting correct hidden/upcoming/ongoing rendering for each `Election.status` value.

## Open items for future sub-projects

- Student model (seeded: first name + matric number), login flow (sub-project 3)
- `Vote` model, one-vote-per-student-per-position enforcement, vote submission flow (sub-project 3)
- Student-facing results page gated by `Election.is_results_published` (sub-project 3)
- Past-election results archive by session/year (sub-project 3), enabled by `Contestant`/`Election` already being scoped per cycle in this spec
