# NAIFT Election Web App

A Django web application for the Nigerian Association of Information Technology Students (NAIFT), Department of Information Technology. It runs the department's public website, student elections (voting + live/published results), the executives showcase, and an admin dashboard for the Electoral Committee (ELECOM) to manage all of it.

## Tech Stack

| Layer | Choice |
|---|---|
| Language / Framework | Python 3.12, Django 6.1.2 |
| Database | PostgreSQL (16/18-alpine locally via Docker; Neon Postgres in production) |
| Media storage | Cloudinary (`django-cloudinary-storage`) — uploaded photos only |
| Static files | Served from disk, built by `collectstatic` (not routed through Cloudinary) |
| CSS | Tailwind CSS via `django-tailwind`, compiled from the `theme` app |
| Images | Pillow |
| Hosting | Vercel (Python + static-build dual pipeline) |
| Config | `python-dotenv` (`.env` file, not committed) |

There is no JS framework and no REST API — this is a server-rendered Django app using Django's own template engine throughout.

## Architecture

Five Django apps, each with a single clear responsibility, plus one app that only exists to compile Tailwind:

```
web/            Project config: settings, root urls.py, wsgi.py
core/           Public marketing site (home, about, academics, credit/author page)
executives/     Public "current executives" showcase
elections/      Domain models shared by voting + admin_panel: Position, Election, Contestant
voting/         Everything a student does: login, ballot wizard, results, Student/Vote models
admin_panel/    The ELECOM dashboard: CRUD for all of the above, role-based access control
theme/          django-tailwind's generated app — owns the Tailwind build, not application code
```

**Dependency direction:** `elections` holds the shared domain models (`Position`, `Election`, `Contestant`) and has no dependency on `voting` or `admin_panel`. `voting` depends on `elections` (casts votes against its models) and on `admin_panel` only indirectly (through `elections.Position`/`Election.modified_by`, which points at `admin_panel.AdminProfile`). `admin_panel` depends on `elections`, `executives`, and `voting` (it's the management layer for all of them). `core` and `executives` are standalone and public-facing.

### Data model

- **`admin_panel.AdminProfile`** — one-to-one with Django's `User`. Holds `role` (`chairman` / `member` / `None`) and `is_active`. Superuser status itself is Django's built-in `User.is_superuser`, not a field here — see **Admin roles** below.
- **`elections.Position`** — an office being contested (e.g. "President"). `modified_by` points at the `AdminProfile` that last touched it.
- **`elections.Election`** — one voting cycle (`session`, `start_time`/`close_time` as *display labels only* — they don't gate access), with a `status` (`upcoming` → `ongoing` → `ended`) and an `is_results_published` flag.
- **`elections.Contestant`** — a candidate for a `Position` within a specific `Election`.
- **`voting.Student`** — the voter roster, keyed by a validated matric number (`YYYY/<digits>/<digits>CF`).
- **`voting.Vote`** — one student's choice for one position in one election. `unique_together = (student, election, position)` is what actually prevents double-voting.
- **`executives.Executive`** — a standalone, admin-managed record for the public "past/current executives" page — not tied to `Election` at all.

### Admin roles

The admin dashboard (`/dashboard/`) has three tiers, enforced by three stacked mixins in `admin_panel/mixins.py`:

| Role | How it's represented | Can do |
|---|---|---|
| **Superuser** | `User.is_superuser = True` (set via `createsuperuser` / Django's own `/admin/`, not through this app) | Everything, including creating/demoting the Chairman |
| **Chairman** | `AdminProfile.role == "chairman"` — exactly one active at a time, enforced atomically on both promotion and reactivation | Everything a Member can, plus the full Election lifecycle (create/start/end/publish results) and the Committee page (add/deactivate/reactivate Members) |
| **Member** | `AdminProfile.role == "member"` | Position / Contestant / Executive / Student CRUD + Dashboard. No Election access at all — hidden from nav and redirected if the URL is hit directly |

`AdminRequiredMixin` → any active admin of any role. `ChairmanOrAboveRequiredMixin` → Chairman or Superuser only (gates Election views + most of the Committee page). `SuperuserRequiredMixin` → Superuser only (gates "create Chairman"). All three auto-provision a Superuser's `AdminProfile` (`role=None`) on first dashboard visit, since `Election.modified_by` needs one to exist.

### Voting flow

1. A student logs in at `/vote/login/` with first name + matric number (no password — this is a low-stakes campus election, not an authenticated account system). The session stores `student_id`.
2. `/vote/` routes to the current election's first `Position`, one position per page (`wizard_step`), with a "review" step before final submission.
3. Casting a vote creates one `Vote` row per position; the DB-level `unique_together` constraint is the actual integrity guarantee, not application logic.
4. `/vote/results/` shows results only once an election's `is_results_published` flag is set by a Chairman/Superuser. `/vote/results/archive/` lists past, already-published elections.
5. Vote tallying (`Count("votes", filter=Q(votes__election=F("election")))`) is intentionally duplicated across `voting.views.results_view`, and `admin_panel.views.ElectionResultsView`/`ElectionResultsPrintView`/`DashboardView` — each call site is comment-linked to the others; keep them in sync if the ordering/annotation logic ever changes.

## Project Structure

```
naift_web_app/
├── web/                    # settings.py, urls.py, wsgi.py
├── core/                   # public site
│   ├── templates/core/
│   └── views.py, urls.py
├── executives/              # public executives showcase
├── elections/               # Position/Election/Contestant models + results.py (winner logic)
├── voting/                  # Student/Vote models, ballot flow, CSV import, management/commands/
├── admin_panel/              # dashboard: models (AdminProfile), mixins (role gates),
│   │                          views.py (all CRUD + Committee page), context_processors.py
│   └── templates/admin_panel/
├── theme/                    # django-tailwind app (static_src/ has package.json, Tailwind config)
├── static/                   # project-wide static assets (images, favicon)
├── docs/superpowers/         # design specs + implementation plans written during feature work
├── docker-compose.yml         # local Postgres only
├── vercel.json / vercel_build.sh   # Vercel deployment pipeline
├── requirements.txt
├── manage.py
└── .env.example               # copy to .env for local dev
```

## Local Setup

**Prerequisites:** Python 3.12+, Docker (for local Postgres), Node (only if you need to rebuild Tailwind).

```bash
# 1. Clone and enter the repo, then create a virtualenv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# edit .env: DB_* values, plus CLOUDINARY_CLOUD_NAME/API_KEY/API_SECRET
# (free tier at https://cloudinary.com — only needed for uploading contestant/executive photos)

# 3. Start Postgres
docker compose up -d db

# 4. Apply migrations
python manage.py migrate

# 5. Build Tailwind CSS (first time installs the npm deps under theme/static_src/)
python manage.py tailwind install
python manage.py tailwind build
# while actively changing templates/CSS, run this instead, in a second terminal:
python manage.py tailwind start

# 6. Create your own admin account
python manage.py createsuperuser
# log into /admin/ once with it, or just visit /dashboard/ — a superuser's
# AdminProfile is auto-created on first dashboard visit

# 7. Run the app
python manage.py runserver
```

Visit `http://localhost:8000/` for the public site, `http://localhost:8000/dashboard/` for the admin panel, `http://localhost:8000/vote/` for the student voting flow.

## Common Commands

```bash
# Run the full test suite
python manage.py test

# Run one app's tests
python manage.py test admin_panel

# Run a single test
python manage.py test admin_panel.tests.CommitteeManagementTests.test_chairman_creates_member

# Bulk-import/update students from CSV (columns: first_name,last_name,matric_number,level)
python manage.py seed_students path/to/students.csv
# (the admin dashboard's Students page also has a CSV upload button that does the same thing)

# Check for model changes missing a migration
python manage.py makemigrations --check --dry-run

# Open a DB shell / Python shell against the configured database
python manage.py dbshell
python manage.py shell
```

If Docker's Postgres container isn't reachable (`docker ps` shows nothing), bring it up with:

```bash
systemctl --user start docker-desktop   # if the Docker daemon itself isn't running
docker compose up -d db
```

## Testing

Each app has its own `tests.py` using Django's standard `TestCase` (a real transactional Postgres test database, not mocks). Tests cover model behavior, view access control (including the three admin role tiers), form validation, and the CSV import's encoding-fallback behavior (UTF-8-BOM → cp1252 → friendly error).

```bash
python manage.py test --keepdb   # --keepdb skips drop/recreate between runs, much faster locally
```

## Deployment

Hosted on Vercel via `vercel.json`'s two parallel builds:
- `@vercel/python` serves `web/wsgi.py` as the actual Django app.
- `@vercel/static-build` runs `vercel_build.sh`, which installs dependencies, builds Tailwind CSS, and runs `collectstatic` — all static files (not just CSS) ship through this pipeline, not through Cloudinary (Cloudinary is media-only).

Required production environment variables: `DEBUG=False`, `SECRET_KEY`, `ALLOWED_HOSTS`, `DB_NAME`/`DB_USER`/`DB_PASSWORD`/`DB_HOST`/`DB_PORT` (plus `DB_SSLMODE`/`DB_CHANNELBINDING` if your Postgres provider requires SSL — Neon does, by default), `CLOUDINARY_CLOUD_NAME`/`CLOUDINARY_API_KEY`/`CLOUDINARY_API_SECRET`.

After deploying a schema change, run migrations against the production database (`python manage.py migrate`, pointed at the production `DATABASE_URL`/`DB_*` vars) — Vercel's build step does not run migrations automatically.
