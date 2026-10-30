# Public Website + Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the Django project foundation and the public website (Home, About, Academics, Current Executive) described in `docs/superpowers/specs/2026-10-30-public-website-foundation-design.md`.

**Architecture:** Two new Django apps — `core` (base layout, static content pages, design system) and `executives` (the `Executive` model and its public listing view) — sitting on top of a Dockerized local Postgres database and Cloudinary-backed media storage, with Tailwind CSS (v4, CSS-first config) for styling and AOS for scroll animations.

**Tech Stack:** Django 6.1.2, PostgreSQL (via Docker Compose), psycopg2-binary, python-dotenv, Pillow, django-cloudinary-storage + cloudinary, django-tailwind (Tailwind v4), AOS (CDN).

---

## Prerequisites

- Docker must be running before Task 2 (`docker compose up`). Start Docker Desktop now if it isn't already — check with `docker ps`.
- A Cloudinary account (free tier is fine) for Task 4. Sign up at cloudinary.com and have your Cloud Name, API Key, and API Secret ready — they go into `.env`, not into any committed file.

---

### Task 1: Project baseline — .gitignore, .env.example, initial commit

**Files:**
- Modify: `.gitignore`
- Create: `.env.example`
- Create: `requirements.txt`

- [ ] **Step 1: Write `.gitignore`**

The current `.gitignore` is empty, which risks committing the virtualenv, secrets, or the SQLite/build artifacts this plan will introduce. Replace its contents with:

```
# Python
__pycache__/
*.py[cod]
*.egg-info/

# Virtual environment
.venv/

# Environment variables
.env

# Django
*.sqlite3
/media/
/staticfiles/

# Tailwind build output (rebuilt from theme/static_src via `manage.py tailwind`)
theme/static/
node_modules/

# Editors / OS
.DS_Store
```

- [ ] **Step 2: Write `.env.example`**

This is the committed template documenting which environment variables the project needs; the real `.env` (with real secrets) stays untracked.

```
# Database (used by docker-compose.yml and web/settings.py)
DB_NAME=naift
DB_USER=naift
DB_PASSWORD=change-me
DB_HOST=localhost
DB_PORT=5434

# Cloudinary (create a free account at https://cloudinary.com and copy these
# from your dashboard's Account Details / API Environment variable section)
CLOUDINARY_CLOUD_NAME=
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=
```

- [ ] **Step 3: Create your real `.env`**

```bash
cp .env.example .env
```

Edit `.env` and set `DB_PASSWORD` to a real value (anything, this is local-only). Leave the `CLOUDINARY_*` values blank for now — you'll fill those in during Task 4.

- [ ] **Step 4: Write `requirements.txt`**

```
Django==6.1.2
```

- [ ] **Step 5: Verify nothing sensitive is staged**

```bash
git status --short
```

Expected: `.env` and `.venv/` do NOT appear (they're now ignored); `.gitignore`, `.env.example`, `requirements.txt`, `manage.py`, `static/`, `web/`, `CLAUDE.md` appear as untracked/new.

- [ ] **Step 6: Commit the project baseline**

```bash
git add .gitignore .env.example requirements.txt manage.py static web CLAUDE.md
git commit -m "Add project baseline: gitignore, env template, requirements"
```

---

### Task 2: Local Postgres via Docker Compose

**Files:**
- Create: `docker-compose.yml`

- [ ] **Step 1: Write `docker-compose.yml`**

```yaml
services:
  db:
    image: postgres:18-alpine
    restart: unless-stopped
    env_file:
      - .env
    environment:
      POSTGRES_DB: ${DB_NAME}
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    ports:
      - "${DB_PORT:-5434}:5432"
    volumes:
      - naift_pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER} -d ${DB_NAME}"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  naift_pgdata:
```

Note: the container's internal Postgres port is always 5432; `DB_PORT` (default 5434) only controls which port it's published on *your host machine*, chosen to avoid clashing with this machine's existing Postgres processes on 5432/5433.

- [ ] **Step 2: Start the database**

```bash
docker compose up -d db
```

Expected: `Container <name>-db-1  Started` (or `Created`/`Started`).

- [ ] **Step 3: Verify it's healthy**

```bash
docker compose ps
```

Expected: the `db` service shows `STATUS` containing `(healthy)`. If it shows `(health: starting)`, wait a few seconds and re-run.

- [ ] **Step 4: Verify you can connect**

```bash
docker compose exec db psql -U "$(grep DB_USER .env | cut -d= -f2)" -d "$(grep DB_NAME .env | cut -d= -f2)" -c "SELECT 1;"
```

Expected output includes:
```
 ?column?
----------
        1
(1 row)
```

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml
git commit -m "Add docker-compose for local Postgres"
```

---

### Task 3: Point Django at Postgres

**Files:**
- Modify: `web/settings.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Install the new dependencies**

```bash
.venv/bin/pip install psycopg2-binary python-dotenv
```

- [ ] **Step 2: Update `requirements.txt`**

```
Django==6.1.2
psycopg2-binary==2.9.13
python-dotenv==1.2.4
```

- [ ] **Step 3: Load `.env` and switch `DATABASES` to Postgres**

In `web/settings.py`, replace:

```python
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
```

with:

```python
import os
from pathlib import Path

from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")
```

Then replace:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
```

with:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'naift'),
        'USER': os.environ.get('DB_USER', 'naift'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5434'),
    }
}
```

- [ ] **Step 4: Run migrations against Postgres**

```bash
.venv/bin/python manage.py migrate
```

Expected: a list of `Applying ...` lines ending successfully (e.g. `Applying sessions.0001_initial... OK`), no errors. This proves Django is talking to the Dockerized Postgres, not SQLite.

- [ ] **Step 5: Verify the tables landed in Postgres (not SQLite)**

```bash
ls db.sqlite3 2>&1
docker compose exec db psql -U "$(grep DB_USER .env | cut -d= -f2)" -d "$(grep DB_NAME .env | cut -d= -f2)" -c "\dt" | grep auth_user
```

Expected: the `ls` command reports `No such file or directory` (no SQLite file was created), and the `psql` command lists `auth_user` among the tables.

- [ ] **Step 6: Commit**

```bash
git add web/settings.py requirements.txt
git commit -m "Switch database to Postgres via docker-compose and .env"
```

---

### Task 4: Cloudinary media storage

**Files:**
- Modify: `web/settings.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Install dependencies**

```bash
.venv/bin/pip install pillow django-cloudinary-storage cloudinary
```

- [ ] **Step 2: Update `requirements.txt`**

```
Django==6.1.2
psycopg2-binary==2.9.13
python-dotenv==1.2.4
pillow==13.0.0
django-cloudinary-storage==0.3.0
cloudinary==1.46.3
```

- [ ] **Step 3: Add the apps and storage config to `web/settings.py`**

Replace:

```python
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]
```

with:

```python
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'cloudinary_storage',
    'django.contrib.staticfiles',
    'cloudinary',
]
```

Then, after the `STATIC_URL = 'static/'` line, add:

```python
MEDIA_URL = 'media/'

CLOUDINARY_STORAGE = {
    'CLOUD_NAME': os.environ.get('CLOUDINARY_CLOUD_NAME', ''),
    'API_KEY': os.environ.get('CLOUDINARY_API_KEY', ''),
    'API_SECRET': os.environ.get('CLOUDINARY_API_SECRET', ''),
}

STORAGES = {
    'default': {
        'BACKEND': 'cloudinary_storage.storage.MediaCloudinaryStorage',
    },
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}
```

(Django 6.1 has no `DEFAULT_FILE_STORAGE` setting any more — `STORAGES` is the only supported way to configure this.)

- [ ] **Step 4: Verify Django boots cleanly**

```bash
.venv/bin/python manage.py check
```

Expected: `System check identified no issues (0 silenced).` This passes even with blank Cloudinary credentials in `.env` — the keys just need to *exist* in `CLOUDINARY_STORAGE`, real values aren't required until something actually uploads a file (Task 11's manual check).

- [ ] **Step 5: Fill in your real Cloudinary credentials**

Open your Cloudinary dashboard and copy your Cloud Name, API Key, and API Secret into `.env`'s `CLOUDINARY_*` variables.

- [ ] **Step 6: Commit**

```bash
git add web/settings.py requirements.txt
git commit -m "Add Cloudinary-backed media storage"
```

---

### Task 5: Tailwind CSS + design system tokens

**Files:**
- Create: `theme/` (generated by `manage.py tailwind init`)
- Modify: `theme/static_src/src/styles.css`
- Modify: `theme/templates/base.html` (will be replaced entirely in Task 6 — this task just confirms the generated default works)
- Modify: `web/settings.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Install django-tailwind with the cookiecutter extra**

The `cookiecutter` extra is only needed to run `tailwind init` once; it is not required at runtime, so it is not added to `requirements.txt`.

```bash
.venv/bin/pip install "django-tailwind[cookiecutter]"
```

- [ ] **Step 2: Add `tailwind` to `INSTALLED_APPS` and set `TAILWIND_APP_NAME`**

In `web/settings.py`, change:

```python
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'cloudinary_storage',
    'django.contrib.staticfiles',
    'cloudinary',
]
```

to:

```python
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'cloudinary_storage',
    'django.contrib.staticfiles',
    'cloudinary',
    'tailwind',
]
```

Then add, after `MEDIA_URL = 'media/'`:

```python
TAILWIND_APP_NAME = 'theme'
```

- [ ] **Step 3: Generate the `theme` app**

```bash
.venv/bin/python manage.py tailwind init --no-input --app-name=theme --tailwind-version=4
```

Expected: `Tailwind application 'theme' has been successfully created. ...`

- [ ] **Step 4: Add `theme` to `INSTALLED_APPS`**

```python
    'tailwind',
    'theme',
```

- [ ] **Step 5: Install the npm dependencies and build once**

```bash
.venv/bin/python manage.py tailwind install
```

Expected: npm installs ~70+ packages ending in `found 0 vulnerabilities`, followed by a successful `build:tailwind` run.

- [ ] **Step 6: Define the purple/black/white palette and typography as theme tokens**

Replace the contents of `theme/static_src/src/styles.css` with:

```css
@import "tailwindcss";

/**
  * A catch-all path to Django template files, JavaScript, and Python files
  * that contain Tailwind CSS classes and will be scanned by Tailwind to generate the final CSS file.
  */
@source "../../../**/*.{html,py,js}";

@theme {
  --color-brand-purple: #4C1D95;
  --color-brand-black: #0A0A0A;
  --color-brand-white: #FFFFFF;
  --font-display: "Fraunces", serif;
  --font-body: "Inter", sans-serif;
}
```

This makes `bg-brand-purple`, `text-brand-black`, `border-brand-purple/20`, `font-display`, and `font-body` available as Tailwind utility classes everywhere in the project (Tailwind v4's CSS-first `@theme` config).

- [ ] **Step 7: Rebuild and verify the custom tokens compiled**

```bash
.venv/bin/python manage.py tailwind build
grep -c "brand-purple" theme/static/css/dist/styles.css
```

Expected: the `grep -c` prints a number greater than `0`, confirming the custom color made it into the compiled CSS.

- [ ] **Step 8: Update `requirements.txt`**

```
Django==6.1.2
psycopg2-binary==2.9.13
python-dotenv==1.2.4
pillow==13.0.0
django-cloudinary-storage==0.3.0
cloudinary==1.46.3
django-tailwind==4.6.0
```

- [ ] **Step 9: Commit**

```bash
git add theme web/settings.py requirements.txt
git commit -m "Add Tailwind CSS with purple/black/white design tokens"
```

---

### Task 6: `core` app — base layout and design system wiring

**Files:**
- Create: `core/__init__.py`, `core/apps.py`
- Create: `core/templates/core/base.html`
- Modify: `web/settings.py`

- [ ] **Step 1: Create the app**

```bash
.venv/bin/python manage.py startapp core
```

- [ ] **Step 2: Add `core` to `INSTALLED_APPS` and register the project-level static directory**

In `web/settings.py`, add `'core',` after `'theme',` in `INSTALLED_APPS`:

```python
    'tailwind',
    'theme',
    'core',
```

Then, right after `STATIC_URL = 'static/'`, add:

```python
STATICFILES_DIRS = [BASE_DIR / 'static']
```

This makes the existing logos at `static/image/ift_logo.jpeg` and `static/image/fut.jpeg` loadable via `{% static %}`.

- [ ] **Step 3: Write the base layout**

Create `core/templates/core/base.html`:

```html
{% load static tailwind_tags %}
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}NAIFT{% endblock %}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300..900;1,9..144,300..900&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/aos/2.3.4/aos.css" rel="stylesheet" integrity="sha512-1cK78a1o+ht2JcaW6g8OXYwqpev9+6GqOkz9xmBN9iUUhIndKtxwILGWYOSibOKjLsEdjyjZvYDq/cZwNeak0w==" crossorigin="anonymous" referrerpolicy="no-referrer">
    {% tailwind_css %}
</head>
<body class="bg-brand-white text-brand-black font-body">
    <header class="flex items-center justify-between px-6 py-4 border-b border-brand-black/10">
        <div class="flex items-center gap-3">
            <img src="{% static 'image/ift_logo.jpeg' %}" alt="Department of Information Technology logo" class="h-12 w-12 rounded-full object-cover">
            <img src="{% static 'image/fut.jpeg' %}" alt="Federal University of Technology Minna logo" class="h-12 w-12 rounded-full object-cover">
            <span class="font-display text-xl text-brand-purple">NAIFT</span>
        </div>
    </header>

    <main>
        {% block content %}{% endblock %}
    </main>

    <footer class="bg-brand-black text-brand-white px-6 py-8 mt-16">
        <div class="flex items-center gap-3 mb-4">
            <img src="{% static 'image/ift_logo.jpeg' %}" alt="Department of Information Technology logo" class="h-10 w-10 rounded-full object-cover">
            <img src="{% static 'image/fut.jpeg' %}" alt="Federal University of Technology Minna logo" class="h-10 w-10 rounded-full object-cover">
        </div>
        <p class="text-sm text-brand-white/70">Department of Information Technology &middot; School of Information and Communication Technology &middot; Federal University of Technology, Minna</p>
    </footer>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/aos/2.3.4/aos.js" integrity="sha512-A7AYk1fGKX6S2SsHywmPkrnzTZHrgiVT7GcQkLGDe2ev0aWb8zejytzS8wjo7PGEXKqJOrjQ4oORtnimIRZBtw==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>
    <script>AOS.init();</script>
</body>
</html>
```

Navigation links (Home/About/Academics/Executive/Vote) are added in Task 12, once every page they point to actually exists — adding them now would make every page render a `NoReverseMatch` error.

- [ ] **Step 4: Verify the project still boots**

```bash
.venv/bin/python manage.py check
```

Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 5: Commit**

```bash
git add core web/settings.py
git commit -m "Add core app with base layout and design system"
```

---

### Task 7: Home page

**Files:**
- Create: `core/views.py`
- Create: `core/urls.py`
- Create: `core/templates/core/home.html`
- Create: `core/tests.py`
- Modify: `web/urls.py`

- [ ] **Step 1: Write the failing test**

Create `core/tests.py`:

```python
from django.test import TestCase
from django.urls import reverse


class CorePagesTests(TestCase):
    def test_home_page_returns_200(self):
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/home.html")
```

- [ ] **Step 2: Run it and confirm it fails**

```bash
.venv/bin/python manage.py test core
```

Expected: `NoReverseMatch` (no URL named `core:home` exists yet).

- [ ] **Step 3: Implement the view**

Create `core/views.py`:

```python
from django.views.generic import TemplateView


class HomeView(TemplateView):
    template_name = "core/home.html"
```

- [ ] **Step 4: Wire the URL**

Create `core/urls.py`:

```python
from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
]
```

In `web/urls.py`, replace:

```python
from django.contrib import admin
from django.urls import path

urlpatterns = [
    path('admin/', admin.site.urls),
]
```

with:

```python
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
]
```

- [ ] **Step 5: Write the template**

Create `core/templates/core/home.html`:

```html
{% extends "core/base.html" %}

{% block title %}Home · NAIFT{% endblock %}

{% block content %}
<section class="bg-brand-purple text-brand-white px-6 py-24 text-center" data-aos="fade-up">
    <h1 class="font-display text-4xl md:text-6xl mb-4">Department of Information Technology</h1>
    <p class="text-lg md:text-xl max-w-2xl mx-auto">School of Information and Communication Technology, Federal University of Technology, Minna</p>
</section>

<section class="px-6 py-16 max-w-4xl mx-auto" data-aos="fade-up">
    <h2 class="font-display text-3xl text-brand-purple mb-4">Welcome</h2>
    <p class="text-lg leading-relaxed">
        This is the home of the Department of Information Technology's student election platform.
        Learn about the department, meet the current executive, and take part in departmental elections.
    </p>
</section>
{% endblock %}
```

- [ ] **Step 6: Run the test and confirm it passes**

```bash
.venv/bin/python manage.py test core
```

Expected: `OK` (1 test).

- [ ] **Step 7: Commit**

```bash
git add core web/urls.py
git commit -m "Add Home page"
```

---

### Task 8: About page

**Files:**
- Modify: `core/views.py`
- Modify: `core/urls.py`
- Create: `core/templates/core/about.html`
- Modify: `core/tests.py`

- [ ] **Step 1: Write the failing test**

Add to `core/tests.py`, inside `CorePagesTests`:

```python
    def test_about_page_returns_200(self):
        response = self.client.get(reverse("core:about"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/about.html")
```

- [ ] **Step 2: Run it and confirm it fails**

```bash
.venv/bin/python manage.py test core
```

Expected: `NoReverseMatch` (no URL named `core:about` exists yet).

- [ ] **Step 3: Implement the view**

Add to `core/views.py`:

```python
class AboutView(TemplateView):
    template_name = "core/about.html"
```

- [ ] **Step 4: Wire the URL**

In `core/urls.py`, add to `urlpatterns`:

```python
    path("about/", views.AboutView.as_view(), name="about"),
```

- [ ] **Step 5: Write the template**

Create `core/templates/core/about.html`:

```html
{% extends "core/base.html" %}

{% block title %}About · NAIFT{% endblock %}

{% block content %}
<section class="px-6 py-16 max-w-4xl mx-auto" data-aos="fade-up">
    <h1 class="font-display text-4xl text-brand-purple mb-8">About</h1>

    <h2 class="font-display text-2xl text-brand-black mb-3">School of Information and Communication Technology (SICT)</h2>
    <p class="text-lg leading-relaxed mb-6">
        The School of Information and Communication Technology (SICT) was created in the 2009/2010 academic
        session. The pioneer departments were Computer Science, Cyber Security Science, Information and
        Media Technology, and Library and Information Technology. SICT received the National Universities
        Commission's Pre-Accreditation Resource Verification Visit in 2010, which saw all its departments
        accredited. Since its inception, the School has graduated over 1,000 undergraduates and 500
        postgraduates.
    </p>

    <div class="grid md:grid-cols-3 gap-6 mb-10">
        <div class="border border-brand-purple/20 rounded-lg p-5">
            <h3 class="font-display text-xl text-brand-purple mb-2">Philosophy</h3>
            <p>To encourage the advancement of learning and the acquisition of higher education in Technology.</p>
        </div>
        <div class="border border-brand-purple/20 rounded-lg p-5">
            <h3 class="font-display text-xl text-brand-purple mb-2">Vision</h3>
            <p>To be the world-class centre of Excellence in training and research in Information and Communication Technology in Nigeria.</p>
        </div>
        <div class="border border-brand-purple/20 rounded-lg p-5">
            <h3 class="font-display text-xl text-brand-purple mb-2">Mission</h3>
            <p>To build excellent research capacity and develop high-quality human capital through pragmatic and dynamic training, research, and entrepreneurial services for the Information and Communication Technology sector in Nigeria and the world at large.</p>
        </div>
    </div>

    <h2 class="font-display text-2xl text-brand-black mb-3">Department of Information Technology</h2>
    <p class="text-lg leading-relaxed">
        The Department of Information Technology was founded in 2021 under the School of Information and
        Communication Technology (SICT). The department trains students in the knowledge, skills, and
        practices needed to design, build, deploy, and manage the information systems that organizations
        rely on every day.
    </p>
</section>
{% endblock %}
```

- [ ] **Step 6: Run the test and confirm it passes**

```bash
.venv/bin/python manage.py test core
```

Expected: `OK` (2 tests).

- [ ] **Step 7: Commit**

```bash
git add core
git commit -m "Add About page"
```

---

### Task 9: Academics page

**Files:**
- Modify: `core/views.py`
- Modify: `core/urls.py`
- Create: `core/templates/core/academics.html`
- Modify: `core/tests.py`

- [ ] **Step 1: Write the failing test**

Add to `core/tests.py`, inside `CorePagesTests`:

```python
    def test_academics_page_returns_200(self):
        response = self.client.get(reverse("core:academics"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/academics.html")
```

- [ ] **Step 2: Run it and confirm it fails**

```bash
.venv/bin/python manage.py test core
```

Expected: `NoReverseMatch` (no URL named `core:academics` exists yet).

- [ ] **Step 3: Implement the view**

Add to `core/views.py`:

```python
class AcademicsView(TemplateView):
    template_name = "core/academics.html"
```

- [ ] **Step 4: Wire the URL**

In `core/urls.py`, add to `urlpatterns`:

```python
    path("academics/", views.AcademicsView.as_view(), name="academics"),
```

- [ ] **Step 5: Write the template**

Create `core/templates/core/academics.html`:

```html
{% extends "core/base.html" %}

{% block title %}Academics · NAIFT{% endblock %}

{% block content %}
<section class="px-6 py-16 max-w-4xl mx-auto" data-aos="fade-up">
    <h1 class="font-display text-4xl text-brand-purple mb-8">Academics</h1>

    <h2 class="font-display text-2xl text-brand-black mb-3">Programme Philosophy</h2>
    <p class="text-lg leading-relaxed mb-8">
        The Information Technology programme applies the principles and practices of Science, Technology,
        Engineering, and Mathematics to meet the computing and information needs of businesses, government,
        and other organizations &mdash; enabling them to achieve their objectives effectively and efficiently.
    </p>

    <h2 class="font-display text-2xl text-brand-black mb-3">Core Areas of Study</h2>
    <ul class="list-disc list-inside text-lg leading-relaxed mb-8 space-y-1">
        <li>Programming &amp; Software Development</li>
        <li>Database Systems</li>
        <li>Computer Networking</li>
        <li>Cybersecurity Fundamentals</li>
        <li>Web &amp; Mobile Application Development</li>
        <li>Systems Administration</li>
    </ul>

    <div class="border-l-4 border-brand-purple bg-brand-purple/5 p-5 text-brand-black/80">
        <p>Detailed course-by-course curriculum (100&ndash;500 level) will be published here once finalized by the department.</p>
    </div>
</section>
{% endblock %}
```

- [ ] **Step 6: Run the test and confirm it passes**

```bash
.venv/bin/python manage.py test core
```

Expected: `OK` (3 tests).

- [ ] **Step 7: Commit**

```bash
git add core
git commit -m "Add Academics page"
```

---

### Task 10: `executives` app — the `Executive` model

**Files:**
- Create: `executives/__init__.py`, `executives/apps.py`
- Create: `executives/models.py`
- Create: `executives/admin.py`
- Create: `executives/tests.py`
- Create: `executives/migrations/0001_initial.py` (generated)
- Modify: `web/settings.py`

- [ ] **Step 1: Write the failing test**

```bash
.venv/bin/python manage.py startapp executives
```

Replace the contents of `executives/tests.py` with:

```python
from django.test import TestCase

from .models import Executive


class ExecutiveModelTests(TestCase):
    def test_string_representation(self):
        executive = Executive(name="Jane Doe", position="President")
        self.assertEqual(str(executive), "Jane Doe (President)")
```

- [ ] **Step 2: Run it and confirm it fails**

First add `'executives',` to `INSTALLED_APPS` in `web/settings.py` (after `'core',`) so the app is discoverable:

```python
    'core',
    'executives',
```

```bash
.venv/bin/python manage.py test executives
```

Expected: `ImportError` or `AttributeError` — `Executive` doesn't exist in `executives/models.py` yet (it's still the empty default `startapp` file).

- [ ] **Step 3: Implement the model**

Replace the contents of `executives/models.py` with:

```python
from django.db import models


class Executive(models.Model):
    name = models.CharField(max_length=150)
    position = models.CharField(max_length=100)
    photo = models.ImageField(upload_to="executives/")
    session = models.CharField(max_length=20, help_text='e.g. "2026/2027"')
    is_current = models.BooleanField(default=True)

    class Meta:
        ordering = ["session", "position"]

    def __str__(self):
        return f"{self.name} ({self.position})"
```

- [ ] **Step 4: Generate and apply the migration**

```bash
.venv/bin/python manage.py makemigrations executives
.venv/bin/python manage.py migrate executives
```

Expected: `Migrations for 'executives': ... 0001_initial.py` then `Applying executives.0001_initial... OK`.

- [ ] **Step 5: Run the test and confirm it passes**

```bash
.venv/bin/python manage.py test executives
```

Expected: `OK` (1 test).

- [ ] **Step 6: Register the model with Django's built-in admin**

Per the spec, `Executive` records are seeded via Django's built-in `/admin/` until the custom admin dashboard (sub-project 2) exists. Replace the contents of `executives/admin.py` with:

```python
from django.contrib import admin

from .models import Executive


@admin.register(Executive)
class ExecutiveAdmin(admin.ModelAdmin):
    list_display = ("name", "position", "session", "is_current")
    list_filter = ("session", "is_current")
```

- [ ] **Step 7: Commit**

```bash
git add executives web/settings.py
git commit -m "Add Executive model with Django admin registration"
```

---

### Task 11: Current Executive page

**Files:**
- Create: `executives/views.py`
- Create: `executives/urls.py`
- Create: `executives/templates/executives/current.html`
- Modify: `executives/tests.py`
- Modify: `web/urls.py`

- [ ] **Step 1: Write the failing test**

Add to `executives/tests.py`:

```python
from django.urls import reverse


class CurrentExecutiveViewTests(TestCase):
    def setUp(self):
        self.current = Executive.objects.create(
            name="Jane Doe",
            position="President",
            session="2026/2027",
            is_current=True,
        )
        self.past = Executive.objects.create(
            name="John Smith",
            position="President",
            session="2025/2026",
            is_current=False,
        )

    def test_returns_200_and_uses_template(self):
        response = self.client.get(reverse("executives:current"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "executives/current.html")

    def test_only_current_executives_are_listed(self):
        response = self.client.get(reverse("executives:current"))
        self.assertIn(self.current, response.context["executives"])
        self.assertNotIn(self.past, response.context["executives"])
```

- [ ] **Step 2: Run it and confirm it fails**

```bash
.venv/bin/python manage.py test executives
```

Expected: `NoReverseMatch` (no URL named `executives:current` exists yet).

- [ ] **Step 3: Implement the view**

Create `executives/views.py`:

```python
from django.views.generic import ListView

from .models import Executive


class CurrentExecutiveView(ListView):
    template_name = "executives/current.html"
    context_object_name = "executives"

    def get_queryset(self):
        return Executive.objects.filter(is_current=True)
```

- [ ] **Step 4: Wire the URL**

Create `executives/urls.py`:

```python
from django.urls import path

from . import views

app_name = "executives"

urlpatterns = [
    path("", views.CurrentExecutiveView.as_view(), name="current"),
]
```

In `web/urls.py`, change:

```python
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
]
```

to:

```python
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('executives/', include('executives.urls')),
]
```

- [ ] **Step 5: Write the template**

Create `executives/templates/executives/current.html`:

```html
{% extends "core/base.html" %}

{% block title %}Current Executive · NAIFT{% endblock %}

{% block content %}
<section class="px-6 py-16 max-w-5xl mx-auto" data-aos="fade-up">
    <h1 class="font-display text-4xl text-brand-purple mb-8">Current Executive</h1>

    {% regroup executives by session as session_list %}
    {% for session in session_list %}
        <h2 class="font-display text-2xl text-brand-black mb-4">{{ session.grouper }}</h2>
        <div class="grid sm:grid-cols-2 md:grid-cols-3 gap-6 mb-10">
            {% for executive in session.list %}
                <div class="border border-brand-purple/20 rounded-lg p-5 text-center" data-aos="fade-up">
                    {% if executive.photo %}
                        <img src="{{ executive.photo.url }}" alt="{{ executive.name }}" class="h-32 w-32 rounded-full object-cover mx-auto mb-3">
                    {% endif %}
                    <h3 class="font-display text-lg text-brand-black">{{ executive.name }}</h3>
                    <p class="text-brand-purple">{{ executive.position }}</p>
                </div>
            {% endfor %}
        </div>
    {% empty %}
        <p class="text-lg">No current executive has been published yet.</p>
    {% endfor %}
</section>
{% endblock %}
```

- [ ] **Step 6: Run the tests and confirm they pass**

```bash
.venv/bin/python manage.py test executives
```

Expected: `OK` (3 tests).

- [ ] **Step 7: Commit**

```bash
git add executives web/urls.py
git commit -m "Add Current Executive page"
```

---

### Task 12: Navigation + full test suite

**Files:**
- Modify: `core/templates/core/base.html`

- [ ] **Step 1: Add the nav bar**

Every URL name used below now exists (`core:home`, `core:about`, `core:academics`, `executives:current`), so this is safe to add. In `core/templates/core/base.html`, replace:

```html
    <header class="flex items-center justify-between px-6 py-4 border-b border-brand-black/10">
        <div class="flex items-center gap-3">
            <img src="{% static 'image/ift_logo.jpeg' %}" alt="Department of Information Technology logo" class="h-12 w-12 rounded-full object-cover">
            <img src="{% static 'image/fut.jpeg' %}" alt="Federal University of Technology Minna logo" class="h-12 w-12 rounded-full object-cover">
            <span class="font-display text-xl text-brand-purple">NAIFT</span>
        </div>
    </header>
```

with:

```html
    <header class="flex items-center justify-between px-6 py-4 border-b border-brand-black/10">
        <div class="flex items-center gap-3">
            <img src="{% static 'image/ift_logo.jpeg' %}" alt="Department of Information Technology logo" class="h-12 w-12 rounded-full object-cover">
            <img src="{% static 'image/fut.jpeg' %}" alt="Federal University of Technology Minna logo" class="h-12 w-12 rounded-full object-cover">
            <span class="font-display text-xl text-brand-purple">NAIFT</span>
        </div>
        <nav class="flex items-center gap-6 font-body">
            <a href="{% url 'core:home' %}" class="hover:text-brand-purple">Home</a>
            <a href="{% url 'core:about' %}" class="hover:text-brand-purple">About</a>
            <a href="{% url 'core:academics' %}" class="hover:text-brand-purple">Academics</a>
            <a href="{% url 'executives:current' %}" class="hover:text-brand-purple">Executive</a>
            <a href="#" class="bg-brand-purple text-brand-white px-4 py-2 rounded-full hover:opacity-90">Vote</a>
        </nav>
    </header>
```

The `Vote` link is a placeholder (`href="#"`) — its target page doesn't exist until the voting dashboard sub-project.

- [ ] **Step 2: Run the entire test suite**

```bash
.venv/bin/python manage.py test
```

Expected: `OK` (6 tests: 3 in `core`, 3 in `executives`).

- [ ] **Step 3: Commit**

```bash
git add core/templates/core/base.html
git commit -m "Add site navigation"
```

---

### Task 13: Manual verification

This task has no automated test — it's the step described in the project guidelines for confirming a UI feature actually works in a browser, not just in the test suite.

- [ ] **Step 1: Create a superuser**

```bash
.venv/bin/python manage.py createsuperuser
```

Follow the prompts (username/email/password).

- [ ] **Step 2: Start the Tailwind watcher in one terminal**

```bash
.venv/bin/python manage.py tailwind start
```

Leave this running — it rebuilds the CSS automatically as you edit templates.

- [ ] **Step 3: Start the dev server in another terminal**

```bash
.venv/bin/python manage.py runserver
```

- [ ] **Step 4: Check each page in a browser**

- `http://127.0.0.1:8000/` — Home renders with the purple hero section, serif display font on headings, Inter on body text, logos in the header/footer, and a fade-up animation as you scroll.
- `http://127.0.0.1:8000/about/` — About page content renders (SICT history, Philosophy/Vision/Mission cards, Department of Information Technology section).
- `http://127.0.0.1:8000/academics/` — Academics page renders, including the "Detailed course-by-course curriculum..." placeholder box.
- `http://127.0.0.1:8000/executives/` — shows "No current executive has been published yet." (no data seeded yet).

- [ ] **Step 5: Seed an Executive through Django's built-in admin and verify Cloudinary**

Go to `http://127.0.0.1:8000/admin/`, log in with the superuser from Step 1, open **Executives → Add Executive**, fill in a name/position/session, set "Is current" to checked, and upload any photo.

After saving:
- In your Cloudinary dashboard's Media Library, confirm the uploaded image appears there.
- Revisit `http://127.0.0.1:8000/executives/` and confirm the executive now appears, and that viewing the page source shows the photo's `src` pointing at a `res.cloudinary.com` URL (not a local `/media/` path) — this confirms Cloudinary storage is actually wired up end-to-end, not just configured.

- [ ] **Step 6: Confirm the nav and Vote placeholder**

Click through Home/About/Academics/Executive in the nav bar and confirm each loads the right page. Confirm the "Vote" button is visible and styled, even though it doesn't go anywhere yet.

---

## Self-Review Notes

- **Spec coverage:** every section of `2026-10-30-public-website-foundation-design.md` has a corresponding task — architecture (Tasks 5–6, 10), pages/content (Tasks 7–9), design system (Tasks 5–6), Executive model (Task 10), Current Executive view (Task 11), navigation (Task 12), testing (Tasks 7–11 inline, Task 12 full-suite run). Postgres (Tasks 2–3) and Cloudinary (Task 4) are infrastructure choices made at plan time (the spec was silent on DB/storage engine) per your explicit direction.
- **Type/name consistency:** `Executive` fields (`name`, `position`, `photo`, `session`, `is_current`) are identical across the model (Task 10), the admin registration, the view's `get_queryset` filter, and both test files. URL names (`core:home`, `core:about`, `core:academics`, `executives:current`) are consistent between each `urls.py` and every template/test that references them via `{% url %}` or `reverse()`.
- **No placeholders:** the one intentionally-placeholder piece of content (Academics' curriculum note) was explicitly approved during brainstorming as real, permanent UI copy — not a plan gap.
