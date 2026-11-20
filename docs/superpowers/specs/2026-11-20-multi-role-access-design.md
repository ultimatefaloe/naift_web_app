# Multi-Role Access System — Design Spec

## Problem

The admin dashboard currently has a single flat permission: `AdminProfile.is_admin`. Every admin account with `is_admin=True` has identical, full access to every admin view (Positions, Contestants, Executives, Students, Elections). There is no way to give someone limited access.

The ELECOM (Electoral Committee) that runs this platform has a real-world hierarchy that the system should mirror:

- **Superuser** (exactly 2 people: the developer and the department HOD) — full control, including provisioning the Chairman.
- **ELECOM Chairman** (exactly one active at a time) — full platform control except creating a Chairman or seeing Superusers.
- **ELECOM Member** — day-to-day candidate/position/student management, but no access to the Election object's lifecycle (create, start, end, publish results) or its results pages.

## Goals

- Introduce a `role` concept on admin accounts: `CHAIRMAN` or `MEMBER`. Superuser status is **not** a role value — it reuses Django's existing built-in `is_superuser` flag, which the codebase already keeps conceptually separate from the custom dashboard's own access flag.
- Enforce exactly one active Chairman at a time: promoting a new Chairman automatically demotes the previous one to Member.
- Restrict Election lifecycle views (list, create, update, start, end, publish, results, results-print) to Chairman and Superuser only. Members never see an "Elections" nav link or page.
- Members retain full CRUD on Position, Contestant (including assigning a Contestant to an election via a dropdown), Executive, and Student — i.e., everything except the Election object itself.
- Add a Committee management page where Superusers create/manage Chairmen and Members, and Chairmen create/manage Members.
- Removing someone's access means deactivating them (`is_active=False`), never hard-deleting — admin accounts are referenced by `Election.modified_by` (a `PROTECT` FK), so deletion could fail anyway, and deactivation preserves audit history.

## Non-goals

- Creating/removing Superuser accounts through this UI. There are exactly 2, provisioned via Django's own `createsuperuser` / `/admin/` outside this feature.
- Finer-grained permissions within a tier (e.g., "Member A can edit Students but not Executives"). The three tiers described above are the only granularity needed.
- Changing how voting, results publication logic, or any non-admin-facing behavior works. This is purely an access-control change.

## Data Model

`admin_panel.AdminProfile` changes:

- Add `role` — `CharField(max_length=10, choices=[("chairman", "Chairman"), ("member", "Member")], null=True, blank=True)`. `None` means "no committee role" — used for Superusers, whose authority comes entirely from `User.is_superuser`.
- Add `is_active` — `BooleanField(default=True)`. Replaces `is_admin`'s old meaning of "has dashboard access." For Chairman/Member this gates login; for Superusers it's irrelevant (they're never blocked by it — `is_superuser` always wins).
- Remove `is_admin` (migrated away — see Migration section).

Superuser accounts (`User.is_superuser=True`) get an `AdminProfile` row auto-created the first time they hit any admin view (via a check added to `AdminRequiredMixin.dispatch()`, not a signal — it only needs to exist by the time they might create/edit an `Election`, which requires `request.user.adminprofile` for `modified_by`). Their row has `role=None`, `is_active=True`.

## Permission Layering

Three mixins, each a superset of the one below it:

1. **`AdminRequiredMixin`** (existing, updated) — grants access if `request.user.is_superuser` is `True`, OR the user has an `AdminProfile` with `is_active=True` (regardless of role — auto-creating the Superuser's profile as described above happens here too). Gates: Dashboard, Position*, Contestant*, Executive*, Student* views. Scope is unchanged from today — just now recognizes roles instead of a flat flag.

2. **`ChairmanOrAboveRequiredMixin`** (new) — grants access if `request.user.is_superuser` is `True`, OR the user has an active `AdminProfile` with `role="chairman"`. Gates: `ElectionListView`, `ElectionCreateView`, `ElectionUpdateView`, `ElectionResultsView`, `ElectionResultsPrintView`, `ElectionStartView`, `ElectionEndView`, `ElectionPublishResultsView`, and the Committee page's "create Member" / "manage Member" actions.

3. **Superuser-only check** (new, simple attribute/mixin checking `request.user.is_superuser`) — gates only the Committee page's "create Chairman" action and the Superuser section of the Committee roster.

A user who fails the relevant check is redirected with an error message, same as `AdminRequiredMixin` does today.

## Committee Management Page

New page under `admin_panel/`, gated by `ChairmanOrAboveRequiredMixin` for the list view (so both Chairman and Superuser can open it — Members are redirected like any other restricted page).

**Roster visibility:**
- Superuser sees three sections: Superusers (read-only list of `User.objects.filter(is_superuser=True)` — no create/edit action here), Chairmen (active + demoted history), Members.
- Chairman sees two sections: Chairmen (themselves) and Members. The Superuser section does not render for them at all.

**Creating an admin** (one form per tier, each creates a `User` + `AdminProfile` together in a single step — username, email, password, role):
- Superuser → "Create Chairman": sets `role="chairman"`. On save, any other currently-active Chairman (`role="chairman", is_active=True`) is atomically demoted to `role="member"` (still `is_active=True`) in the same transaction, enforcing exactly one active Chairman at a time.
- Chairman or Superuser → "Create Member": sets `role="member"`. No demotion logic — unlimited Members.

**Deactivate / reactivate** (toggles `is_active`; no hard delete):
- Superuser can deactivate/reactivate any Chairman or Member.
- Chairman can deactivate/reactivate any Member — scoped to *any* Member regardless of who created them, not just ones they personally created.
- Self-deactivation is blocked at the view level (reject with an error message) to prevent accidental lockout.

Deactivated accounts (`is_active=False`) are rejected by `AdminRequiredMixin`/the login view immediately, same mechanism as today's `is_admin=False` rejection.

## Templates & Navigation

New `admin_panel/context_processors.py` (mirrors the existing `elections/context_processors.py` pattern), registered in `TEMPLATES['OPTIONS']['context_processors']`, exposing:
- `can_manage_elections` — `True` for Chairman/Superuser, `False` for Member.
- `can_manage_committee` — `True` for Chairman/Superuser, `False` for Member.

`admin_panel/base.html`'s desktop nav and mobile drawer both wrap the existing "Elections" link in `{% if can_manage_elections %}` and add a new "Committee" link wrapped in `{% if can_manage_committee %}`.

The Dashboard is unchanged for every role (shows the same stats to Member, Chairman, and Superuser alike, per explicit decision during brainstorming).

The Contestant create/edit form keeps its existing `election` dropdown field unmodified — that remains how a Member picks which election a Contestant belongs to, without ever needing access to the Election list/detail pages.

## Migration

1. Schema migration: add `role` and `is_active` to `AdminProfile`.
2. Data migration: for every existing `AdminProfile` row, set `is_active` to the old `is_admin` value; set `role="member"` where `is_admin` was `True`, else `role=None`.
3. Schema migration: drop `is_admin`.
4. Manual follow-up (not automatable — the old flat data has no concept of "who is the current Chairman"): after migrating, a Superuser must open the Committee page and promote whichever existing account should actually hold the Chairman role.

## Testing

New test coverage added to `admin_panel/tests.py` (following existing patterns already in that file):
- `AdminRequiredMixin` still grants Member/Chairman/Superuser access to Position/Contestant/Executive/Student/Dashboard views; denies unauthenticated and deactivated accounts.
- `ChairmanOrAboveRequiredMixin` denies Member access to every Election view (list/create/update/start/end/publish/results/print) and the "create Member"/"manage Member" actions; allows Chairman and Superuser.
- Superuser-only check denies Chairman and Member access to "create Chairman" and the Committee page's Superuser section; allows Superuser.
- Creating a new Chairman atomically demotes the previously-active Chairman to Member.
- Deactivating an account blocks their next login/dashboard access immediately.
- Self-deactivation is rejected with an error message.
- A Superuser's `AdminProfile` is auto-created on first admin-view access with `role=None, is_active=True`.
- Nav template: `can_manage_elections` / `can_manage_committee` correctly hide/show the "Elections" and "Committee" links per role.

## Open items for the implementation plan (not design decisions — just naming details to settle during planning)

- Exact URL/template names for the Committee page (e.g. `admin_panel:committee_list`, `admin_panel/committee_list.html`).
- Exact field list on the "create admin" form (likely `username`, `email`, `password` via Django's `UserCreationForm` or a custom equivalent).
