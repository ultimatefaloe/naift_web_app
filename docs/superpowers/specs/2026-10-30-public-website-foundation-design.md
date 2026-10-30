# Public Website + Foundation — Design Spec

**Date:** 2026-10-30
**Sub-project:** 1 of 3 (Public website → Admin panel → Voting dashboard)

## Context

This is the NAIFT election web app for the Information Technology department (School of Information and Communication Technology, SICT) at FUTMinna. The full system has three subsystems that will be designed and built sequentially:

1. **Public website + foundation** (this spec)
2. Admin panel (CRUD for executives/contestants/positions, election timing, audit log)
3. Voting dashboard (student login, voting, results)

This spec covers only the public website and the shared project foundation (Django apps, design system). It does not cover admin CRUD UI, student authentication, voting, or results.

## Scope

- Django project foundation: Tailwind integration, base layout, design system (colors, typography, animation)
- Public pages: Home, About, Academics, Current Executive
- `Executive` data model (read-only on the public site; CRUD comes in sub-project 2)
- Navigation including a placeholder "Vote" CTA link (target page doesn't exist yet — sub-project 3)

Out of scope: admin authentication/CRUD, student login, voting flow, results pages, past-executive archive UI (the model supports it via `session`/`is_current`, but no archive page is built yet).

## Architecture

Two new Django apps added to the existing `web` project:

### `core` app
- `base.html`: shared layout with navbar (logo, nav links, Vote CTA) and footer (logos, contact info)
- Template views (no models needed — content is static prose):
  - `HomeView` — hero section, highlights of current executives (pulls from `executives` app), quick links
  - `AboutView` — SICT history/philosophy/vision/mission + Information Technology department context
  - `AcademicsView` — general IT programme overview
- Design system: Tailwind config with CSS custom properties for purple/black/white in `:root`, serif heading font + sans body font, AOS (Animate on Scroll) wired into `base.html`

### `executives` app
- `Executive` model:
  - `name` (CharField)
  - `position` (CharField) — e.g. "President", "Vice President"
  - `photo` (ImageField)
  - `session` (CharField) — e.g. "2026/2027"
  - `is_current` (BooleanField) — distinguishes the active executive set from past ones (past-executive archive UI is a future addition, not built in this sub-project)
- `CurrentExecutiveView` — lists `Executive.objects.filter(is_current=True)`, grouped/labeled by `session`
- No admin UI in this sub-project. Data entry via Django's built-in `/admin/` site or a fixture, until sub-project 2 builds the custom admin panel.

### CSS tooling
`django-tailwind` added to `INSTALLED_APPS`, replacing the default static files setup, to get a managed Tailwind build integrated with `manage.py runserver`.

## Pages & Content

### Home
Hero section with school/department framing and logos, CTA buttons (Vote, Learn more), a highlights section surfacing current executives, and quick links to About/Academics.

### About
- SICT (School) history, philosophy, vision, and mission — sourced from the official text already captured in CLAUDE.md (verified accurate against futminna.edu.ng).
- Department of **Information Technology** (not "Information and Media Technology" — the school's public site has this merged/outdated, but the department's actual name and identity is Information Technology), founded in **2021**, presented as its own department under SICT.

### Academics
General IT programme overview, since no official FUTMinna-specific IT curriculum is publicly published:
- Programme philosophy: applying Science/Technology/Engineering/Math principles to meet the information needs of businesses and organizations effectively and efficiently (adapted from Nigeria's NUC Computing CCMAS framework, which IT programmes nationally are benchmarked against)
- Broad subject areas covered by the programme: programming, databases, networking, cybersecurity fundamentals, web/software development, systems administration
- A clearly marked placeholder section for course-level/level-by-level (100–500) curriculum detail, to be filled in later once real department data is available

### Current Executive
Card grid of `Executive.objects.filter(is_current=True)`: photo, name, position, grouped/labeled by session year.

### Logos
- Public site header/footer: `fut.jpeg` (note: CLAUDE.md refers to this as `fut_logo.jpeg`; the actual file in `static/image/` is named `fut.jpeg` — using the real filename) and `ift_logo.jpeg`
- `naifts_logo.jpeg` is reserved for the voting dashboard (sub-project 3), not used on the public site

### Navigation
Home · About · Academics · Executive · **Vote** (CTA-styled button/link; target page doesn't exist until sub-project 3, so this is a placeholder link for now)

## Design System

- Tailwind CSS with purple/black/white defined as CSS custom properties on `:root` (not hardcoded Tailwind color classes), so the palette has one source of truth
- Typography: a distinctive serif for headings (institutional/academic feel, avoiding generic SaaS defaults) paired with a clean sans for body text
- Animation: AOS (Animate On Scroll) — lightweight, no build step beyond a static script include, `data-aos` attributes on key elements (hero, section reveals, exec cards)
- Avoid generic/default-looking fonts and layouts per CLAUDE.md's explicit direction for a "school-like" design

## Testing

- Django `TestCase` + test client: each page (Home, About, Academics, Current Executive) returns HTTP 200 and renders the expected template
- `Executive` model/view test: records with `is_current=True` appear on the Current Executive page; records with `is_current=False` do not
- No JS test framework — AOS is purely presentational with no interactive logic to test at this stage

## Open items for future sub-projects

- Admin CRUD for `Executive`, `Position`, `Contestant` (sub-project 2)
- Election timing control (server-time-based, boolean + timestamp) (sub-project 2)
- Audit log of admin actions on voting-related data (sub-project 2)
- Student login (first name + matric number, pre-seeded), voting flow, one-time-vote enforcement, results page gated by admin timing, past-election results archive by year (sub-project 3)
