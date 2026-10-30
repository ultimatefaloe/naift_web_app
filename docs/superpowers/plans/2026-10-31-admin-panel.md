# Admin Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the custom admin dashboard and shared election data model described in `docs/superpowers/specs/2026-10-30-admin-panel-design.md`: a two-tier admin system (Django superuser vs. `AdminProfile`-flagged admins), CRUD for Position/Contestant/Election/Executive, DB-enforced audit trail on Position/Election, and a homepage marquee driven by election status.

**Architecture:** Two new Django apps — `admin_panel` (the `AdminProfile` model, custom auth, and every dashboard view/template) and `elections` (the `Position`/`Election`/`Contestant` data models, consumed by both `admin_panel` now and the voting dashboard later). `AdminProfile` is created first since `Position`/`Election` have a required FK to it.

**Tech Stack:** Django 6.1, same stack as sub-project 1 (Postgres, Cloudinary, Tailwind) — no new third-party packages needed.

---

### Task 1: `admin_panel` app — `AdminProfile` model

**Files:**
- Create: `admin_panel/__init__.py`, `admin_panel/apps.py`
- Create: `admin_panel/models.py`
- Create: `admin_panel/admin.py`
- Create: `admin_panel/tests.py`
- Create: `admin_panel/migrations/0001_initial.py` (generated)
- Modify: `web/settings.py`

- [ ] **Step 1: Write the failing test**

```bash
.venv/bin/python manage.py startapp admin_panel
```

Replace the contents of `admin_panel/tests.py` with:

```python
from django.contrib.auth.models import User
from django.test import TestCase

from .models import AdminProfile


class AdminProfileModelTests(TestCase):
    def test_string_representation(self):
        user = User.objects.create_user(username="admin1", password="pass12345")
        profile = AdminProfile.objects.create(user=user, is_admin=True)
        self.assertEqual(str(profile), "admin1")
```

- [ ] **Step 2: Run it and confirm it fails**

Add `'admin_panel',` to `INSTALLED_APPS` in `web/settings.py` (after `'executives',`) first, so the app is discoverable:

```python
    'core',
    'executives',
    'admin_panel',
```

```bash
.venv/bin/python manage.py test admin_panel
```

Expected: `ImportError` or `AttributeError` — `AdminProfile` doesn't exist in `admin_panel/models.py` yet.

- [ ] **Step 3: Implement the model**

Replace the contents of `admin_panel/models.py` with:

```python
from django.conf import settings
from django.db import models


class AdminProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    is_admin = models.BooleanField(default=False)

    def __str__(self):
        return self.user.username
```

- [ ] **Step 4: Generate and apply the migration**

```bash
.venv/bin/python manage.py makemigrations admin_panel
.venv/bin/python manage.py migrate admin_panel
```

Expected: `Migrations for 'admin_panel': ... 0001_initial.py` then `Applying admin_panel.0001_initial... OK`.

- [ ] **Step 5: Run the test and confirm it passes**

```bash
.venv/bin/python manage.py test admin_panel
```

Expected: `OK` (1 test).

- [ ] **Step 6: Register with Django's built-in admin**

Per the spec, `AdminProfile` is managed exclusively through Django's built-in `/admin/` by the superuser. Replace the contents of `admin_panel/admin.py` with:

```python
from django.contrib import admin

from .models import AdminProfile


@admin.register(AdminProfile)
class AdminProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "is_admin")
    list_filter = ("is_admin",)
```

- [ ] **Step 7: Commit**

```bash
git add admin_panel web/settings.py
git commit -m "Add AdminProfile model with Django admin registration"
```

---

### Task 2: `elections` app — `Position` model

**Files:**
- Create: `elections/__init__.py`, `elections/apps.py`
- Create: `elections/models.py`
- Create: `elections/tests.py`
- Create: `elections/migrations/0001_initial.py` (generated)
- Modify: `web/settings.py`

- [ ] **Step 1: Write the failing tests**

```bash
.venv/bin/python manage.py startapp elections
```

Replace the contents of `elections/tests.py` with:

```python
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase

from admin_panel.models import AdminProfile
from .models import Position


class PositionModelTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="admin1", password="pass12345")
        self.admin_profile = AdminProfile.objects.create(user=user, is_admin=True)

    def test_string_representation(self):
        position = Position.objects.create(title="President", modified_by=self.admin_profile)
        self.assertEqual(str(position), "President")

    def test_save_without_modified_by_raises_integrity_error(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Position.objects.create(title="President")
```

- [ ] **Step 2: Run it and confirm it fails**

Add `'elections',` to `INSTALLED_APPS` in `web/settings.py` (after `'admin_panel',`):

```python
    'admin_panel',
    'elections',
```

```bash
.venv/bin/python manage.py test elections
```

Expected: `ImportError` or `AttributeError` — `Position` doesn't exist in `elections/models.py` yet.

- [ ] **Step 3: Implement the model**

Replace the contents of `elections/models.py` with:

```python
from django.db import models

from admin_panel.models import AdminProfile


class Position(models.Model):
    title = models.CharField(max_length=100)
    modified_by = models.ForeignKey(AdminProfile, on_delete=models.PROTECT)
    modified_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title
```

- [ ] **Step 4: Generate and apply the migration**

```bash
.venv/bin/python manage.py makemigrations elections
.venv/bin/python manage.py migrate elections
```

Expected: `Migrations for 'elections': ... 0001_initial.py` then `Applying elections.0001_initial... OK`.

- [ ] **Step 5: Run the tests and confirm they pass**

```bash
.venv/bin/python manage.py test elections
```

Expected: `OK` (2 tests).

- [ ] **Step 6: Commit**

```bash
git add elections web/settings.py
git commit -m "Add Position model with required modified_by audit FK"
```

---

### Task 3: `elections` app — `Election` model

**Files:**
- Modify: `elections/models.py`
- Modify: `elections/tests.py`

- [ ] **Step 1: Write the failing tests**

Add to `elections/tests.py`:

```python
from .models import Election


class ElectionModelTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="admin2", password="pass12345")
        self.admin_profile = AdminProfile.objects.create(user=user, is_admin=True)

    def test_string_representation(self):
        election = Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            status="upcoming",
            modified_by=self.admin_profile,
        )
        self.assertEqual(str(election), "2026/2027")

    def test_default_status_and_results_published(self):
        election = Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            modified_by=self.admin_profile,
        )
        self.assertEqual(election.status, "upcoming")
        self.assertFalse(election.is_results_published)

    def test_save_without_modified_by_raises_integrity_error(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Election.objects.create(
                    session="2026/2027",
                    start_time="2026-11-01T09:00:00Z",
                    close_time="2026-11-01T17:00:00Z",
                )
```

- [ ] **Step 2: Run it and confirm it fails**

```bash
.venv/bin/python manage.py test elections
```

Expected: `ImportError` or `AttributeError` — `Election` doesn't exist yet.

- [ ] **Step 3: Implement the model**

Add to `elections/models.py`, after the `Position` class:

```python
class Election(models.Model):
    STATUS_UPCOMING = "upcoming"
    STATUS_ONGOING = "ongoing"
    STATUS_ENDED = "ended"
    STATUS_CHOICES = [
        (STATUS_UPCOMING, "Upcoming"),
        (STATUS_ONGOING, "Ongoing"),
        (STATUS_ENDED, "Ended"),
    ]

    session = models.CharField(max_length=20, help_text='e.g. "2026/2027"')
    start_time = models.DateTimeField(help_text="Display label only — does not gate access")
    close_time = models.DateTimeField(help_text="Display label only — does not gate access")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_UPCOMING)
    is_results_published = models.BooleanField(default=False)
    modified_by = models.ForeignKey(AdminProfile, on_delete=models.PROTECT)
    modified_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.session
```

- [ ] **Step 4: Generate and apply the migration**

```bash
.venv/bin/python manage.py makemigrations elections
.venv/bin/python manage.py migrate elections
```

Expected: `Migrations for 'elections': ... 0002_election.py` then `Applying elections.0002_election... OK`.

- [ ] **Step 5: Run the tests and confirm they pass**

```bash
.venv/bin/python manage.py test elections
```

Expected: `OK` (5 tests).

- [ ] **Step 6: Commit**

```bash
git add elections
git commit -m "Add Election model with status enum and results-published flag"
```

---

### Task 4: `elections` app — `Contestant` model

**Files:**
- Modify: `elections/models.py`
- Modify: `elections/tests.py`

- [ ] **Step 1: Write the failing test**

Add to `elections/tests.py`:

```python
from .models import Contestant


class ContestantModelTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="admin3", password="pass12345")
        admin_profile = AdminProfile.objects.create(user=user, is_admin=True)
        self.position = Position.objects.create(title="President", modified_by=admin_profile)
        self.election = Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            modified_by=admin_profile,
        )

    def test_string_representation(self):
        contestant = Contestant.objects.create(
            name="Jane Doe",
            alias="JD",
            manifesto="Vote for progress.",
            position=self.position,
            election=self.election,
        )
        self.assertEqual(str(contestant), "Jane Doe (President)")
```

- [ ] **Step 2: Run it and confirm it fails**

```bash
.venv/bin/python manage.py test elections
```

Expected: `ImportError` or `AttributeError` — `Contestant` doesn't exist yet.

- [ ] **Step 3: Implement the model**

Add to `elections/models.py`, after the `Election` class:

```python
class Contestant(models.Model):
    name = models.CharField(max_length=150)
    alias = models.CharField(max_length=100, blank=True, help_text="Popularly known as")
    photo = models.ImageField(upload_to="contestants/")
    manifesto = models.TextField()
    position = models.ForeignKey(Position, on_delete=models.CASCADE, related_name="contestants")
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name="contestants")

    def __str__(self):
        return f"{self.name} ({self.position.title})"
```

- [ ] **Step 4: Generate and apply the migration**

```bash
.venv/bin/python manage.py makemigrations elections
.venv/bin/python manage.py migrate elections
```

Expected: `Migrations for 'elections': ... 0003_contestant.py` then `Applying elections.0003_contestant... OK`.

- [ ] **Step 5: Run the tests and confirm they pass**

```bash
.venv/bin/python manage.py test elections
```

Expected: `OK` (6 tests).

- [ ] **Step 6: Commit**

```bash
git add elections
git commit -m "Add Contestant model scoped to Position and Election"
```

---

### Task 5: `admin_panel` — base layout, login/logout, access control, dashboard home

**Files:**
- Create: `admin_panel/templates/admin_panel/base.html`
- Create: `admin_panel/templates/admin_panel/login.html`
- Create: `admin_panel/templates/admin_panel/dashboard.html`
- Create: `admin_panel/mixins.py`
- Create: `admin_panel/views.py`
- Create: `admin_panel/urls.py`
- Modify: `admin_panel/tests.py`
- Modify: `web/urls.py`
- Modify: `web/settings.py`

- [ ] **Step 1: Write the failing tests**

Add to `admin_panel/tests.py`:

```python
from django.urls import reverse


class DashboardAccessTests(TestCase):
    def setUp(self):
        self.non_admin = User.objects.create_user(username="student1", password="pass12345")
        self.admin_user = User.objects.create_user(username="admin4", password="pass12345")
        AdminProfile.objects.create(user=self.admin_user, is_admin=True)

    def test_unauthenticated_user_redirected_to_login(self):
        response = self.client.get(reverse("admin_panel:dashboard"))
        self.assertRedirects(response, reverse("admin_panel:login"))

    def test_authenticated_non_admin_redirected_to_login(self):
        self.client.force_login(self.non_admin)
        response = self.client.get(reverse("admin_panel:dashboard"))
        self.assertRedirects(response, reverse("admin_panel:login"))

    def test_admin_can_access_dashboard(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("admin_panel:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin_panel/dashboard.html")


class LoginViewTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username="admin5", password="pass12345")
        AdminProfile.objects.create(user=self.admin_user, is_admin=True)

    def test_valid_credentials_log_the_user_in(self):
        response = self.client.post(
            reverse("admin_panel:login"),
            {"username": "admin5", "password": "pass12345"},
        )
        self.assertRedirects(response, reverse("admin_panel:dashboard"))

    def test_invalid_credentials_show_error(self):
        response = self.client.post(
            reverse("admin_panel:login"),
            {"username": "admin5", "password": "wrongpassword"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid username or password.")
```

- [ ] **Step 2: Run it and confirm it fails**

```bash
.venv/bin/python manage.py test admin_panel
```

Expected: `NoReverseMatch` — `admin_panel:dashboard`/`admin_panel:login` don't exist yet.

- [ ] **Step 3: Implement the access-control mixin**

Create `admin_panel/mixins.py`:

```python
from django.contrib import messages
from django.shortcuts import redirect


class AdminRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("admin_panel:login")
        if not hasattr(request.user, "adminprofile") or not request.user.adminprofile.is_admin:
            messages.error(request, "You are not authorized to access the admin dashboard.")
            return redirect("admin_panel:login")
        return super().dispatch(request, *args, **kwargs)
```

- [ ] **Step 4: Implement the views**

Create `admin_panel/views.py`:

```python
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.generic import TemplateView

from elections.models import Contestant, Election, Position
from executives.models import Executive
from .mixins import AdminRequiredMixin


def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username", "")
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            auth_login(request, user)
            return redirect("admin_panel:dashboard")
        messages.error(request, "Invalid username or password.")
    return render(request, "admin_panel/login.html")


def logout_view(request):
    auth_logout(request)
    return redirect("admin_panel:login")


class DashboardView(AdminRequiredMixin, TemplateView):
    template_name = "admin_panel/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["position_count"] = Position.objects.count()
        context["contestant_count"] = Contestant.objects.count()
        context["executive_count"] = Executive.objects.count()
        context["current_election"] = Election.objects.order_by("-id").first()
        return context
```

- [ ] **Step 5: Wire the URLs**

Create `admin_panel/urls.py`:

```python
from django.urls import path

from . import views

app_name = "admin_panel"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("", views.DashboardView.as_view(), name="dashboard"),
]
```

In `web/urls.py`, change:

```python
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('executives/', include('executives.urls')),
]
```

to:

```python
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('executives/', include('executives.urls')),
    path('dashboard/', include('admin_panel.urls')),
]
```

- [ ] **Step 6: Write the templates**

Create `admin_panel/templates/admin_panel/base.html`:

```html
{% load static tailwind_tags %}
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Admin · NAIFT{% endblock %}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300..900;1,9..144,300..900&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    {% tailwind_css %}
</head>
<body class="bg-brand-white text-brand-black font-body">
    {% if user.is_authenticated %}
    <header class="flex items-center justify-between px-6 py-4 bg-brand-black text-brand-white">
        <span class="font-display text-xl">NAIFT Admin</span>
        <nav class="flex items-center gap-6 font-body">
            <a href="{% url 'admin_panel:dashboard' %}" class="hover:text-brand-purple">Dashboard</a>
            <a href="{% url 'admin_panel:position_list' %}" class="hover:text-brand-purple">Positions</a>
            <a href="{% url 'admin_panel:contestant_list' %}" class="hover:text-brand-purple">Contestants</a>
            <a href="{% url 'admin_panel:executive_list' %}" class="hover:text-brand-purple">Executives</a>
            <a href="{% url 'admin_panel:election_list' %}" class="hover:text-brand-purple">Elections</a>
            <form method="post" action="{% url 'admin_panel:logout' %}" class="inline">
                {% csrf_token %}
                <button type="submit" class="hover:text-brand-purple">Logout</button>
            </form>
        </nav>
    </header>
    {% endif %}

    <main class="px-6 py-10 max-w-5xl mx-auto">
        {% if messages %}
            {% for message in messages %}
                <div class="mb-6 px-4 py-3 rounded bg-brand-purple/10 text-brand-purple">{{ message }}</div>
            {% endfor %}
        {% endif %}
        {% block content %}{% endblock %}
    </main>
</body>
</html>
```

Note: the nav links to `position_list`/`contestant_list`/`executive_list`/`election_list` don't exist until later tasks — that's fine, this template isn't rendered with `user.is_authenticated` True until Task 6+ adds real data to test against, but to avoid breaking the login/dashboard tests in *this* task, those URLs must resolve. Since Django template `{% url %}` raises `NoReverseMatch` at render time if the name doesn't exist, add placeholder URL entries now in `admin_panel/urls.py` pointing at the dashboard itself, to be replaced with real views in Tasks 6-9:

Update `admin_panel/urls.py` to:

```python
from django.urls import path

from . import views

app_name = "admin_panel"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("positions/", views.DashboardView.as_view(), name="position_list"),
    path("contestants/", views.DashboardView.as_view(), name="contestant_list"),
    path("executives/", views.DashboardView.as_view(), name="executive_list"),
    path("elections/", views.DashboardView.as_view(), name="election_list"),
]
```

(Tasks 6-9 will replace each of these four placeholder lines with the real list view as that CRUD section is built.)

Create `admin_panel/templates/admin_panel/login.html`:

```html
{% extends "admin_panel/base.html" %}

{% block title %}Admin Login · NAIFT{% endblock %}

{% block content %}
<div class="max-w-sm mx-auto mt-16">
    <h1 class="font-display text-3xl text-brand-purple mb-6 text-center">Admin Login</h1>
    <form method="post" class="flex flex-col gap-4">
        {% csrf_token %}
        <input type="text" name="username" placeholder="Username" required class="border border-brand-black/20 rounded px-4 py-2">
        <input type="password" name="password" placeholder="Password" required class="border border-brand-black/20 rounded px-4 py-2">
        <button type="submit" class="bg-brand-purple text-brand-white px-4 py-2 rounded hover:opacity-90">Log in</button>
    </form>
</div>
{% endblock %}
```

Create `admin_panel/templates/admin_panel/dashboard.html`:

```html
{% extends "admin_panel/base.html" %}

{% block title %}Dashboard · NAIFT Admin{% endblock %}

{% block content %}
<h1 class="font-display text-3xl text-brand-purple mb-8">Dashboard</h1>

<div class="grid sm:grid-cols-2 md:grid-cols-4 gap-6 mb-10">
    <div class="border border-brand-purple/20 rounded-lg p-5 text-center">
        <p class="text-3xl font-display text-brand-purple">{{ position_count }}</p>
        <p>Positions</p>
    </div>
    <div class="border border-brand-purple/20 rounded-lg p-5 text-center">
        <p class="text-3xl font-display text-brand-purple">{{ contestant_count }}</p>
        <p>Contestants</p>
    </div>
    <div class="border border-brand-purple/20 rounded-lg p-5 text-center">
        <p class="text-3xl font-display text-brand-purple">{{ executive_count }}</p>
        <p>Executives</p>
    </div>
    <div class="border border-brand-purple/20 rounded-lg p-5 text-center">
        <p class="text-3xl font-display text-brand-purple">{% if current_election %}{{ current_election.get_status_display }}{% else %}None{% endif %}</p>
        <p>Current Election</p>
    </div>
</div>
{% endblock %}
```

- [ ] **Step 7: Run the tests and confirm they pass**

```bash
.venv/bin/python manage.py test admin_panel
```

Expected: `OK` (6 tests).

- [ ] **Step 8: Commit**

```bash
git add admin_panel web/urls.py
git commit -m "Add admin login/logout, access control, and dashboard home"
```

---

### Task 6: `admin_panel` — Position CRUD

**Files:**
- Modify: `admin_panel/views.py`
- Modify: `admin_panel/urls.py`
- Create: `admin_panel/templates/admin_panel/position_list.html`
- Create: `admin_panel/templates/admin_panel/position_form.html`
- Create: `admin_panel/templates/admin_panel/position_confirm_delete.html`
- Modify: `admin_panel/tests.py`

- [ ] **Step 1: Write the failing tests**

Add to `admin_panel/tests.py`:

```python
from elections.models import Position


class PositionCRUDTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username="admin6", password="pass12345")
        self.admin_profile = AdminProfile.objects.create(user=self.admin_user, is_admin=True)
        self.client.force_login(self.admin_user)

    def test_list_view_returns_200(self):
        response = self.client.get(reverse("admin_panel:position_list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin_panel/position_list.html")

    def test_create_sets_modified_by(self):
        response = self.client.post(reverse("admin_panel:position_create"), {"title": "President"})
        self.assertRedirects(response, reverse("admin_panel:position_list"))
        position = Position.objects.get(title="President")
        self.assertEqual(position.modified_by, self.admin_profile)

    def test_update_position(self):
        position = Position.objects.create(title="Secretary", modified_by=self.admin_profile)
        response = self.client.post(
            reverse("admin_panel:position_update", args=[position.pk]), {"title": "General Secretary"}
        )
        self.assertRedirects(response, reverse("admin_panel:position_list"))
        position.refresh_from_db()
        self.assertEqual(position.title, "General Secretary")

    def test_delete_position(self):
        position = Position.objects.create(title="Treasurer", modified_by=self.admin_profile)
        response = self.client.post(reverse("admin_panel:position_delete", args=[position.pk]))
        self.assertRedirects(response, reverse("admin_panel:position_list"))
        self.assertFalse(Position.objects.filter(pk=position.pk).exists())
```

- [ ] **Step 2: Run it and confirm it fails**

```bash
.venv/bin/python manage.py test admin_panel
```

Expected: `NoReverseMatch` — `admin_panel:position_create`/`position_update`/`position_delete` don't exist yet.

- [ ] **Step 3: Implement the views**

Add to `admin_panel/views.py`, after the imports (extend the `elections.models` import line) and after `DashboardView`:

Change the import line:

```python
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, TemplateView, UpdateView

from elections.models import Contestant, Election, Position
```

Add at the end of the file:

```python
class PositionListView(AdminRequiredMixin, ListView):
    model = Position
    template_name = "admin_panel/position_list.html"
    context_object_name = "positions"


class PositionCreateView(AdminRequiredMixin, CreateView):
    model = Position
    fields = ["title"]
    template_name = "admin_panel/position_form.html"
    success_url = reverse_lazy("admin_panel:position_list")

    def form_valid(self, form):
        form.instance.modified_by = self.request.user.adminprofile
        return super().form_valid(form)


class PositionUpdateView(AdminRequiredMixin, UpdateView):
    model = Position
    fields = ["title"]
    template_name = "admin_panel/position_form.html"
    success_url = reverse_lazy("admin_panel:position_list")

    def form_valid(self, form):
        form.instance.modified_by = self.request.user.adminprofile
        return super().form_valid(form)


class PositionDeleteView(AdminRequiredMixin, DeleteView):
    model = Position
    template_name = "admin_panel/position_confirm_delete.html"
    success_url = reverse_lazy("admin_panel:position_list")
```

- [ ] **Step 4: Wire the URLs**

In `admin_panel/urls.py`, replace the single placeholder line:

```python
    path("positions/", views.DashboardView.as_view(), name="position_list"),
```

with:

```python
    path("positions/", views.PositionListView.as_view(), name="position_list"),
    path("positions/add/", views.PositionCreateView.as_view(), name="position_create"),
    path("positions/<int:pk>/edit/", views.PositionUpdateView.as_view(), name="position_update"),
    path("positions/<int:pk>/delete/", views.PositionDeleteView.as_view(), name="position_delete"),
```

- [ ] **Step 5: Write the templates**

Create `admin_panel/templates/admin_panel/position_list.html`:

```html
{% extends "admin_panel/base.html" %}

{% block title %}Positions · NAIFT Admin{% endblock %}

{% block content %}
<div class="flex items-center justify-between mb-8">
    <h1 class="font-display text-3xl text-brand-purple">Positions</h1>
    <a href="{% url 'admin_panel:position_create' %}" class="bg-brand-purple text-brand-white px-4 py-2 rounded hover:opacity-90">Add Position</a>
</div>

<table class="w-full text-left border-collapse">
    <thead>
        <tr class="border-b border-brand-black/10">
            <th class="py-2">Title</th>
            <th class="py-2">Last modified by</th>
            <th class="py-2"></th>
        </tr>
    </thead>
    <tbody>
        {% for position in positions %}
            <tr class="border-b border-brand-black/10">
                <td class="py-2">{{ position.title }}</td>
                <td class="py-2">{{ position.modified_by }}</td>
                <td class="py-2 text-right">
                    <a href="{% url 'admin_panel:position_update' position.pk %}" class="text-brand-purple hover:underline">Edit</a>
                    &middot;
                    <a href="{% url 'admin_panel:position_delete' position.pk %}" class="text-brand-purple hover:underline">Delete</a>
                </td>
            </tr>
        {% empty %}
            <tr><td colspan="3" class="py-4">No positions yet.</td></tr>
        {% endfor %}
    </tbody>
</table>
{% endblock %}
```

Create `admin_panel/templates/admin_panel/position_form.html`:

```html
{% extends "admin_panel/base.html" %}

{% block title %}Position · NAIFT Admin{% endblock %}

{% block content %}
<h1 class="font-display text-3xl text-brand-purple mb-8">{% if object %}Edit{% else %}Add{% endif %} Position</h1>

<form method="post" class="flex flex-col gap-4 max-w-md">
    {% csrf_token %}
    {{ form.as_p }}
    <button type="submit" class="bg-brand-purple text-brand-white px-4 py-2 rounded hover:opacity-90">Save</button>
</form>
{% endblock %}
```

Create `admin_panel/templates/admin_panel/position_confirm_delete.html`:

```html
{% extends "admin_panel/base.html" %}

{% block title %}Delete Position · NAIFT Admin{% endblock %}

{% block content %}
<h1 class="font-display text-3xl text-brand-purple mb-8">Delete Position</h1>
<p class="mb-6">Are you sure you want to delete "{{ object.title }}"?</p>
<form method="post">
    {% csrf_token %}
    <button type="submit" class="bg-brand-purple text-brand-white px-4 py-2 rounded hover:opacity-90">Confirm Delete</button>
    <a href="{% url 'admin_panel:position_list' %}" class="ml-4 text-brand-purple hover:underline">Cancel</a>
</form>
{% endblock %}
```

- [ ] **Step 6: Run the tests and confirm they pass**

```bash
.venv/bin/python manage.py test admin_panel
```

Expected: `OK` (10 tests).

- [ ] **Step 7: Commit**

```bash
git add admin_panel
git commit -m "Add Position CRUD dashboard views"
```

---

### Task 7: `admin_panel` — Contestant CRUD

**Files:**
- Modify: `admin_panel/views.py`
- Modify: `admin_panel/urls.py`
- Create: `admin_panel/templates/admin_panel/contestant_list.html`
- Create: `admin_panel/templates/admin_panel/contestant_form.html`
- Create: `admin_panel/templates/admin_panel/contestant_confirm_delete.html`
- Modify: `admin_panel/tests.py`

- [ ] **Step 1: Write the failing tests**

Add to `admin_panel/tests.py`:

```python
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from elections.models import Contestant, Election

TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(STORAGES=TEST_STORAGES)
class ContestantCRUDTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username="admin7", password="pass12345")
        self.admin_profile = AdminProfile.objects.create(user=self.admin_user, is_admin=True)
        self.client.force_login(self.admin_user)
        self.position = Position.objects.create(title="President", modified_by=self.admin_profile)
        self.election = Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            modified_by=self.admin_profile,
        )

    def test_list_view_returns_200(self):
        response = self.client.get(reverse("admin_panel:contestant_list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin_panel/contestant_list.html")

    def test_create_contestant(self):
        # A minimal valid 1x1 GIF — ImageField validates uploads are real images via
        # Pillow, so arbitrary bytes (e.g. b"fake-image-bytes") fail validation.
        gif_1px = (
            b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04"
            b"\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
        )
        photo = SimpleUploadedFile("candidate.gif", gif_1px, content_type="image/gif")
        response = self.client.post(
            reverse("admin_panel:contestant_create"),
            {
                "name": "Jane Doe",
                "alias": "JD",
                "manifesto": "Vote for progress.",
                "position": self.position.pk,
                "election": self.election.pk,
                "photo": photo,
            },
        )
        self.assertRedirects(response, reverse("admin_panel:contestant_list"))
        self.assertTrue(Contestant.objects.filter(name="Jane Doe").exists())

    def test_delete_contestant(self):
        contestant = Contestant.objects.create(
            name="John Smith",
            alias="JS",
            manifesto="Vote for stability.",
            position=self.position,
            election=self.election,
        )
        response = self.client.post(reverse("admin_panel:contestant_delete", args=[contestant.pk]))
        self.assertRedirects(response, reverse("admin_panel:contestant_list"))
        self.assertFalse(Contestant.objects.filter(pk=contestant.pk).exists())
```

Note: `@override_settings(STORAGES=TEST_STORAGES)` on the class swaps the default file storage to Django's in-memory backend for every test in this class. Without it, `test_create_contestant`'s real file upload would go through the project's actual default storage — Cloudinary, configured in `web/settings.py` — making the test hit a live external API (slow, network-dependent, and would fail outright with blank Cloudinary credentials). `Position`/`Executive` tests elsewhere in this plan avoid this by never supplying a `photo`/`image` value through a form (Django's ORM `.objects.create()` doesn't validate `blank=False` the way a `ModelForm` does), but this test specifically needs to exercise a real upload through the form to prove the Contestant create view works end-to-end, so it isolates storage instead.

- [ ] **Step 2: Run it and confirm it fails**

```bash
.venv/bin/python manage.py test admin_panel
```

Expected: `NoReverseMatch` — `admin_panel:contestant_create`/`contestant_delete` don't exist yet.

- [ ] **Step 3: Implement the views**

Add to `admin_panel/views.py`, at the end of the file:

```python
class ContestantListView(AdminRequiredMixin, ListView):
    model = Contestant
    template_name = "admin_panel/contestant_list.html"
    context_object_name = "contestants"


class ContestantCreateView(AdminRequiredMixin, CreateView):
    model = Contestant
    fields = ["name", "alias", "manifesto", "position", "election", "photo"]
    template_name = "admin_panel/contestant_form.html"
    success_url = reverse_lazy("admin_panel:contestant_list")


class ContestantUpdateView(AdminRequiredMixin, UpdateView):
    model = Contestant
    fields = ["name", "alias", "manifesto", "position", "election", "photo"]
    template_name = "admin_panel/contestant_form.html"
    success_url = reverse_lazy("admin_panel:contestant_list")


class ContestantDeleteView(AdminRequiredMixin, DeleteView):
    model = Contestant
    template_name = "admin_panel/contestant_confirm_delete.html"
    success_url = reverse_lazy("admin_panel:contestant_list")
```

Note: `Contestant` has no `modified_by` field (not in the spec's audit scope), so unlike `Position`'s views, these don't override `form_valid`.

- [ ] **Step 4: Wire the URLs**

In `admin_panel/urls.py`, replace:

```python
    path("contestants/", views.DashboardView.as_view(), name="contestant_list"),
```

with:

```python
    path("contestants/", views.ContestantListView.as_view(), name="contestant_list"),
    path("contestants/add/", views.ContestantCreateView.as_view(), name="contestant_create"),
    path("contestants/<int:pk>/edit/", views.ContestantUpdateView.as_view(), name="contestant_update"),
    path("contestants/<int:pk>/delete/", views.ContestantDeleteView.as_view(), name="contestant_delete"),
```

- [ ] **Step 5: Write the templates**

Create `admin_panel/templates/admin_panel/contestant_list.html`:

```html
{% extends "admin_panel/base.html" %}

{% block title %}Contestants · NAIFT Admin{% endblock %}

{% block content %}
<div class="flex items-center justify-between mb-8">
    <h1 class="font-display text-3xl text-brand-purple">Contestants</h1>
    <a href="{% url 'admin_panel:contestant_create' %}" class="bg-brand-purple text-brand-white px-4 py-2 rounded hover:opacity-90">Add Contestant</a>
</div>

<table class="w-full text-left border-collapse">
    <thead>
        <tr class="border-b border-brand-black/10">
            <th class="py-2">Name</th>
            <th class="py-2">Position</th>
            <th class="py-2">Election</th>
            <th class="py-2"></th>
        </tr>
    </thead>
    <tbody>
        {% for contestant in contestants %}
            <tr class="border-b border-brand-black/10">
                <td class="py-2">{{ contestant.name }}{% if contestant.alias %} ({{ contestant.alias }}){% endif %}</td>
                <td class="py-2">{{ contestant.position }}</td>
                <td class="py-2">{{ contestant.election }}</td>
                <td class="py-2 text-right">
                    <a href="{% url 'admin_panel:contestant_update' contestant.pk %}" class="text-brand-purple hover:underline">Edit</a>
                    &middot;
                    <a href="{% url 'admin_panel:contestant_delete' contestant.pk %}" class="text-brand-purple hover:underline">Delete</a>
                </td>
            </tr>
        {% empty %}
            <tr><td colspan="4" class="py-4">No contestants yet.</td></tr>
        {% endfor %}
    </tbody>
</table>
{% endblock %}
```

Create `admin_panel/templates/admin_panel/contestant_form.html`:

```html
{% extends "admin_panel/base.html" %}

{% block title %}Contestant · NAIFT Admin{% endblock %}

{% block content %}
<h1 class="font-display text-3xl text-brand-purple mb-8">{% if object %}Edit{% else %}Add{% endif %} Contestant</h1>

<form method="post" enctype="multipart/form-data" class="flex flex-col gap-4 max-w-md">
    {% csrf_token %}
    {{ form.as_p }}
    <button type="submit" class="bg-brand-purple text-brand-white px-4 py-2 rounded hover:opacity-90">Save</button>
</form>
{% endblock %}
```

Create `admin_panel/templates/admin_panel/contestant_confirm_delete.html`:

```html
{% extends "admin_panel/base.html" %}

{% block title %}Delete Contestant · NAIFT Admin{% endblock %}

{% block content %}
<h1 class="font-display text-3xl text-brand-purple mb-8">Delete Contestant</h1>
<p class="mb-6">Are you sure you want to delete "{{ object.name }}"?</p>
<form method="post">
    {% csrf_token %}
    <button type="submit" class="bg-brand-purple text-brand-white px-4 py-2 rounded hover:opacity-90">Confirm Delete</button>
    <a href="{% url 'admin_panel:contestant_list' %}" class="ml-4 text-brand-purple hover:underline">Cancel</a>
</form>
{% endblock %}
```

- [ ] **Step 6: Run the tests and confirm they pass**

```bash
.venv/bin/python manage.py test admin_panel
```

Expected: `OK` (13 tests).

- [ ] **Step 7: Commit**

```bash
git add admin_panel
git commit -m "Add Contestant CRUD dashboard views"
```

---

### Task 8: `admin_panel` — Executive CRUD

**Files:**
- Modify: `admin_panel/views.py`
- Modify: `admin_panel/urls.py`
- Create: `admin_panel/templates/admin_panel/executive_list.html`
- Create: `admin_panel/templates/admin_panel/executive_form.html`
- Create: `admin_panel/templates/admin_panel/executive_confirm_delete.html`
- Modify: `admin_panel/tests.py`

- [ ] **Step 1: Write the failing tests**

Add to `admin_panel/tests.py`:

```python
from executives.models import Executive


class ExecutiveCRUDTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username="admin8", password="pass12345")
        AdminProfile.objects.create(user=self.admin_user, is_admin=True)
        self.client.force_login(self.admin_user)

    def test_list_view_returns_200(self):
        response = self.client.get(reverse("admin_panel:executive_list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin_panel/executive_list.html")

    def test_delete_executive(self):
        executive = Executive.objects.create(
            name="Jane Doe", position="President", session="2026/2027", is_current=True
        )
        response = self.client.post(reverse("admin_panel:executive_delete", args=[executive.pk]))
        self.assertRedirects(response, reverse("admin_panel:executive_list"))
        self.assertFalse(Executive.objects.filter(pk=executive.pk).exists())
```

- [ ] **Step 2: Run it and confirm it fails**

```bash
.venv/bin/python manage.py test admin_panel
```

Expected: `NoReverseMatch` — `admin_panel:executive_delete` doesn't exist yet.

- [ ] **Step 3: Implement the views**

Change the `executives.models` import line in `admin_panel/views.py`:

```python
from executives.models import Executive
```

Add to the end of `admin_panel/views.py`:

```python
class ExecutiveListView(AdminRequiredMixin, ListView):
    model = Executive
    template_name = "admin_panel/executive_list.html"
    context_object_name = "executives"


class ExecutiveCreateView(AdminRequiredMixin, CreateView):
    model = Executive
    fields = ["name", "position", "photo", "session", "is_current"]
    template_name = "admin_panel/executive_form.html"
    success_url = reverse_lazy("admin_panel:executive_list")


class ExecutiveUpdateView(AdminRequiredMixin, UpdateView):
    model = Executive
    fields = ["name", "position", "photo", "session", "is_current"]
    template_name = "admin_panel/executive_form.html"
    success_url = reverse_lazy("admin_panel:executive_list")


class ExecutiveDeleteView(AdminRequiredMixin, DeleteView):
    model = Executive
    template_name = "admin_panel/executive_confirm_delete.html"
    success_url = reverse_lazy("admin_panel:executive_list")
```

- [ ] **Step 4: Wire the URLs**

In `admin_panel/urls.py`, replace:

```python
    path("executives/", views.DashboardView.as_view(), name="executive_list"),
```

with:

```python
    path("executives/", views.ExecutiveListView.as_view(), name="executive_list"),
    path("executives/add/", views.ExecutiveCreateView.as_view(), name="executive_create"),
    path("executives/<int:pk>/edit/", views.ExecutiveUpdateView.as_view(), name="executive_update"),
    path("executives/<int:pk>/delete/", views.ExecutiveDeleteView.as_view(), name="executive_delete"),
```

- [ ] **Step 5: Write the templates**

Create `admin_panel/templates/admin_panel/executive_list.html`:

```html
{% extends "admin_panel/base.html" %}

{% block title %}Executives · NAIFT Admin{% endblock %}

{% block content %}
<div class="flex items-center justify-between mb-8">
    <h1 class="font-display text-3xl text-brand-purple">Executives</h1>
    <a href="{% url 'admin_panel:executive_create' %}" class="bg-brand-purple text-brand-white px-4 py-2 rounded hover:opacity-90">Add Executive</a>
</div>

<table class="w-full text-left border-collapse">
    <thead>
        <tr class="border-b border-brand-black/10">
            <th class="py-2">Name</th>
            <th class="py-2">Position</th>
            <th class="py-2">Session</th>
            <th class="py-2">Current?</th>
            <th class="py-2"></th>
        </tr>
    </thead>
    <tbody>
        {% for executive in executives %}
            <tr class="border-b border-brand-black/10">
                <td class="py-2">{{ executive.name }}</td>
                <td class="py-2">{{ executive.position }}</td>
                <td class="py-2">{{ executive.session }}</td>
                <td class="py-2">{% if executive.is_current %}Yes{% else %}No{% endif %}</td>
                <td class="py-2 text-right">
                    <a href="{% url 'admin_panel:executive_update' executive.pk %}" class="text-brand-purple hover:underline">Edit</a>
                    &middot;
                    <a href="{% url 'admin_panel:executive_delete' executive.pk %}" class="text-brand-purple hover:underline">Delete</a>
                </td>
            </tr>
        {% empty %}
            <tr><td colspan="5" class="py-4">No executives yet.</td></tr>
        {% endfor %}
    </tbody>
</table>
{% endblock %}
```

Create `admin_panel/templates/admin_panel/executive_form.html`:

```html
{% extends "admin_panel/base.html" %}

{% block title %}Executive · NAIFT Admin{% endblock %}

{% block content %}
<h1 class="font-display text-3xl text-brand-purple mb-8">{% if object %}Edit{% else %}Add{% endif %} Executive</h1>

<form method="post" enctype="multipart/form-data" class="flex flex-col gap-4 max-w-md">
    {% csrf_token %}
    {{ form.as_p }}
    <button type="submit" class="bg-brand-purple text-brand-white px-4 py-2 rounded hover:opacity-90">Save</button>
</form>
{% endblock %}
```

Create `admin_panel/templates/admin_panel/executive_confirm_delete.html`:

```html
{% extends "admin_panel/base.html" %}

{% block title %}Delete Executive · NAIFT Admin{% endblock %}

{% block content %}
<h1 class="font-display text-3xl text-brand-purple mb-8">Delete Executive</h1>
<p class="mb-6">Are you sure you want to delete "{{ object.name }}"?</p>
<form method="post">
    {% csrf_token %}
    <button type="submit" class="bg-brand-purple text-brand-white px-4 py-2 rounded hover:opacity-90">Confirm Delete</button>
    <a href="{% url 'admin_panel:executive_list' %}" class="ml-4 text-brand-purple hover:underline">Cancel</a>
</form>
{% endblock %}
```

- [ ] **Step 6: Run the tests and confirm they pass**

```bash
.venv/bin/python manage.py test admin_panel
```

Expected: `OK` (15 tests).

- [ ] **Step 7: Commit**

```bash
git add admin_panel
git commit -m "Add Executive CRUD dashboard views"
```

---

### Task 9: `admin_panel` — Election create/edit

**Files:**
- Create: `admin_panel/forms.py`
- Modify: `admin_panel/views.py`
- Modify: `admin_panel/urls.py`
- Create: `admin_panel/templates/admin_panel/election_list.html`
- Create: `admin_panel/templates/admin_panel/election_form.html`
- Modify: `admin_panel/tests.py`

- [ ] **Step 1: Write the failing tests**

Add to `admin_panel/tests.py`:

```python
class ElectionCRUDTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username="admin9", password="pass12345")
        self.admin_profile = AdminProfile.objects.create(user=self.admin_user, is_admin=True)
        self.client.force_login(self.admin_user)

    def test_list_view_returns_200(self):
        response = self.client.get(reverse("admin_panel:election_list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin_panel/election_list.html")

    def test_create_election_sets_modified_by(self):
        response = self.client.post(
            reverse("admin_panel:election_create"),
            {
                "session": "2026/2027",
                "start_time": "2026-11-01T09:00",
                "close_time": "2026-11-01T17:00",
                "status": "upcoming",
            },
        )
        self.assertRedirects(response, reverse("admin_panel:election_list"))
        election = Election.objects.get(session="2026/2027")
        self.assertEqual(election.modified_by, self.admin_profile)
        self.assertFalse(election.is_results_published)

    def test_update_election_status(self):
        election = Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            modified_by=self.admin_profile,
        )
        response = self.client.post(
            reverse("admin_panel:election_update", args=[election.pk]),
            {
                "session": "2026/2027",
                "start_time": "2026-11-01T09:00",
                "close_time": "2026-11-01T17:00",
                "status": "ongoing",
                "is_results_published": "",
            },
        )
        self.assertRedirects(response, reverse("admin_panel:election_list"))
        election.refresh_from_db()
        self.assertEqual(election.status, "ongoing")
```

- [ ] **Step 2: Run it and confirm it fails**

```bash
.venv/bin/python manage.py test admin_panel
```

Expected: `NoReverseMatch` — `admin_panel:election_create`/`election_update` don't exist yet.

- [ ] **Step 3: Implement the form**

Create `admin_panel/forms.py`:

```python
from django import forms

from elections.models import Election


class ElectionForm(forms.ModelForm):
    class Meta:
        model = Election
        fields = ["session", "start_time", "close_time", "status", "is_results_published"]
        widgets = {
            "start_time": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "close_time": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }
```

- [ ] **Step 4: Implement the views**

Add `from .forms import ElectionForm` to the imports at the top of `admin_panel/views.py`.

Add to the end of `admin_panel/views.py`:

```python
class ElectionListView(AdminRequiredMixin, ListView):
    model = Election
    template_name = "admin_panel/election_list.html"
    context_object_name = "elections"


class ElectionCreateView(AdminRequiredMixin, CreateView):
    model = Election
    form_class = ElectionForm
    template_name = "admin_panel/election_form.html"
    success_url = reverse_lazy("admin_panel:election_list")

    def form_valid(self, form):
        form.instance.modified_by = self.request.user.adminprofile
        return super().form_valid(form)


class ElectionUpdateView(AdminRequiredMixin, UpdateView):
    model = Election
    form_class = ElectionForm
    template_name = "admin_panel/election_form.html"
    success_url = reverse_lazy("admin_panel:election_list")

    def form_valid(self, form):
        form.instance.modified_by = self.request.user.adminprofile
        return super().form_valid(form)
```

- [ ] **Step 5: Wire the URLs**

In `admin_panel/urls.py`, replace:

```python
    path("elections/", views.DashboardView.as_view(), name="election_list"),
```

with:

```python
    path("elections/", views.ElectionListView.as_view(), name="election_list"),
    path("elections/add/", views.ElectionCreateView.as_view(), name="election_create"),
    path("elections/<int:pk>/edit/", views.ElectionUpdateView.as_view(), name="election_update"),
```

- [ ] **Step 6: Write the templates**

Create `admin_panel/templates/admin_panel/election_list.html`:

```html
{% extends "admin_panel/base.html" %}

{% block title %}Elections · NAIFT Admin{% endblock %}

{% block content %}
<div class="flex items-center justify-between mb-8">
    <h1 class="font-display text-3xl text-brand-purple">Elections</h1>
    <a href="{% url 'admin_panel:election_create' %}" class="bg-brand-purple text-brand-white px-4 py-2 rounded hover:opacity-90">Add Election</a>
</div>

<table class="w-full text-left border-collapse">
    <thead>
        <tr class="border-b border-brand-black/10">
            <th class="py-2">Session</th>
            <th class="py-2">Status</th>
            <th class="py-2">Results Published?</th>
            <th class="py-2"></th>
        </tr>
    </thead>
    <tbody>
        {% for election in elections %}
            <tr class="border-b border-brand-black/10">
                <td class="py-2">{{ election.session }}</td>
                <td class="py-2">{{ election.get_status_display }}</td>
                <td class="py-2">{% if election.is_results_published %}Yes{% else %}No{% endif %}</td>
                <td class="py-2 text-right">
                    <a href="{% url 'admin_panel:election_update' election.pk %}" class="text-brand-purple hover:underline">Edit</a>
                    &middot;
                    <a href="{% url 'admin_panel:election_results' election.pk %}" class="text-brand-purple hover:underline">Results</a>
                </td>
            </tr>
        {% empty %}
            <tr><td colspan="4" class="py-4">No elections yet.</td></tr>
        {% endfor %}
    </tbody>
</table>
{% endblock %}
```

Create `admin_panel/templates/admin_panel/election_form.html`:

```html
{% extends "admin_panel/base.html" %}

{% block title %}Election · NAIFT Admin{% endblock %}

{% block content %}
<h1 class="font-display text-3xl text-brand-purple mb-8">{% if object %}Edit{% else %}Add{% endif %} Election</h1>

<form method="post" class="flex flex-col gap-4 max-w-md">
    {% csrf_token %}
    {{ form.as_p }}
    <button type="submit" class="bg-brand-purple text-brand-white px-4 py-2 rounded hover:opacity-90">Save</button>
</form>
{% endblock %}
```

- [ ] **Step 7: Run the tests and confirm they pass**

Note: `election_results` is referenced in `election_list.html` but not built until Task 10 — this will cause a `NoReverseMatch` when rendering the list template if any elections exist in a test. Since `test_list_view_returns_200` in this task runs with zero elections (empty table body via `{% empty %}`), the `{% url 'admin_panel:election_results' %}` tag inside the `{% for %}` loop is never evaluated, so it's safe for now. Task 10 adds the real route before any test creates an election and then views the list page.

```bash
.venv/bin/python manage.py test admin_panel
```

Expected: `OK` (18 tests).

- [ ] **Step 8: Commit**

```bash
git add admin_panel
git commit -m "Add Election create/edit dashboard views"
```

---

### Task 10: `admin_panel` — Election results view

**Files:**
- Modify: `admin_panel/views.py`
- Modify: `admin_panel/urls.py`
- Create: `admin_panel/templates/admin_panel/election_results.html`
- Modify: `admin_panel/tests.py`

- [ ] **Step 1: Write the failing test**

Add to `admin_panel/tests.py`:

```python
class ElectionResultsViewTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username="admin10", password="pass12345")
        self.admin_profile = AdminProfile.objects.create(user=self.admin_user, is_admin=True)
        self.client.force_login(self.admin_user)
        self.position = Position.objects.create(title="President", modified_by=self.admin_profile)
        self.election = Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            modified_by=self.admin_profile,
        )
        Contestant.objects.create(
            name="Jane Doe",
            manifesto="Vote for progress.",
            position=self.position,
            election=self.election,
        )

    def test_results_view_shows_contestants_by_position(self):
        response = self.client.get(reverse("admin_panel:election_results", args=[self.election.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin_panel/election_results.html")
        self.assertContains(response, "Jane Doe")
        self.assertContains(response, "President")
```

- [ ] **Step 2: Run it and confirm it fails**

```bash
.venv/bin/python manage.py test admin_panel
```

Expected: `NoReverseMatch` — `admin_panel:election_results` doesn't exist yet.

- [ ] **Step 3: Implement the view**

Add `DetailView` to the `django.views.generic` import line in `admin_panel/views.py`:

```python
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView
```

Add to the end of `admin_panel/views.py`:

```python
class ElectionResultsView(AdminRequiredMixin, DetailView):
    model = Election
    template_name = "admin_panel/election_results.html"
    context_object_name = "election"
```

- [ ] **Step 4: Wire the URL**

In `admin_panel/urls.py`, add after the `election_update` line:

```python
    path("elections/<int:pk>/results/", views.ElectionResultsView.as_view(), name="election_results"),
```

- [ ] **Step 5: Write the template**

Create `admin_panel/templates/admin_panel/election_results.html`:

```html
{% extends "admin_panel/base.html" %}

{% block title %}{{ election.session }} Results · NAIFT Admin{% endblock %}

{% block content %}
<h1 class="font-display text-3xl text-brand-purple mb-2">{{ election.session }} Results</h1>
<p class="text-brand-black/70 mb-8">Status: {{ election.get_status_display }}. Vote tallies will appear here once the voting system is live — this view currently lists the ballot composition for each position so admins can verify data entry before voting opens.</p>

{% regroup election.contestants.all by position as position_list %}
{% for position in position_list %}
    <h2 class="font-display text-2xl text-brand-black mb-3">{{ position.grouper }}</h2>
    <ul class="list-disc list-inside mb-8">
        {% for contestant in position.list %}
            <li>{{ contestant.name }}{% if contestant.alias %} ({{ contestant.alias }}){% endif %}</li>
        {% endfor %}
    </ul>
{% empty %}
    <p>No contestants have been added for this election yet.</p>
{% endfor %}
{% endblock %}
```

- [ ] **Step 6: Run the tests and confirm they pass**

```bash
.venv/bin/python manage.py test admin_panel
```

Expected: `OK` (19 tests).

- [ ] **Step 7: Commit**

```bash
git add admin_panel
git commit -m "Add Election results view (ballot composition, no vote tallies yet)"
```

---

### Task 11: Election marquee on the public homepage

**Files:**
- Modify: `core/views.py`
- Modify: `core/templates/core/home.html`
- Modify: `core/tests.py`

- [ ] **Step 1: Write the failing tests**

Add to `core/tests.py`:

```python
from django.contrib.auth.models import User

from admin_panel.models import AdminProfile
from elections.models import Election


class HomeMarqueeTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="admin_marquee", password="pass12345")
        self.admin_profile = AdminProfile.objects.create(user=user, is_admin=True)

    def test_no_election_shows_no_marquee(self):
        response = self.client.get(reverse("core:home"))
        self.assertNotContains(response, "Voting Ongoing")
        self.assertNotContains(response, "Election starts")

    def test_upcoming_election_shows_announcement(self):
        Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            status="upcoming",
            modified_by=self.admin_profile,
        )
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, "Election starts")
        self.assertContains(response, "2026/2027")

    def test_ongoing_election_shows_voting_banner(self):
        Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            status="ongoing",
            modified_by=self.admin_profile,
        )
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, "Voting Ongoing")

    def test_ended_election_shows_no_marquee(self):
        Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            status="ended",
            modified_by=self.admin_profile,
        )
        response = self.client.get(reverse("core:home"))
        self.assertNotContains(response, "Voting Ongoing")
        self.assertNotContains(response, "Election starts")
```

- [ ] **Step 2: Run it and confirm it fails**

```bash
.venv/bin/python manage.py test core
```

Expected: `AttributeError` or the `assertContains`/`assertNotContains` checks failing — `HomeView` doesn't provide election context yet.

- [ ] **Step 3: Implement the view context**

Replace the contents of `core/views.py` with:

```python
from django.views.generic import TemplateView

from elections.models import Election


class HomeView(TemplateView):
    template_name = "core/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["latest_election"] = (
            Election.objects.exclude(status=Election.STATUS_ENDED).order_by("-id").first()
        )
        return context


class AboutView(TemplateView):
    template_name = "core/about.html"


class AcademicsView(TemplateView):
    template_name = "core/academics.html"
```

- [ ] **Step 4: Add the marquee to the template**

In `core/templates/core/home.html`, add the marquee block right after the opening `{% block content %}` line and before the existing hero `<section>`:

```html
{% block content %}
{% if latest_election %}
    <div class="bg-brand-black text-brand-white px-6 py-3 text-center" data-aos="fade-down">
        {% if latest_election.status == "ongoing" %}
            <p>Voting Ongoing for {{ latest_election.session }} &mdash; closes {{ latest_election.close_time }}. <a href="#" class="underline hover:text-brand-purple">Vote now</a></p>
        {% else %}
            <p>Election starts {{ latest_election.start_time }} for {{ latest_election.session }} &mdash; closes {{ latest_election.close_time }}.</p>
        {% endif %}
    </div>
{% endif %}

<section class="relative overflow-hidden text-brand-white text-center" data-aos="zoom-in">
```

The rest of `home.html` (the hero section, the gradient overlay div, the Welcome section) stays exactly as it already is — only the marquee block above is new, inserted immediately after `{% block content %}`.

- [ ] **Step 5: Run the tests and confirm they pass**

```bash
.venv/bin/python manage.py test core
```

Expected: `OK` (7 tests — the original 3 `core` tests from sub-project 1 plus these 4 new marquee tests).

- [ ] **Step 6: Commit**

```bash
git add core
git commit -m "Add election status marquee to the public homepage"
```

---

### Task 12: Final verification

**Files:** none (verification only)

- [ ] **Step 1: Run the entire test suite**

```bash
.venv/bin/python manage.py test
```

Expected: `OK` (35 tests total — 7 in `core`, 3 in `executives`, 6 in `elections`, 19 in `admin_panel`).

- [ ] **Step 2: Run Django's system check**

```bash
.venv/bin/python manage.py check
```

Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 3: Verify migrations are all applied**

```bash
.venv/bin/python manage.py showmigrations admin_panel elections
```

Expected: every migration listed has `[X]` next to it (none pending).

- [ ] **Step 4: Manual smoke test**

This step has no automated test — confirming the dashboard actually works end-to-end in a browser, per the project's standard of visually checking UI changes before calling them done.

1. Ensure a superuser exists (`python manage.py createsuperuser` if you don't already have one from sub-project 1).
2. Start Postgres if it isn't running: `docker compose up -d db`.
3. Start the Tailwind watcher: `.venv/bin/python manage.py tailwind start` (or run `.venv/bin/python manage.py tailwind build` once if you just want a static rebuild).
4. Start the dev server: `.venv/bin/python manage.py runserver`.
5. In Django's built-in `/admin/` (log in as the superuser), open **Admin profiles → Add admin profile**, pick your superuser's `User`, check "Is admin", save.
6. Visit `http://127.0.0.1:8000/dashboard/login/`, log in with that same superuser's username/password — confirm you land on the dashboard and see the 4 stat cards.
7. Add a Position, then a Contestant under that Position (for a new Election you create first), then edit the Election's status from "upcoming" to "ongoing" and back.
8. Visit `http://127.0.0.1:8000/` and confirm the marquee appears/disappears correctly as you change the Election's status between upcoming/ongoing/ended in the dashboard.
9. Confirm a non-admin user (create one via `python manage.py shell` with `User.objects.create_user(...)`, no `AdminProfile`) gets redirected to the login page with the "You are not authorized" message when visiting `/dashboard/`.

- [ ] **Step 5: Stop services**

```bash
lsof -ti:8000 -sTCP:LISTEN | xargs -r kill
```

(Leave Postgres running via `docker compose` — it's shared infrastructure for future work, not something to tear down after each session.)

---

## Self-Review Notes

- **Spec coverage:** every section of `2026-10-30-admin-panel-design.md` maps to a task — two-tier admin model (Tasks 1, 5), `elections` app models (Tasks 2-4), `admin_panel` app + audit enforcement (Tasks 1, 2, 3, 6, 9), all 4 CRUD sections (Tasks 6-9), Election results view (Task 10), homepage marquee (Task 11), and the spec's full testing checklist (AdminProfile/auth rejection → Task 5; IntegrityError on missing `modified_by` → Tasks 2 & 3; CRUD round-trips → Tasks 6-9; marquee states → Task 11).
- **Type/name consistency:** `Election.STATUS_UPCOMING/STATUS_ONGOING/STATUS_ENDED` constants (Task 3) are reused as-is in `HomeView.get_context_data` (Task 11, `Election.STATUS_ENDED`) and the test string literals `"upcoming"`/`"ongoing"`/`"ended"` match the choices tuples exactly. `AdminRequiredMixin` (Task 5) is applied consistently to every dashboard CBV in Tasks 6-10. URL names (`admin_panel:position_list`, `election_results`, etc.) are consistent between `urls.py`, every view's `success_url`, and every template's `{% url %}` reference — cross-checked each one while writing.
- **Known forward-reference handled explicitly, not silently left as a gap:** the Election results view (Task 10) shows ballot composition rather than real vote tallies, because the `Vote` model doesn't exist until sub-project 3 — this is called out directly in both the view's own template copy and this plan, not left implicit.
- **No placeholders:** every step has complete, runnable code; the one spot that could look like a placeholder (Task 9 Step 7's note about `election_results` not existing yet) is an explicit, deliberate sequencing note about *why* a test still passes mid-plan, not a TBD.
