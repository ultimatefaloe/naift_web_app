# Voting Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the final sub-project described in `docs/superpowers/specs/2026-10-30-voting-dashboard-design.md`: student login, the vote wizard, "you have voted"/"no active election" states, and public results pages (current + past-elections archive).

**Architecture:** A new `voting` app with two models (`Student`, `Vote`) and session-based, password-less authentication (first name + matric number). The vote wizard holds in-progress picks in the session only — nothing touches the database until a final atomic submit. Results pages are public and read-only. This is the last sub-project; no further specs follow it.

**Tech Stack:** Same stack as sub-projects 1–2 (Django 6.1, Postgres, Cloudinary, Tailwind) — no new third-party packages needed.

---

### Task 1: `voting` app — `Student` model

**Files:**
- Create: `voting/__init__.py`, `voting/apps.py`
- Create: `voting/models.py`
- Create: `voting/admin.py`
- Create: `voting/tests.py`
- Create: `voting/migrations/0001_initial.py` (generated)
- Modify: `web/settings.py`

- [ ] **Step 1: Write the failing tests**

```bash
.venv/bin/python manage.py startapp voting
```

Replace the contents of `voting/tests.py` with:

```python
from django.core.exceptions import ValidationError
from django.test import TestCase

from .models import Student


class StudentModelTests(TestCase):
    def test_string_representation(self):
        student = Student.objects.create(
            first_name="Jane", last_name="Doe", matric_number="2022/1/90976CF", level="300"
        )
        self.assertEqual(str(student), "Jane Doe (2022/1/90976CF)")

    def test_valid_matric_number_passes_validation(self):
        student = Student(
            first_name="Jane", last_name="Doe", matric_number="2022/1/90976CF", level="300"
        )
        student.full_clean()

    def test_invalid_matric_number_raises_validation_error(self):
        student = Student(
            first_name="Jane", last_name="Doe", matric_number="not-a-matric-number", level="300"
        )
        with self.assertRaises(ValidationError):
            student.full_clean()
```

- [ ] **Step 2: Run it and confirm it fails**

Add `'voting',` to `INSTALLED_APPS` in `web/settings.py` (after `'elections',`):

```python
    'admin_panel',
    'elections',
    'voting',
```

```bash
.venv/bin/python manage.py test voting
```

Expected: `ImportError` or `AttributeError` — `Student` doesn't exist in `voting/models.py` yet.

- [ ] **Step 3: Implement the model**

Replace the contents of `voting/models.py` with:

```python
from django.core.validators import RegexValidator
from django.db import models

matric_number_validator = RegexValidator(
    regex=r"^\d{4}/\d+/\d+CF$",
    message="Matric number must be in the format YYYY/N/NNNNNCF (e.g. 2022/1/90976CF).",
)


class Student(models.Model):
    LEVEL_CHOICES = [
        ("100", "100 Level"),
        ("200", "200 Level"),
        ("300", "300 Level"),
        ("400", "400 Level"),
        ("500", "500 Level"),
    ]

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    matric_number = models.CharField(max_length=30, unique=True, validators=[matric_number_validator])
    level = models.CharField(max_length=3, choices=LEVEL_CHOICES)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.matric_number})"
```

`matric_number` is `unique=True` — not explicitly stated in the spec's field list, but required for login to unambiguously resolve one student. The regex validator only runs on `full_clean()`/form validation (standard Django behavior), not on a raw `.objects.create()` — same pattern already used throughout this project.

- [ ] **Step 4: Generate and apply the migration**

```bash
.venv/bin/python manage.py makemigrations voting
.venv/bin/python manage.py migrate voting
```

Expected: `Migrations for 'voting': ... 0001_initial.py` then `Applying voting.0001_initial... OK`.

- [ ] **Step 5: Run the tests and confirm they pass**

```bash
.venv/bin/python manage.py test voting
```

Expected: `OK` (3 tests).

- [ ] **Step 6: Register with Django's built-in admin**

Per the spec, students are "pre-seeded by admin" — Django's built-in `/admin/` is one of the two seeding paths (the other, CSV import, is Task 9). Replace the contents of `voting/admin.py` with:

```python
from django.contrib import admin

from .models import Student


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "matric_number", "level")
    list_filter = ("level",)
    search_fields = ("first_name", "last_name", "matric_number")
```

- [ ] **Step 7: Commit**

```bash
git add voting web/settings.py
git commit -m "Add Student model with matric number validation"
```

---

### Task 2: `voting` app — `Vote` model

**Files:**
- Modify: `voting/models.py`
- Modify: `voting/tests.py`

- [ ] **Step 1: Write the failing tests**

Add to `voting/tests.py`:

```python
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction

from admin_panel.models import AdminProfile
from elections.models import Contestant, Election, Position

from .models import Vote


class VoteModelTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="admin_voting1", password="pass12345")
        admin_profile = AdminProfile.objects.create(user=user, is_admin=True)
        self.position = Position.objects.create(title="President", modified_by=admin_profile)
        self.election = Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            status="ongoing",
            modified_by=admin_profile,
        )
        self.contestant = Contestant.objects.create(
            name="Jane Doe", manifesto="Vote for progress.", position=self.position, election=self.election
        )
        self.student = Student.objects.create(
            first_name="John", last_name="Smith", matric_number="2022/1/90976CF", level="300"
        )

    def test_string_representation(self):
        vote = Vote.objects.create(
            student=self.student, election=self.election, position=self.position, contestant=self.contestant
        )
        self.assertEqual(str(vote), f"{self.student} -> {self.contestant} ({self.position})")

    def test_duplicate_vote_for_same_position_raises_integrity_error(self):
        Vote.objects.create(
            student=self.student, election=self.election, position=self.position, contestant=self.contestant
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Vote.objects.create(
                    student=self.student,
                    election=self.election,
                    position=self.position,
                    contestant=self.contestant,
                )
```

- [ ] **Step 2: Run it and confirm it fails**

```bash
.venv/bin/python manage.py test voting
```

Expected: `ImportError` or `AttributeError` — `Vote` doesn't exist yet.

- [ ] **Step 3: Implement the model**

Add to `voting/models.py`, after the `Student` class:

```python
class Vote(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="votes")
    election = models.ForeignKey("elections.Election", on_delete=models.CASCADE, related_name="votes")
    position = models.ForeignKey("elections.Position", on_delete=models.CASCADE, related_name="votes")
    contestant = models.ForeignKey("elections.Contestant", on_delete=models.CASCADE, related_name="votes")
    voted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("student", "election", "position")

    def __str__(self):
        return f"{self.student} -> {self.contestant} ({self.position})"
```

`unique_together` is the DB-level mechanism (a composite unique index) that makes a second vote for the same student+election+position impossible, regardless of any application-level check — the same "DB constraint is the real guarantee" pattern used for `Position`/`Election`'s `modified_by` in sub-project 2.

- [ ] **Step 4: Generate and apply the migration**

```bash
.venv/bin/python manage.py makemigrations voting
.venv/bin/python manage.py migrate voting
```

Expected: `Migrations for 'voting': ... 0002_vote.py` then `Applying voting.0002_vote... OK`.

- [ ] **Step 5: Run the tests and confirm they pass**

```bash
.venv/bin/python manage.py test voting
```

Expected: `OK` (5 tests).

- [ ] **Step 6: Commit**

```bash
git add voting
git commit -m "Add Vote model with DB-level one-vote-per-position enforcement"
```

---

### Task 3: `voting` — base layout, login/logout

**Files:**
- Create: `voting/templates/voting/base.html`
- Create: `voting/templates/voting/login.html`
- Create: `voting/views.py` (currently has unmodified `startapp` boilerplate — you're replacing its contents)
- Create: `voting/urls.py`
- Modify: `voting/tests.py`
- Modify: `web/urls.py`

- [ ] **Step 1: Write the failing tests**

Add to `voting/tests.py`:

```python
from django.urls import reverse


class LoginViewTests(TestCase):
    def setUp(self):
        self.student = Student.objects.create(
            first_name="Jane", last_name="Doe", matric_number="2022/1/90976CF", level="300"
        )

    def test_valid_credentials_log_student_in(self):
        response = self.client.post(
            reverse("voting:login"),
            {"first_name": "Jane", "matric_number": "2022/1/90976CF"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session["student_id"], self.student.id)

    def test_invalid_credentials_show_error(self):
        response = self.client.post(
            reverse("voting:login"),
            {"first_name": "Jane", "matric_number": "0000/0/00000CF"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No matching student record found.")


class LogoutViewTests(TestCase):
    def setUp(self):
        self.student = Student.objects.create(
            first_name="Jane", last_name="Doe", matric_number="2022/1/90976CF", level="300"
        )

    def test_logout_clears_session(self):
        session = self.client.session
        session["student_id"] = self.student.id
        session.save()
        response = self.client.post(reverse("voting:logout"))
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("student_id", self.client.session)
```

- [ ] **Step 2: Run it and confirm it fails**

```bash
.venv/bin/python manage.py test voting
```

Expected: `NoReverseMatch` — `voting:login`/`voting:logout` don't exist yet.

- [ ] **Step 3: Implement the views**

Replace the contents of `voting/views.py` with:

```python
from django.shortcuts import redirect, render

from .models import Student


def login_view(request):
    if request.method == "POST":
        first_name = request.POST.get("first_name", "").strip()
        matric_number = request.POST.get("matric_number", "").strip()
        student = Student.objects.filter(
            first_name__iexact=first_name, matric_number=matric_number
        ).first()
        if student is not None:
            request.session["student_id"] = student.id
            return redirect("voting:vote_entry")
        return render(request, "voting/login.html", {"error": "No matching student record found."})
    return render(request, "voting/login.html")


def logout_view(request):
    request.session.pop("student_id", None)
    return redirect("voting:login")
```

First name is matched case-insensitively (`first_name__iexact`) for a more forgiving login experience; `matric_number` (the real unique identifier) is matched exactly.

- [ ] **Step 4: Wire the URLs**

Create `voting/urls.py`. `vote_entry` is a placeholder pointing at `login_view` for now (the only view that exists yet) — Task 4 replaces this line with the real view:

```python
from django.urls import path

from . import views

app_name = "voting"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("", views.login_view, name="vote_entry"),
]
```

In `web/urls.py`, change:

```python
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('executives/', include('executives.urls')),
    path('dashboard/', include('admin_panel.urls')),
]
```

to:

```python
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('executives/', include('executives.urls')),
    path('dashboard/', include('admin_panel.urls')),
    path('vote/', include('voting.urls')),
]
```

- [ ] **Step 5: Write the templates**

Create `voting/templates/voting/base.html`. Per CLAUDE.md, the voting dashboard uses `ift_logo.jpeg` + `naifts_logo.jpeg` (not `fut.jpeg`, which is the public site's pairing):

```html
{% load static tailwind_tags %}
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Vote · NAIFT{% endblock %}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300..900;1,9..144,300..900&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    {% tailwind_css %}
</head>
<body class="bg-brand-white text-brand-black font-body">
    <header class="flex items-center justify-between px-6 py-4 border-b border-brand-black/10">
        <div class="flex items-center gap-3">
            <img src="{% static 'image/ift_logo.jpeg' %}" alt="Department of Information Technology logo" class="h-12 w-12 rounded-full object-cover">
            <img src="{% static 'image/naifts_logo.jpeg' %}" alt="NAIFT logo" class="h-12 w-12 rounded-full object-cover">
            <span class="font-display text-xl text-brand-purple">NAIFT Voting</span>
        </div>
        {% if request.session.student_id %}
        <form method="post" action="{% url 'voting:logout' %}">
            {% csrf_token %}
            <button type="submit" class="hover:text-brand-purple">Logout</button>
        </form>
        {% endif %}
    </header>

    <main class="px-6 py-10 max-w-3xl mx-auto">
        {% block content %}{% endblock %}
    </main>
</body>
</html>
```

Create `voting/templates/voting/login.html`:

```html
{% extends "voting/base.html" %}

{% block title %}Student Login · NAIFT Voting{% endblock %}

{% block content %}
<div class="max-w-sm mx-auto mt-16">
    <h1 class="font-display text-3xl text-brand-purple mb-6 text-center">Student Login</h1>
    {% if error %}
        <p class="mb-4 px-4 py-3 rounded bg-brand-purple/10 text-brand-purple">{{ error }}</p>
    {% endif %}
    <form method="post" class="flex flex-col gap-4">
        {% csrf_token %}
        <input type="text" name="first_name" placeholder="First Name" required class="border border-brand-black/20 rounded px-4 py-2">
        <input type="text" name="matric_number" placeholder="Matric Number (e.g. 2022/1/90976CF)" required class="border border-brand-black/20 rounded px-4 py-2">
        <button type="submit" class="bg-brand-purple text-brand-white px-4 py-2 rounded hover:opacity-90">Log in</button>
    </form>
</div>
{% endblock %}
```

- [ ] **Step 6: Run the tests and confirm they pass**

```bash
.venv/bin/python manage.py test voting
```

Expected: `OK` (8 tests).

- [ ] **Step 7: Commit**

```bash
git add voting web/urls.py
git commit -m "Add student login/logout and voting dashboard base layout"
```

---

### Task 4: Vote entry point (eligibility gate)

**Files:**
- Modify: `voting/views.py`
- Modify: `voting/urls.py`
- Create: `voting/templates/voting/no_election.html`
- Create: `voting/templates/voting/voted.html`
- Modify: `voting/tests.py`

- [ ] **Step 1: Write the failing tests**

Add to `voting/tests.py`:

```python
class VoteEntryAccessTests(TestCase):
    def test_unauthenticated_redirected_to_login(self):
        response = self.client.get(reverse("voting:vote_entry"))
        self.assertRedirects(response, reverse("voting:login"))


class VoteEntryTests(TestCase):
    def setUp(self):
        self.student = Student.objects.create(
            first_name="Jane", last_name="Doe", matric_number="2022/1/90976CF", level="300"
        )
        session = self.client.session
        session["student_id"] = self.student.id
        session.save()
        user = User.objects.create_user(username="admin_voting2", password="pass12345")
        self.admin_profile = AdminProfile.objects.create(user=user, is_admin=True)

    def test_no_ongoing_election_shows_no_election_page(self):
        response = self.client.get(reverse("voting:vote_entry"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "voting/no_election.html")

    def test_already_voted_shows_voted_page(self):
        position = Position.objects.create(title="President", modified_by=self.admin_profile)
        election = Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            status="ongoing",
            modified_by=self.admin_profile,
        )
        contestant = Contestant.objects.create(
            name="Jane Doe", manifesto="Vote for progress.", position=position, election=election
        )
        Vote.objects.create(student=self.student, election=election, position=position, contestant=contestant)
        response = self.client.get(reverse("voting:vote_entry"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "voting/voted.html")

    def test_eligible_student_redirected_to_first_wizard_step(self):
        position = Position.objects.create(title="President", modified_by=self.admin_profile)
        election = Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            status="ongoing",
            modified_by=self.admin_profile,
        )
        Contestant.objects.create(
            name="Jane Doe", manifesto="Vote for progress.", position=position, election=election
        )
        response = self.client.get(reverse("voting:vote_entry"))
        self.assertRedirects(response, reverse("voting:wizard_step", args=[position.pk]))
```

- [ ] **Step 2: Run it and confirm it fails**

```bash
.venv/bin/python manage.py test voting
```

Expected: `NoReverseMatch` — `voting:wizard_step` doesn't exist yet, and `vote_entry` still points at the `login_view` placeholder (always renders the login form, not the eligibility-gated behavior these tests expect).

- [ ] **Step 3: Implement the view**

Replace the contents of `voting/views.py` with:

```python
from functools import wraps

from django.shortcuts import get_object_or_404, redirect, render

from elections.models import Contestant, Election, Position

from .models import Student, Vote


def login_view(request):
    if request.method == "POST":
        first_name = request.POST.get("first_name", "").strip()
        matric_number = request.POST.get("matric_number", "").strip()
        student = Student.objects.filter(
            first_name__iexact=first_name, matric_number=matric_number
        ).first()
        if student is not None:
            request.session["student_id"] = student.id
            return redirect("voting:vote_entry")
        return render(request, "voting/login.html", {"error": "No matching student record found."})
    return render(request, "voting/login.html")


def logout_view(request):
    request.session.pop("student_id", None)
    return redirect("voting:login")


def student_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        student_id = request.session.get("student_id")
        if not student_id or not Student.objects.filter(pk=student_id).exists():
            return redirect("voting:login")
        return view_func(request, *args, **kwargs)
    return wrapper


def get_ongoing_election():
    return Election.objects.filter(status=Election.STATUS_ONGOING).order_by("-id").first()


@student_required
def vote_entry(request):
    election = get_ongoing_election()
    if election is None:
        return render(request, "voting/no_election.html")
    student = Student.objects.get(pk=request.session["student_id"])
    if Vote.objects.filter(student=student, election=election).exists():
        return render(request, "voting/voted.html")
    positions = Position.objects.filter(contestants__election=election).distinct().order_by("title")
    if not positions.exists():
        return render(request, "voting/no_election.html")
    picks = request.session.get("vote_picks", {})
    for position in positions:
        if str(position.id) not in picks:
            return redirect("voting:wizard_step", position_id=position.id)
    return redirect("voting:wizard_review")
```

- [ ] **Step 4: Wire the URLs**

Replace the contents of `voting/urls.py`. `wizard_step`/`wizard_review` are placeholders for now (Tasks 5 and 6 replace them one at a time with real views):

```python
from django.urls import path
from django.views.generic import TemplateView

from . import views

app_name = "voting"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("", views.vote_entry, name="vote_entry"),
    path(
        "position/<int:position_id>/",
        TemplateView.as_view(template_name="voting/login.html"),
        name="wizard_step",
    ),
    path(
        "review/",
        TemplateView.as_view(template_name="voting/login.html"),
        name="wizard_review",
    ),
]
```

- [ ] **Step 5: Write the templates**

Create `voting/templates/voting/no_election.html`:

```html
{% extends "voting/base.html" %}

{% block title %}No Active Election · NAIFT Voting{% endblock %}

{% block content %}
<div class="text-center mt-16">
    <h1 class="font-display text-3xl text-brand-purple mb-4">No Active Election</h1>
    <p class="text-lg">There is no election open for voting right now. Please check back later.</p>
</div>
{% endblock %}
```

Create `voting/templates/voting/voted.html`:

```html
{% extends "voting/base.html" %}

{% block title %}You Have Voted · NAIFT Voting{% endblock %}

{% block content %}
<div class="text-center mt-16">
    <h1 class="font-display text-3xl text-brand-purple mb-4">You Have Voted</h1>
    <p class="text-lg">Thank you for voting. You have already submitted your vote for this election.</p>
</div>
{% endblock %}
```

- [ ] **Step 6: Run the tests and confirm they pass**

```bash
.venv/bin/python manage.py test voting
```

Expected: `OK` (12 tests).

- [ ] **Step 7: Commit**

```bash
git add voting
git commit -m "Add vote entry point with eligibility gate (no election / already voted)"
```

---

### Task 5: Vote wizard step

**Files:**
- Modify: `voting/views.py`
- Modify: `voting/urls.py`
- Create: `voting/templates/voting/wizard_step.html`
- Modify: `voting/tests.py`

- [ ] **Step 1: Write the failing tests**

Add to `voting/tests.py`:

```python
class WizardStepTests(TestCase):
    def setUp(self):
        self.student = Student.objects.create(
            first_name="Jane", last_name="Doe", matric_number="2022/1/90976CF", level="300"
        )
        session = self.client.session
        session["student_id"] = self.student.id
        session.save()
        user = User.objects.create_user(username="admin_voting3", password="pass12345")
        admin_profile = AdminProfile.objects.create(user=user, is_admin=True)
        self.position = Position.objects.create(title="President", modified_by=admin_profile)
        self.election = Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            status="ongoing",
            modified_by=admin_profile,
        )
        self.contestant = Contestant.objects.create(
            name="Jane Doe", manifesto="Vote for progress.", position=self.position, election=self.election
        )

    def test_get_shows_contestants(self):
        response = self.client.get(reverse("voting:wizard_step", args=[self.position.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "voting/wizard_step.html")
        self.assertContains(response, "Jane Doe")

    def test_post_stores_pick_in_session_not_database(self):
        response = self.client.post(
            reverse("voting:wizard_step", args=[self.position.pk]), {"contestant": self.contestant.pk}
        )
        self.assertRedirects(response, reverse("voting:vote_entry"))
        self.assertEqual(self.client.session["vote_picks"], {str(self.position.pk): self.contestant.pk})
        self.assertEqual(Vote.objects.count(), 0)
```

- [ ] **Step 2: Run it and confirm it fails**

```bash
.venv/bin/python manage.py test voting
```

Expected: the `test_get_shows_contestants` test fails because `wizard_step` still resolves to the `login.html` placeholder (wrong template, no contestant content).

- [ ] **Step 3: Implement the view**

Add to the end of `voting/views.py`:

```python
@student_required
def wizard_step(request, position_id):
    election = get_ongoing_election()
    if election is None:
        return redirect("voting:vote_entry")
    student = Student.objects.get(pk=request.session["student_id"])
    if Vote.objects.filter(student=student, election=election).exists():
        return redirect("voting:vote_entry")
    position = get_object_or_404(Position, pk=position_id)
    contestants = position.contestants.filter(election=election)
    if request.method == "POST":
        contestant_id = request.POST.get("contestant")
        contestant = get_object_or_404(Contestant, pk=contestant_id, position=position, election=election)
        picks = request.session.get("vote_picks", {})
        picks[str(position.id)] = contestant.id
        request.session["vote_picks"] = picks
        return redirect("voting:vote_entry")
    return render(request, "voting/wizard_step.html", {"position": position, "contestants": contestants})
```

- [ ] **Step 4: Wire the URL**

In `voting/urls.py`, replace:

```python
    path(
        "position/<int:position_id>/",
        TemplateView.as_view(template_name="voting/login.html"),
        name="wizard_step",
    ),
```

with:

```python
    path("position/<int:position_id>/", views.wizard_step, name="wizard_step"),
```

(The `TemplateView` import stays in the file — it's still used by the `wizard_review` placeholder until Task 6.)

- [ ] **Step 5: Write the template**

Create `voting/templates/voting/wizard_step.html`:

```html
{% extends "voting/base.html" %}

{% block title %}{{ position.title }} · NAIFT Voting{% endblock %}

{% block content %}
<h1 class="font-display text-3xl text-brand-purple mb-8">{{ position.title }}</h1>

<form method="post" class="flex flex-col gap-4">
    {% csrf_token %}
    {% for contestant in contestants %}
        <label class="flex items-center gap-4 border border-brand-purple/20 rounded-lg p-4 cursor-pointer">
            <input type="radio" name="contestant" value="{{ contestant.pk }}" required>
            {% if contestant.photo %}
                <img src="{{ contestant.photo.url }}" alt="{{ contestant.name }}" class="h-16 w-16 rounded-full object-cover">
            {% endif %}
            <span>
                <span class="font-display text-lg">{{ contestant.name }}{% if contestant.alias %} ({{ contestant.alias }}){% endif %}</span>
                <span class="block text-sm text-brand-black/70">{{ contestant.manifesto }}</span>
            </span>
        </label>
    {% endfor %}
    <button type="submit" class="bg-brand-purple text-brand-white px-4 py-2 rounded hover:opacity-90">Next</button>
</form>
{% endblock %}
```

- [ ] **Step 6: Run the tests and confirm they pass**

```bash
.venv/bin/python manage.py test voting
```

Expected: `OK` (14 tests).

- [ ] **Step 7: Commit**

```bash
git add voting
git commit -m "Add vote wizard step (position-by-position contestant picks)"
```

---

### Task 6: Vote review/submit

**Files:**
- Modify: `voting/views.py`
- Modify: `voting/urls.py`
- Create: `voting/templates/voting/wizard_review.html`
- Modify: `voting/tests.py`

- [ ] **Step 1: Write the failing tests**

Add to `voting/tests.py`:

```python
class WizardReviewTests(TestCase):
    def setUp(self):
        self.student = Student.objects.create(
            first_name="Jane", last_name="Doe", matric_number="2022/1/90976CF", level="300"
        )
        session = self.client.session
        session["student_id"] = self.student.id
        session.save()
        user = User.objects.create_user(username="admin_voting4", password="pass12345")
        admin_profile = AdminProfile.objects.create(user=user, is_admin=True)
        self.position = Position.objects.create(title="President", modified_by=admin_profile)
        self.election = Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            status="ongoing",
            modified_by=admin_profile,
        )
        self.contestant = Contestant.objects.create(
            name="Jane Doe", manifesto="Vote for progress.", position=self.position, election=self.election
        )
        session = self.client.session
        session["vote_picks"] = {str(self.position.pk): self.contestant.pk}
        session.save()

    def test_get_shows_selections(self):
        response = self.client.get(reverse("voting:wizard_review"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Jane Doe")

    def test_post_submits_votes_atomically_and_clears_session(self):
        response = self.client.post(reverse("voting:wizard_review"))
        self.assertRedirects(response, reverse("voting:vote_entry"))
        self.assertEqual(Vote.objects.count(), 1)
        vote = Vote.objects.get()
        self.assertEqual(vote.student, self.student)
        self.assertEqual(vote.contestant, self.contestant)
        self.assertNotIn("vote_picks", self.client.session)

    def test_post_then_vote_entry_shows_voted_page(self):
        self.client.post(reverse("voting:wizard_review"))
        response = self.client.get(reverse("voting:vote_entry"))
        self.assertTemplateUsed(response, "voting/voted.html")
```

- [ ] **Step 2: Run it and confirm it fails**

```bash
.venv/bin/python manage.py test voting
```

Expected: `test_get_shows_selections` fails because `wizard_review` still resolves to the `login.html` placeholder.

- [ ] **Step 3: Implement the view**

Change the imports at the top of `voting/views.py` — add `transaction` to the `django.db` import:

```python
from django.db import transaction
from functools import wraps

from django.shortcuts import get_object_or_404, redirect, render

from elections.models import Contestant, Election, Position

from .models import Student, Vote
```

Add to the end of `voting/views.py`:

```python
@student_required
def wizard_review(request):
    election = get_ongoing_election()
    if election is None:
        return redirect("voting:vote_entry")
    student = Student.objects.get(pk=request.session["student_id"])
    if Vote.objects.filter(student=student, election=election).exists():
        return redirect("voting:vote_entry")
    picks = request.session.get("vote_picks", {})
    selections = [get_object_or_404(Contestant, pk=contestant_id) for contestant_id in picks.values()]
    if request.method == "POST":
        with transaction.atomic():
            for contestant in selections:
                Vote.objects.create(
                    student=student,
                    election=election,
                    position=contestant.position,
                    contestant=contestant,
                )
        request.session.pop("vote_picks", None)
        return redirect("voting:vote_entry")
    return render(request, "voting/wizard_review.html", {"selections": selections})
```

- [ ] **Step 4: Wire the URL**

In `voting/urls.py`, replace:

```python
    path(
        "review/",
        TemplateView.as_view(template_name="voting/login.html"),
        name="wizard_review",
    ),
```

with:

```python
    path("review/", views.wizard_review, name="wizard_review"),
```

The `from django.views.generic import TemplateView` import at the top of `voting/urls.py` is no longer used anywhere in the file after this change — remove that import line.

- [ ] **Step 5: Write the template**

Create `voting/templates/voting/wizard_review.html`:

```html
{% extends "voting/base.html" %}

{% block title %}Review Your Vote · NAIFT Voting{% endblock %}

{% block content %}
<h1 class="font-display text-3xl text-brand-purple mb-8">Review Your Vote</h1>

<ul class="mb-8 space-y-3">
    {% for contestant in selections %}
        <li class="border border-brand-purple/20 rounded-lg p-4">
            <span class="font-display">{{ contestant.position.title }}:</span>
            {{ contestant.name }}{% if contestant.alias %} ({{ contestant.alias }}){% endif %}
        </li>
    {% endfor %}
</ul>

<form method="post">
    {% csrf_token %}
    <button type="submit" class="bg-brand-purple text-brand-white px-4 py-2 rounded hover:opacity-90">Submit My Vote</button>
</form>
{% endblock %}
```

- [ ] **Step 6: Run the tests and confirm they pass**

```bash
.venv/bin/python manage.py test voting
```

Expected: `OK` (17 tests).

- [ ] **Step 7: Commit**

```bash
git add voting
git commit -m "Add vote review/submit (atomic transaction writes all Vote rows)"
```

---

### Task 7: Results view (current published election)

**Files:**
- Modify: `voting/views.py`
- Modify: `voting/urls.py`
- Create: `voting/templates/voting/results.html`
- Create: `voting/templates/voting/results_not_published.html`
- Modify: `voting/tests.py`

- [ ] **Step 1: Write the failing tests**

Add to `voting/tests.py`:

```python
class ResultsViewTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="admin_voting5", password="pass12345")
        self.admin_profile = AdminProfile.objects.create(user=user, is_admin=True)
        self.position = Position.objects.create(title="President", modified_by=self.admin_profile)
        self.election = Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            status="ended",
            is_results_published=True,
            modified_by=self.admin_profile,
        )
        self.contestant = Contestant.objects.create(
            name="Jane Doe", manifesto="Vote for progress.", position=self.position, election=self.election
        )
        student = Student.objects.create(
            first_name="John", last_name="Smith", matric_number="2022/1/90976CF", level="300"
        )
        Vote.objects.create(
            student=student, election=self.election, position=self.position, contestant=self.contestant
        )

    def test_results_not_published_shows_fallback_page(self):
        self.election.is_results_published = False
        self.election.save()
        response = self.client.get(reverse("voting:results"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "voting/results_not_published.html")

    def test_results_shows_vote_tally(self):
        response = self.client.get(reverse("voting:results"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Jane Doe")
        self.assertContains(response, "1 vote")

    def test_results_no_login_required(self):
        response = self.client.get(reverse("voting:results"))
        self.assertEqual(response.status_code, 200)
```

- [ ] **Step 2: Run it and confirm it fails**

```bash
.venv/bin/python manage.py test voting
```

Expected: `NoReverseMatch` — `voting:results` doesn't exist yet.

- [ ] **Step 3: Implement the view**

Add `Count` to the `django.db.models` import and `get_object_or_404` is already imported — change the top of `voting/views.py`:

```python
from django.db import transaction
from django.db.models import Count
from functools import wraps

from django.shortcuts import get_object_or_404, redirect, render

from elections.models import Contestant, Election, Position

from .models import Student, Vote
```

Add to the end of `voting/views.py`:

```python
def results_view(request, pk=None):
    if pk:
        election = get_object_or_404(Election, pk=pk, is_results_published=True)
    else:
        election = Election.objects.filter(is_results_published=True).order_by("-id").first()
        if election is None:
            return render(request, "voting/results_not_published.html")
    tallies = (
        Contestant.objects.filter(election=election)
        .select_related("position")
        .annotate(vote_count=Count("votes"))
        .order_by("position__title", "-vote_count")
    )
    return render(request, "voting/results.html", {"election": election, "tallies": tallies})
```

No `@student_required` here — results are public, per the spec.

- [ ] **Step 4: Wire the URLs**

In `voting/urls.py`, add two new routes after the `review/` line:

```python
    path("results/", views.results_view, name="results"),
    path("results/<int:pk>/", views.results_view, name="results_detail"),
```

- [ ] **Step 5: Write the templates**

Create `voting/templates/voting/results.html`:

```html
{% extends "voting/base.html" %}

{% block title %}{{ election.session }} Results · NAIFT Voting{% endblock %}

{% block content %}
<h1 class="font-display text-3xl text-brand-purple mb-8">{{ election.session }} Results</h1>

{% regroup tallies by position as position_list %}
{% for position in position_list %}
    <h2 class="font-display text-2xl text-brand-black mb-3">{{ position.grouper }}</h2>
    <ul class="mb-8 space-y-2">
        {% for contestant in position.list %}
            <li class="flex justify-between border-b border-brand-black/10 py-2">
                <span>{{ contestant.name }}{% if contestant.alias %} ({{ contestant.alias }}){% endif %}</span>
                <span class="font-display text-brand-purple">{{ contestant.vote_count }} vote{{ contestant.vote_count|pluralize }}</span>
            </li>
        {% endfor %}
    </ul>
{% endfor %}
{% endblock %}
```

`tallies` is already ordered by `position__title` first, so `{% regroup %}` groups correctly without the extra-context-variable workaround needed in sub-project 2's Election results view (there, the base queryset had no ordering at all; here it's explicitly `order_by("position__title", "-vote_count")` from the start).

Create `voting/templates/voting/results_not_published.html`:

```html
{% extends "voting/base.html" %}

{% block title %}Results Not Published · NAIFT Voting{% endblock %}

{% block content %}
<div class="text-center mt-16">
    <h1 class="font-display text-3xl text-brand-purple mb-4">Results Not Yet Published</h1>
    <p class="text-lg">Check back once the election results have been published.</p>
</div>
{% endblock %}
```

- [ ] **Step 6: Run the tests and confirm they pass**

```bash
.venv/bin/python manage.py test voting
```

Expected: `OK` (20 tests).

- [ ] **Step 7: Commit**

```bash
git add voting
git commit -m "Add public results view for the current published election"
```

---

### Task 8: Results archive (past elections)

**Files:**
- Modify: `voting/views.py`
- Modify: `voting/urls.py`
- Create: `voting/templates/voting/results_archive.html`
- Modify: `voting/tests.py`

- [ ] **Step 1: Write the failing test**

Add to `voting/tests.py`:

```python
class ResultsArchiveTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="admin_voting6", password="pass12345")
        admin_profile = AdminProfile.objects.create(user=user, is_admin=True)
        self.published = Election.objects.create(
            session="2025/2026",
            start_time="2025-11-01T09:00:00Z",
            close_time="2025-11-01T17:00:00Z",
            status="ended",
            is_results_published=True,
            modified_by=admin_profile,
        )
        self.unpublished = Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            status="ended",
            is_results_published=False,
            modified_by=admin_profile,
        )

    def test_archive_lists_only_published_elections(self):
        response = self.client.get(reverse("voting:results_archive"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "2025/2026")
        self.assertNotContains(response, "2026/2027")
```

- [ ] **Step 2: Run it and confirm it fails**

```bash
.venv/bin/python manage.py test voting
```

Expected: `NoReverseMatch` — `voting:results_archive` doesn't exist yet.

- [ ] **Step 3: Implement the view**

Add to the end of `voting/views.py`:

```python
def results_archive(request):
    elections = Election.objects.filter(is_results_published=True).order_by("-id")
    return render(request, "voting/results_archive.html", {"elections": elections})
```

- [ ] **Step 4: Wire the URL**

In `voting/urls.py`, add after the `results/<int:pk>/` line:

```python
    path("results/archive/", views.results_archive, name="results_archive"),
```

- [ ] **Step 5: Write the template**

Create `voting/templates/voting/results_archive.html`:

```html
{% extends "voting/base.html" %}

{% block title %}Past Election Results · NAIFT Voting{% endblock %}

{% block content %}
<h1 class="font-display text-3xl text-brand-purple mb-8">Past Election Results</h1>

<ul class="space-y-3">
    {% for election in elections %}
        <li>
            <a href="{% url 'voting:results_detail' election.pk %}" class="text-brand-purple hover:underline font-display text-lg">{{ election.session }}</a>
        </li>
    {% empty %}
        <li>No published election results yet.</li>
    {% endfor %}
</ul>
{% endblock %}
```

- [ ] **Step 6: Run the tests and confirm they pass**

```bash
.venv/bin/python manage.py test voting
```

Expected: `OK` (21 tests).

- [ ] **Step 7: Commit**

```bash
git add voting
git commit -m "Add past-elections results archive page"
```

---

### Task 9: Student CSV seeding command

**Files:**
- Create: `voting/management/__init__.py`
- Create: `voting/management/commands/__init__.py`
- Create: `voting/management/commands/seed_students.py`
- Modify: `voting/tests.py`

- [ ] **Step 1: Write the failing tests**

Add to `voting/tests.py`:

```python
import os
import tempfile
from io import StringIO

from django.core.management import call_command, CommandError


class SeedStudentsCommandTests(TestCase):
    def test_imports_students_from_csv(self):
        csv_content = "first_name,last_name,matric_number,level\nJane,Doe,2022/1/90976CF,300\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            csv_path = f.name
        try:
            out = StringIO()
            call_command("seed_students", csv_path, stdout=out)
            self.assertTrue(Student.objects.filter(matric_number="2022/1/90976CF").exists())
            self.assertIn("Imported 1 new student", out.getvalue())
        finally:
            os.unlink(csv_path)

    def test_missing_csv_file_raises_command_error(self):
        with self.assertRaises(CommandError):
            call_command("seed_students", "/nonexistent/path.csv")
```

- [ ] **Step 2: Run it and confirm it fails**

```bash
.venv/bin/python manage.py test voting
```

Expected: `CommandError: Unknown command: 'seed_students'`.

- [ ] **Step 3: Create the management command package**

```bash
mkdir -p voting/management/commands
touch voting/management/__init__.py voting/management/commands/__init__.py
```

- [ ] **Step 4: Implement the command**

Create `voting/management/commands/seed_students.py`:

```python
import csv

from django.core.management.base import BaseCommand, CommandError

from voting.models import Student


class Command(BaseCommand):
    help = "Bulk-import students from a CSV file (columns: first_name,last_name,matric_number,level)"

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str)

    def handle(self, *args, **options):
        csv_path = options["csv_path"]
        created_count = 0
        try:
            with open(csv_path, newline="") as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    student, created = Student.objects.get_or_create(
                        matric_number=row["matric_number"],
                        defaults={
                            "first_name": row["first_name"],
                            "last_name": row["last_name"],
                            "level": row["level"],
                        },
                    )
                    if created:
                        created_count += 1
        except FileNotFoundError:
            raise CommandError(f"CSV file not found: {csv_path}")
        self.stdout.write(self.style.SUCCESS(f"Imported {created_count} new student(s)."))
```

- [ ] **Step 5: Run the tests and confirm they pass**

```bash
.venv/bin/python manage.py test voting
```

Expected: `OK` (23 tests).

- [ ] **Step 6: Commit**

```bash
git add voting
git commit -m "Add seed_students management command for CSV import"
```

---

### Task 10: Wire "Vote" nav links to the real voting login page

**Files:**
- Modify: `core/templates/core/base.html`
- Modify: `core/templates/core/home.html`
- Modify: `core/tests.py`

- [ ] **Step 1: Write the failing test**

Add to `core/tests.py`:

```python
class NavVoteLinkTests(TestCase):
    def test_home_vote_link_points_to_voting_login(self):
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, reverse("voting:login"))
```

- [ ] **Step 2: Run it and confirm it fails**

```bash
.venv/bin/python manage.py test core
```

Expected: fails — the nav's `Vote` link is currently a literal `href="#"`, so the rendered page doesn't contain `/vote/login/`.

- [ ] **Step 3: Update the nav link**

In `core/templates/core/base.html`, replace:

```html
            <a href="#" class="cta-bounce bg-brand-purple text-brand-white px-4 py-2 rounded-full hover:opacity-90">Vote</a>
```

with:

```html
            <a href="{% url 'voting:login' %}" class="cta-bounce bg-brand-purple text-brand-white px-4 py-2 rounded-full hover:opacity-90">Vote</a>
```

- [ ] **Step 4: Update the homepage marquee's "Vote now" link**

In `core/templates/core/home.html`, replace:

```html
            <p>Voting Ongoing for {{ latest_election.session }} &mdash; closes {{ latest_election.close_time }}. <a href="#" class="underline hover:text-brand-purple">Vote now</a></p>
```

with:

```html
            <p>Voting Ongoing for {{ latest_election.session }} &mdash; closes {{ latest_election.close_time }}. <a href="{% url 'voting:login' %}" class="underline hover:text-brand-purple">Vote now</a></p>
```

- [ ] **Step 5: Run the tests and confirm they pass**

```bash
.venv/bin/python manage.py test core
```

Expected: `OK` (8 tests — the 7 existing plus this new test).

- [ ] **Step 6: Commit**

```bash
git add core
git commit -m "Wire public-site Vote links to the real student login page"
```

---

### Task 11: Final verification

**Files:** none (verification only)

- [ ] **Step 1: Run the entire test suite**

```bash
.venv/bin/python manage.py test
```

Expected: `OK` (66 tests total — 8 in `core`, 3 in `executives`, 10 in `elections`, 22 in `admin_panel`, 23 in `voting`).

- [ ] **Step 2: Run Django's system check**

```bash
.venv/bin/python manage.py check
```

Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 3: Verify migrations are all applied**

```bash
.venv/bin/python manage.py showmigrations voting
```

Expected: both `0001_initial` and `0002_vote` show `[X]` (applied).

- [ ] **Step 4: Manual smoke test**

No automated test substitutes for actually using the voting flow in a browser — this step confirms the full student journey works end-to-end.

1. Ensure Postgres is running: `docker compose up -d db`.
2. Seed at least one `Student` via Django's built-in `/admin/` (Students → Add) or the `seed_students` command with a small CSV.
3. As an admin (via `/dashboard/`), create a `Position`, an `Election` with `status = ongoing`, and at least two `Contestant`s for that position/election.
4. Start the Tailwind watcher (`.venv/bin/python manage.py tailwind start`) and the dev server (`.venv/bin/python manage.py runserver`).
5. Visit `http://127.0.0.1:8000/` — confirm the `Vote` nav button and the marquee's `Vote now` link both go to `/vote/login/`.
6. Log in with the seeded student's first name + matric number.
7. Step through the wizard for each position, reach the review page, confirm the picks shown match what was selected, submit.
8. Revisit `/vote/` — confirm it now shows "You have voted" instead of the wizard.
9. As admin, flip the `Election`'s `status` to `ended` and `is_results_published` to `True`.
10. Visit `/vote/results/` — confirm the tally reflects the one vote cast. Visit `/vote/results/archive/` — confirm the election is listed and links to the same results page.
11. Try `/vote/` while logged out — confirm it redirects to `/vote/login/`.

- [ ] **Step 5: Stop services**

```bash
lsof -ti:8000 -sTCP:LISTEN | xargs -r kill
```

(Leave Postgres running via `docker compose` — shared infrastructure.)

---

## Self-Review Notes

- **Spec coverage:** every section of `2026-10-30-voting-dashboard-design.md` maps to a task — `Student`/`Vote` models (Tasks 1–2), session-based login (Task 3), eligibility gate (Task 4), vote wizard + atomic submit (Tasks 5–6), results + archive (Tasks 7–8), student pre-seeding via management command (Task 9, complementing Task 1's admin registration), and the distinct logo pairing (Task 3's `base.html`). The spec's full testing checklist is covered 1:1: matric regex validation → Task 1; login match/mismatch → Task 3; `Vote` uniqueness `IntegrityError` → Task 2; wizard picks not persisted until submit → Tasks 5–6; eligibility gating (`ongoing`-only, "you have voted") → Task 4; results tally accuracy + publish gating + archive → Tasks 7–8.
- **Type/name consistency:** `Election.STATUS_ONGOING` (defined in sub-project 2's `elections/models.py`) is referenced identically in `get_ongoing_election()` (Task 4) and nowhere re-declared or typo'd. `request.session["student_id"]`/`request.session["vote_picks"]` key names are used identically across `login_view`, `student_required`, `vote_entry`, `wizard_step`, and `wizard_review` — cross-checked while writing each task. URL names (`voting:login`, `voting:vote_entry`, `voting:wizard_step`, `voting:wizard_review`, `voting:results`, `voting:results_detail`, `voting:results_archive`) are consistent between `urls.py`, every view's `redirect()`/`reverse()` call, and every template's `{% url %}` tag.
- **No placeholders:** every step has complete, runnable code. The `TemplateView`-based placeholder routes (Task 3's `vote_entry`, Task 4's `wizard_step`/`wizard_review`) are the same deliberate, explicitly-labeled sequencing technique already used and reviewed in sub-project 2's plan — not unfinished work, but a known-safe way to let early tasks' tests pass before the URL names they reference are fully built out.
- **Verified against the real Django install, not assumed:** `unique_together` (Task 2's `Vote.Meta`) was confirmed to still work in Django 6.1.2 with no deprecation warnings (checked directly with `warnings.filterwarnings('error')`, which would have raised if it were deprecated). The matric number regex was confirmed against the spec's own example (`2022/1/90976CF` matches) and against malformed/lowercase-suffix inputs (both correctly rejected). Task 6's original draft used `del request.session["vote_picks"]`, which would raise `KeyError` if a student POSTs to the review page without ever visiting a wizard step (so the key was never set) — fixed to `request.session.pop("vote_picks", None)`, matching the safer pattern `logout_view` already uses for `student_id`.
