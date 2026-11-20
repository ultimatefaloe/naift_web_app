# Multi-Role Access System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the flat `AdminProfile.is_admin` admin-access flag with a three-tier role hierarchy (Superuser → Chairman → Member), gate the Election lifecycle to Chairman-and-above, and add a Committee management page for creating/deactivating Chairmen and Members.

**Architecture:** `AdminProfile` gains `role` (`chairman`/`member`/`None`) and `is_active` fields, replacing `is_admin`. Superuser status stays Django's native `is_superuser` flag — never duplicated into `role`. Three dispatch-based mixins (`AdminRequiredMixin`, `ChairmanOrAboveRequiredMixin`, `SuperuserRequiredMixin`) layer access control onto existing class-based views. A new Committee page and a template context processor round out the visible surface.

**Tech Stack:** Django 6.1, PostgreSQL, existing `admin_panel` app conventions (class-based views, Tailwind-styled templates, `AdminProfile` as the FK target for `modified_by`).

---

## Before you start

Postgres must be running via docker-compose. Verify with `docker ps`; if the daemon isn't reachable, run `systemctl --user start docker-desktop` then `docker compose up -d db`. The full test suite currently has 81+ passing tests (plus a known, pre-existing, unrelated set of template-redesign-caused failures from a concurrent uncommitted change in this working tree — don't try to fix those, they're out of scope for this plan).

Run the baseline before Task 1:

```bash
python manage.py test admin_panel core elections voting -v 1
```

Note the pass/fail count so you can compare after Task 1's mechanical rename.

---

### Task 1: Replace `AdminProfile.is_admin` with `role` + `is_active`

**Files:**
- Modify: `admin_panel/models.py`
- Create: `admin_panel/migrations/0002_adminprofile_role_is_active.py`
- Modify: `admin_panel/mixins.py`
- Modify: `admin_panel/admin.py`
- Modify: `admin_panel/tests.py` (22 call sites), `core/tests.py` (3 call sites), `elections/tests.py` (5 call sites), `voting/tests.py` (7 call sites)

- [ ] **Step 1: Write failing tests for the new fields and the new mixin behavior**

Add this new test class to `admin_panel/tests.py`, directly after the existing `AdminProfileModelTests` class (after line 22, before `class DashboardAccessTests`):

```python
class SuperuserAccessTests(TestCase):
    def test_superuser_gets_adminprofile_auto_created_on_first_dashboard_visit(self):
        superuser = User.objects.create_superuser(
            username="dev_super", password="pass12345", email="dev@example.com"
        )
        self.assertFalse(AdminProfile.objects.filter(user=superuser).exists())
        self.client.force_login(superuser)
        response = self.client.get(reverse("admin_panel:dashboard"))
        self.assertEqual(response.status_code, 200)
        profile = AdminProfile.objects.get(user=superuser)
        self.assertIsNone(profile.role)
        self.assertTrue(profile.is_active)

    def test_deactivated_member_is_denied_dashboard_access(self):
        user = User.objects.create_user(username="deactivated_member", password="pass12345")
        AdminProfile.objects.create(user=user, role=AdminProfile.ROLE_MEMBER, is_active=False)
        self.client.force_login(user)
        response = self.client.get(reverse("admin_panel:dashboard"))
        self.assertRedirects(response, reverse("admin_panel:login"))
```

Also add this new test method inside the existing `AdminProfileModelTests` class (after `test_string_representation`, which you'll fix in Step 4):

```python
    def test_role_and_is_active_default_values(self):
        user = User.objects.create_user(username="admin_defaults", password="pass12345")
        profile = AdminProfile.objects.create(user=user)
        self.assertIsNone(profile.role)
        self.assertTrue(profile.is_active)
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `python manage.py test admin_panel.tests.SuperuserAccessTests admin_panel.tests.AdminProfileModelTests.test_role_and_is_active_default_values -v 2`
Expected: FAIL — `AdminProfile` has no `role` field yet (`TypeError: AdminProfile() got unexpected keyword arguments: 'role'`).

- [ ] **Step 3: Update the model**

Replace the full contents of `admin_panel/models.py`:

```python
from django.conf import settings
from django.db import models


class AdminProfile(models.Model):
    ROLE_CHAIRMAN = "chairman"
    ROLE_MEMBER = "member"
    ROLE_CHOICES = [
        (ROLE_CHAIRMAN, "Chairman"),
        (ROLE_MEMBER, "Member"),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.user.username
```

- [ ] **Step 4: Create the migration**

Create `admin_panel/migrations/0002_adminprofile_role_is_active.py`:

```python
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("admin_panel", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="adminprofile",
            name="role",
            field=models.CharField(
                blank=True,
                choices=[("chairman", "Chairman"), ("member", "Member")],
                max_length=10,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="adminprofile",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
        migrations.RunSQL(
            sql="UPDATE admin_panel_adminprofile SET role = 'member', is_active = is_admin;",
            reverse_sql="UPDATE admin_panel_adminprofile SET role = NULL;",
        ),
        migrations.RemoveField(
            model_name="adminprofile",
            name="is_admin",
        ),
    ]
```

The `RunSQL` step preserves any existing `is_admin=True` accounts as `role=member` (least-privilege default) before the column is dropped — this only matters for real deployed data, not this test suite, but keeps the migration correct for production.

- [ ] **Step 5: Fix the existing `test_string_representation` test**

In `admin_panel/tests.py`, change:

```python
        profile = AdminProfile.objects.create(user=user, is_admin=True)
```

to:

```python
        profile = AdminProfile.objects.create(user=user, role=AdminProfile.ROLE_MEMBER, is_active=True)
```

(This is the `AdminProfile.objects.create(user=user, is_admin=True)` call inside `test_string_representation` — the first one in the file.)

- [ ] **Step 6: Update `AdminRequiredMixin`**

Replace the full contents of `admin_panel/mixins.py`:

```python
from django.contrib import messages
from django.shortcuts import redirect

from .models import AdminProfile


class AdminRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("admin_panel:login")
        if request.user.is_superuser:
            AdminProfile.objects.get_or_create(user=request.user, defaults={"role": None, "is_active": True})
            return super().dispatch(request, *args, **kwargs)
        profile = getattr(request.user, "adminprofile", None)
        if profile is None or not profile.is_active:
            messages.error(request, "You are not authorized to access the admin dashboard.")
            return redirect("admin_panel:login")
        return super().dispatch(request, *args, **kwargs)
```

- [ ] **Step 7: Update `admin_panel/admin.py`**

Replace the full contents:

```python
from django.contrib import admin

from .models import AdminProfile


@admin.register(AdminProfile)
class AdminProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "is_active")
    list_filter = ("role", "is_active")
```

- [ ] **Step 8: Run the Step 1 tests again to verify they pass**

Run: `python manage.py test admin_panel.tests.SuperuserAccessTests admin_panel.tests.AdminProfileModelTests -v 2`
Expected: PASS (3 tests).

- [ ] **Step 9: Fix every other `is_admin=True` call site in `admin_panel/tests.py`**

First verify the file hasn't drifted from what this plan expects:

```bash
grep -n "is_admin=True" admin_panel/tests.py
```

Expected output: exactly these 21 lines (Step 5 already fixed line 21, the 22nd original occurrence):
```
29:        AdminProfile.objects.create(user=self.admin_user, is_admin=True)
57:        self.admin_profile = AdminProfile.objects.create(user=self.admin_user, is_admin=True)
184:        self.admin_profile = AdminProfile.objects.create(user=self.admin_user, is_admin=True)
222:        AdminProfile.objects.create(user=self.admin_user, is_admin=True)
243:        self.admin_profile = AdminProfile.objects.create(user=self.admin_user, is_admin=True)
277:        self.admin_profile = AdminProfile.objects.create(user=self.admin_user, is_admin=True)
372:        AdminProfile.objects.create(user=self.admin_user, is_admin=True)
393:        AdminProfile.objects.create(user=self.admin_user, is_admin=True)
419:        self.admin_profile = AdminProfile.objects.create(user=self.admin_user, is_admin=True)
478:        self.admin_profile = AdminProfile.objects.create(user=self.admin_user, is_admin=True)
618:        self.admin_profile = AdminProfile.objects.create(user=self.admin_user, is_admin=True)
634:        other_profile = AdminProfile.objects.create(user=other_user, is_admin=True)
687:        other_profile = AdminProfile.objects.create(user=other_user, is_admin=True)
704:        self.admin_profile = AdminProfile.objects.create(user=self.admin_user, is_admin=True)
752:        self.admin_profile = AdminProfile.objects.create(user=self.admin_user, is_admin=True)
826:        AdminProfile.objects.create(user=self.admin_user, is_admin=True)
846:        self.admin_profile = AdminProfile.objects.create(user=self.admin_user, is_admin=True)
887:        self.admin_profile = AdminProfile.objects.create(user=self.admin_user, is_admin=True)
948:        AdminProfile.objects.create(user=self.admin_user, is_admin=True)
994:        AdminProfile.objects.create(user=self.admin_user, is_admin=True)
1057:        self.admin_profile = AdminProfile.objects.create(user=self.admin_user, is_admin=True)
```

If the line numbers differ from this list, STOP and re-map each occurrence by reading the surrounding test class instead of trusting line numbers — the replacement rule below still applies, just apply it by hand per occurrence.

If they match, run this single command. Lines 419, 478, 618, 704, 752, 846, and 1057 belong to test classes that call Election-lifecycle URLs (`election_list`, `election_create`, `election_update`, `election_results`, `election_results_print`, `election_start`, `election_end`, `election_publish_results`) and so need `ROLE_CHAIRMAN`. Every other line is a Position/Contestant/Executive/Student/Dashboard/Login-only test (or an unused `modified_by` placeholder profile that never logs in) and gets `ROLE_MEMBER`:

```bash
sed -i \
  -e '29s/is_admin=True/role=AdminProfile.ROLE_MEMBER, is_active=True/' \
  -e '57s/is_admin=True/role=AdminProfile.ROLE_MEMBER, is_active=True/' \
  -e '184s/is_admin=True/role=AdminProfile.ROLE_MEMBER, is_active=True/' \
  -e '222s/is_admin=True/role=AdminProfile.ROLE_MEMBER, is_active=True/' \
  -e '243s/is_admin=True/role=AdminProfile.ROLE_MEMBER, is_active=True/' \
  -e '277s/is_admin=True/role=AdminProfile.ROLE_MEMBER, is_active=True/' \
  -e '372s/is_admin=True/role=AdminProfile.ROLE_MEMBER, is_active=True/' \
  -e '393s/is_admin=True/role=AdminProfile.ROLE_MEMBER, is_active=True/' \
  -e '634s/is_admin=True/role=AdminProfile.ROLE_MEMBER, is_active=True/' \
  -e '687s/is_admin=True/role=AdminProfile.ROLE_MEMBER, is_active=True/' \
  -e '826s/is_admin=True/role=AdminProfile.ROLE_MEMBER, is_active=True/' \
  -e '887s/is_admin=True/role=AdminProfile.ROLE_MEMBER, is_active=True/' \
  -e '948s/is_admin=True/role=AdminProfile.ROLE_MEMBER, is_active=True/' \
  -e '994s/is_admin=True/role=AdminProfile.ROLE_MEMBER, is_active=True/' \
  -e '419s/is_admin=True/role=AdminProfile.ROLE_CHAIRMAN, is_active=True/' \
  -e '478s/is_admin=True/role=AdminProfile.ROLE_CHAIRMAN, is_active=True/' \
  -e '618s/is_admin=True/role=AdminProfile.ROLE_CHAIRMAN, is_active=True/' \
  -e '704s/is_admin=True/role=AdminProfile.ROLE_CHAIRMAN, is_active=True/' \
  -e '752s/is_admin=True/role=AdminProfile.ROLE_CHAIRMAN, is_active=True/' \
  -e '846s/is_admin=True/role=AdminProfile.ROLE_CHAIRMAN, is_active=True/' \
  -e '1057s/is_admin=True/role=AdminProfile.ROLE_CHAIRMAN, is_active=True/' \
  admin_panel/tests.py
```

Then verify no occurrences remain: `grep -n "is_admin" admin_panel/tests.py` → expected: no output.

(Line 846 belongs to `ElectionActionModalTests`, which only GETs `election_list` to check button markup — it needs `ROLE_CHAIRMAN` because `election_list` is now Chairman-gated, same reasoning as the other Election-touching classes.)

- [ ] **Step 10: Fix `core/tests.py`, `elections/tests.py`, `voting/tests.py`**

None of these three files test `admin_panel`'s permission system — they only need a valid `AdminProfile` to satisfy the `modified_by` foreign key on `Position`/`Election`/etc. Drop the now-nonexistent kwarg entirely:

```bash
sed -i 's/, is_admin=True)/)/g' core/tests.py elections/tests.py voting/tests.py
```

Verify: `grep -rn "is_admin" core/tests.py elections/tests.py voting/tests.py` → expected: no output.

- [ ] **Step 11: Run the full test suite**

Run: `python manage.py test admin_panel core elections voting -v 1`
Expected: same pass count as the "Before you start" baseline, plus the 3 new tests from Step 1 — zero new failures. (The known pre-existing unrelated template-redesign failures from the start of this session may still be present; don't try to fix those.)

- [ ] **Step 12: Commit**

```bash
git add admin_panel/models.py admin_panel/migrations/0002_adminprofile_role_is_active.py admin_panel/mixins.py admin_panel/admin.py admin_panel/tests.py core/tests.py elections/tests.py voting/tests.py
git commit -m "Replace AdminProfile.is_admin with role + is_active fields"
```

---

### Task 2: Gate the Election lifecycle to Chairman-and-above

**Files:**
- Modify: `admin_panel/mixins.py`
- Modify: `admin_panel/views.py:270-373` (the 8 Election view classes)
- Modify: `admin_panel/tests.py`

- [ ] **Step 1: Write failing tests for Member denial / Chairman allowance**

Add this new test class to `admin_panel/tests.py`, after `ElectionActionModalTests` (i.e. right before `class StudentCRUDTests`):

```python
class ElectionViewsMemberAccessTests(TestCase):
    def setUp(self):
        self.member_user = User.objects.create_user(username="member_blocked", password="pass12345")
        self.member_profile = AdminProfile.objects.create(
            user=self.member_user, role=AdminProfile.ROLE_MEMBER, is_active=True
        )
        self.client.force_login(self.member_user)
        self.election = Election.objects.create(
            session="2026/2027",
            start_time="2026-11-01T09:00:00Z",
            close_time="2026-11-01T17:00:00Z",
            status="upcoming",
            modified_by=self.member_profile,
        )

    def test_member_cannot_view_election_list(self):
        response = self.client.get(reverse("admin_panel:election_list"))
        self.assertRedirects(response, reverse("admin_panel:dashboard"))

    def test_member_cannot_create_election(self):
        response = self.client.get(reverse("admin_panel:election_create"))
        self.assertRedirects(response, reverse("admin_panel:dashboard"))

    def test_member_cannot_update_election(self):
        response = self.client.get(reverse("admin_panel:election_update", args=[self.election.pk]))
        self.assertRedirects(response, reverse("admin_panel:dashboard"))

    def test_member_cannot_view_election_results(self):
        response = self.client.get(reverse("admin_panel:election_results", args=[self.election.pk]))
        self.assertRedirects(response, reverse("admin_panel:dashboard"))

    def test_member_cannot_view_results_print(self):
        self.election.is_results_published = True
        self.election.save()
        response = self.client.get(reverse("admin_panel:election_results_print", args=[self.election.pk]))
        self.assertRedirects(response, reverse("admin_panel:dashboard"))

    def test_member_cannot_start_election(self):
        response = self.client.post(reverse("admin_panel:election_start", args=[self.election.pk]))
        self.assertRedirects(response, reverse("admin_panel:dashboard"))
        self.election.refresh_from_db()
        self.assertEqual(self.election.status, "upcoming")

    def test_member_cannot_end_election(self):
        self.election.status = "ongoing"
        self.election.save()
        response = self.client.post(reverse("admin_panel:election_end", args=[self.election.pk]))
        self.assertRedirects(response, reverse("admin_panel:dashboard"))

    def test_member_cannot_publish_results(self):
        self.election.status = "ended"
        self.election.save()
        response = self.client.post(reverse("admin_panel:election_publish_results", args=[self.election.pk]))
        self.assertRedirects(response, reverse("admin_panel:dashboard"))

    def test_chairman_can_view_election_list(self):
        chairman_user = User.objects.create_user(username="chairman_allowed", password="pass12345")
        AdminProfile.objects.create(user=chairman_user, role=AdminProfile.ROLE_CHAIRMAN, is_active=True)
        self.client.logout()
        self.client.force_login(chairman_user)
        response = self.client.get(reverse("admin_panel:election_list"))
        self.assertEqual(response.status_code, 200)
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `python manage.py test admin_panel.tests.ElectionViewsMemberAccessTests -v 2`
Expected: FAIL — `election_list` etc. still use `AdminRequiredMixin`, so a Member (who has an active `AdminProfile`) is let through with a 200 instead of being redirected to the dashboard.

- [ ] **Step 3: Add `ChairmanOrAboveRequiredMixin`**

Append this class to the end of `admin_panel/mixins.py` (after `AdminRequiredMixin`):

```python


class ChairmanOrAboveRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("admin_panel:login")
        if request.user.is_superuser:
            AdminProfile.objects.get_or_create(user=request.user, defaults={"role": None, "is_active": True})
            return super().dispatch(request, *args, **kwargs)
        profile = getattr(request.user, "adminprofile", None)
        if profile is None or not profile.is_active:
            messages.error(request, "You are not authorized to access the admin dashboard.")
            return redirect("admin_panel:login")
        if profile.role != AdminProfile.ROLE_CHAIRMAN:
            messages.error(request, "You are not authorized to access this page.")
            return redirect("admin_panel:dashboard")
        return super().dispatch(request, *args, **kwargs)
```

- [ ] **Step 4: Apply the new mixin to the 8 Election views**

In `admin_panel/views.py`, add `ChairmanOrAboveRequiredMixin` to the imports:

```python
from .mixins import AdminRequiredMixin, ChairmanOrAboveRequiredMixin
```

Then change the base class on each of these 8 class declarations (each `old_string` below is unique in the file):

```python
class ElectionListView(AdminRequiredMixin, ListView):
```
→
```python
class ElectionListView(ChairmanOrAboveRequiredMixin, ListView):
```

```python
class ElectionCreateView(AdminRequiredMixin, CreateView):
```
→
```python
class ElectionCreateView(ChairmanOrAboveRequiredMixin, CreateView):
```

```python
class ElectionUpdateView(AdminRequiredMixin, UpdateView):
```
→
```python
class ElectionUpdateView(ChairmanOrAboveRequiredMixin, UpdateView):
```

```python
class ElectionResultsView(AdminRequiredMixin, DetailView):
```
→
```python
class ElectionResultsView(ChairmanOrAboveRequiredMixin, DetailView):
```

```python
class ElectionResultsPrintView(AdminRequiredMixin, DetailView):
```
→
```python
class ElectionResultsPrintView(ChairmanOrAboveRequiredMixin, DetailView):
```

```python
class ElectionStartView(AdminRequiredMixin, View):
```
→
```python
class ElectionStartView(ChairmanOrAboveRequiredMixin, View):
```

```python
class ElectionEndView(AdminRequiredMixin, View):
```
→
```python
class ElectionEndView(ChairmanOrAboveRequiredMixin, View):
```

```python
class ElectionPublishResultsView(AdminRequiredMixin, View):
```
→
```python
class ElectionPublishResultsView(ChairmanOrAboveRequiredMixin, View):
```

- [ ] **Step 5: Run the new tests to verify they pass**

Run: `python manage.py test admin_panel.tests.ElectionViewsMemberAccessTests -v 2`
Expected: PASS (9 tests).

- [ ] **Step 6: Run the full test suite**

Run: `python manage.py test admin_panel core elections voting -v 1`
Expected: all Election-related tests from Task 1 (which already use `ROLE_CHAIRMAN`) still pass; no new failures.

- [ ] **Step 7: Commit**

```bash
git add admin_panel/mixins.py admin_panel/views.py admin_panel/tests.py
git commit -m "Restrict Election lifecycle views to Chairman and Superuser"
```

---

### Task 3: Committee management page

**Files:**
- Modify: `admin_panel/mixins.py`
- Modify: `admin_panel/forms.py`
- Modify: `admin_panel/views.py`
- Modify: `admin_panel/urls.py`
- Create: `admin_panel/templates/admin_panel/committee_list.html`
- Create: `admin_panel/templates/admin_panel/committee_admin_form.html`
- Modify: `admin_panel/tests.py`

- [ ] **Step 1: Write failing tests**

Add this new test class to the end of `admin_panel/tests.py`:

```python
class CommitteeManagementTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username="hod_super", password="pass12345", email="hod@example.com"
        )
        self.client.force_login(self.superuser)

    def test_superuser_creates_first_chairman(self):
        response = self.client.post(
            reverse("admin_panel:committee_add_chairman"),
            {
                "username": "chairman_one",
                "email": "chairman1@example.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )
        self.assertRedirects(response, reverse("admin_panel:committee_list"))
        profile = AdminProfile.objects.get(user__username="chairman_one")
        self.assertEqual(profile.role, AdminProfile.ROLE_CHAIRMAN)
        self.assertTrue(profile.is_active)

    def test_creating_new_chairman_demotes_previous_chairman_to_member(self):
        old_chairman_user = User.objects.create_user(username="chairman_old", password="pass12345")
        old_chairman_profile = AdminProfile.objects.create(
            user=old_chairman_user, role=AdminProfile.ROLE_CHAIRMAN, is_active=True
        )
        self.client.post(
            reverse("admin_panel:committee_add_chairman"),
            {
                "username": "chairman_new",
                "email": "chairman2@example.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )
        old_chairman_profile.refresh_from_db()
        self.assertEqual(old_chairman_profile.role, AdminProfile.ROLE_MEMBER)
        self.assertTrue(old_chairman_profile.is_active)
        new_chairman_profile = AdminProfile.objects.get(user__username="chairman_new")
        self.assertEqual(new_chairman_profile.role, AdminProfile.ROLE_CHAIRMAN)

    def test_chairman_creates_member(self):
        chairman_user = User.objects.create_user(username="chairman_active", password="pass12345")
        AdminProfile.objects.create(user=chairman_user, role=AdminProfile.ROLE_CHAIRMAN, is_active=True)
        self.client.logout()
        self.client.force_login(chairman_user)
        response = self.client.post(
            reverse("admin_panel:committee_add_member"),
            {
                "username": "member_one",
                "email": "member1@example.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )
        self.assertRedirects(response, reverse("admin_panel:committee_list"))
        profile = AdminProfile.objects.get(user__username="member_one")
        self.assertEqual(profile.role, AdminProfile.ROLE_MEMBER)

    def test_member_cannot_create_chairman(self):
        member_user = User.objects.create_user(username="member_blocked2", password="pass12345")
        AdminProfile.objects.create(user=member_user, role=AdminProfile.ROLE_MEMBER, is_active=True)
        self.client.logout()
        self.client.force_login(member_user)
        response = self.client.get(reverse("admin_panel:committee_add_chairman"))
        self.assertRedirects(response, reverse("admin_panel:dashboard"))

    def test_chairman_cannot_create_chairman(self):
        chairman_user = User.objects.create_user(username="chairman_cant_promote", password="pass12345")
        AdminProfile.objects.create(user=chairman_user, role=AdminProfile.ROLE_CHAIRMAN, is_active=True)
        self.client.logout()
        self.client.force_login(chairman_user)
        response = self.client.get(reverse("admin_panel:committee_add_chairman"))
        self.assertRedirects(response, reverse("admin_panel:dashboard"))

    def test_chairman_deactivates_any_member(self):
        chairman_user = User.objects.create_user(username="chairman_deactivator", password="pass12345")
        AdminProfile.objects.create(user=chairman_user, role=AdminProfile.ROLE_CHAIRMAN, is_active=True)
        member_user = User.objects.create_user(username="member_to_deactivate", password="pass12345")
        member_profile = AdminProfile.objects.create(
            user=member_user, role=AdminProfile.ROLE_MEMBER, is_active=True
        )
        self.client.logout()
        self.client.force_login(chairman_user)
        response = self.client.post(reverse("admin_panel:committee_deactivate", args=[member_profile.pk]))
        self.assertRedirects(response, reverse("admin_panel:committee_list"))
        member_profile.refresh_from_db()
        self.assertFalse(member_profile.is_active)

    def test_chairman_cannot_deactivate_self(self):
        chairman_user = User.objects.create_user(username="chairman_self", password="pass12345")
        chairman_profile = AdminProfile.objects.create(
            user=chairman_user, role=AdminProfile.ROLE_CHAIRMAN, is_active=True
        )
        self.client.logout()
        self.client.force_login(chairman_user)
        response = self.client.post(reverse("admin_panel:committee_deactivate", args=[chairman_profile.pk]))
        self.assertRedirects(response, reverse("admin_panel:committee_list"))
        chairman_profile.refresh_from_db()
        self.assertTrue(chairman_profile.is_active)

    def test_deactivated_member_can_be_reactivated(self):
        member_user = User.objects.create_user(username="member_reactivate", password="pass12345")
        member_profile = AdminProfile.objects.create(
            user=member_user, role=AdminProfile.ROLE_MEMBER, is_active=False
        )
        response = self.client.post(reverse("admin_panel:committee_reactivate", args=[member_profile.pk]))
        self.assertRedirects(response, reverse("admin_panel:committee_list"))
        member_profile.refresh_from_db()
        self.assertTrue(member_profile.is_active)

    def test_committee_list_shows_superuser_section_to_superuser(self):
        response = self.client.get(reverse("admin_panel:committee_list"))
        self.assertContains(response, "hod_super")

    def test_committee_list_hides_superuser_section_from_chairman(self):
        chairman_user = User.objects.create_user(username="chairman_viewer", password="pass12345")
        AdminProfile.objects.create(user=chairman_user, role=AdminProfile.ROLE_CHAIRMAN, is_active=True)
        self.client.logout()
        self.client.force_login(chairman_user)
        response = self.client.get(reverse("admin_panel:committee_list"))
        self.assertNotContains(response, "hod_super")
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `python manage.py test admin_panel.tests.CommitteeManagementTests -v 2`
Expected: FAIL — `NoReverseMatch` for `admin_panel:committee_add_chairman` (URL doesn't exist yet).

- [ ] **Step 3: Add `SuperuserRequiredMixin`**

Append this class to the end of `admin_panel/mixins.py`:

```python


class SuperuserRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("admin_panel:login")
        if not request.user.is_superuser:
            messages.error(request, "You are not authorized to access this page.")
            return redirect("admin_panel:dashboard")
        AdminProfile.objects.get_or_create(user=request.user, defaults={"role": None, "is_active": True})
        return super().dispatch(request, *args, **kwargs)
```

- [ ] **Step 4: Add the account-creation form**

Replace the full contents of `admin_panel/forms.py`:

```python
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from elections.models import Election


class ElectionForm(forms.ModelForm):
    class Meta:
        model = Election
        fields = ["session", "start_time", "close_time", "status", "is_results_published"]
        widgets = {
            "start_time": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "close_time": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        }


class AdminAccountCreateForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ["username", "email"]
```

- [ ] **Step 5: Add the Committee views**

In `admin_panel/views.py`, update the imports:

```python
from django.contrib.auth.models import User
from django.db import transaction
```

(Add these two lines alongside the existing imports at the top of the file.)

Update the mixins import line to:

```python
from .mixins import AdminRequiredMixin, ChairmanOrAboveRequiredMixin, SuperuserRequiredMixin
```

Update the forms import line to:

```python
from .forms import AdminAccountCreateForm, ElectionForm
```

Append these view classes to the end of `admin_panel/views.py`:

```python


class CommitteeListView(ChairmanOrAboveRequiredMixin, TemplateView):
    template_name = "admin_panel/committee_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["chairmen"] = (
            AdminProfile.objects.filter(role=AdminProfile.ROLE_CHAIRMAN)
            .select_related("user")
            .order_by("user__username")
        )
        context["members"] = (
            AdminProfile.objects.filter(role=AdminProfile.ROLE_MEMBER)
            .select_related("user")
            .order_by("user__username")
        )
        if self.request.user.is_superuser:
            context["superusers"] = User.objects.filter(is_superuser=True).order_by("username")
        return context


class ChairmanCreateView(SuperuserRequiredMixin, CreateView):
    form_class = AdminAccountCreateForm
    template_name = "admin_panel/committee_admin_form.html"
    success_url = reverse_lazy("admin_panel:committee_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["role_label"] = "Chairman"
        return context

    def form_valid(self, form):
        with transaction.atomic():
            response = super().form_valid(form)
            AdminProfile.objects.filter(role=AdminProfile.ROLE_CHAIRMAN, is_active=True).update(
                role=AdminProfile.ROLE_MEMBER
            )
            AdminProfile.objects.create(user=self.object, role=AdminProfile.ROLE_CHAIRMAN, is_active=True)
        messages.success(self.request, f"{self.object.username} is now the ELECOM Chairman.")
        return response


class MemberCreateView(ChairmanOrAboveRequiredMixin, CreateView):
    form_class = AdminAccountCreateForm
    template_name = "admin_panel/committee_admin_form.html"
    success_url = reverse_lazy("admin_panel:committee_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["role_label"] = "Member"
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        AdminProfile.objects.create(user=self.object, role=AdminProfile.ROLE_MEMBER, is_active=True)
        messages.success(self.request, f"{self.object.username} added as an ELECOM Member.")
        return response


class AdminDeactivateView(ChairmanOrAboveRequiredMixin, View):
    def post(self, request, pk):
        profile = get_object_or_404(AdminProfile, pk=pk)
        if profile.user_id == request.user.id:
            messages.error(request, "You cannot deactivate your own account.")
            return redirect("admin_panel:committee_list")
        if profile.role is None:
            messages.error(request, "Superuser accounts cannot be managed here.")
            return redirect("admin_panel:committee_list")
        if profile.role == AdminProfile.ROLE_CHAIRMAN and not request.user.is_superuser:
            messages.error(request, "Only a Superuser can deactivate a Chairman.")
            return redirect("admin_panel:committee_list")
        profile.is_active = False
        profile.save()
        messages.success(request, f"{profile.user.username} has been deactivated.")
        return redirect("admin_panel:committee_list")


class AdminReactivateView(ChairmanOrAboveRequiredMixin, View):
    def post(self, request, pk):
        profile = get_object_or_404(AdminProfile, pk=pk)
        if profile.role == AdminProfile.ROLE_CHAIRMAN and not request.user.is_superuser:
            messages.error(request, "Only a Superuser can reactivate a Chairman.")
            return redirect("admin_panel:committee_list")
        profile.is_active = True
        profile.save()
        messages.success(request, f"{profile.user.username} has been reactivated.")
        return redirect("admin_panel:committee_list")
```

`admin_panel/views.py` does not currently import its own `models.py` at all. Add this line to the imports block too:

```python
from .models import AdminProfile
```

- [ ] **Step 6: Add the URLs**

In `admin_panel/urls.py`, append after the `election_publish_results` path (before the closing `]`):

```python
    path("committee/", views.CommitteeListView.as_view(), name="committee_list"),
    path("committee/add-chairman/", views.ChairmanCreateView.as_view(), name="committee_add_chairman"),
    path("committee/add-member/", views.MemberCreateView.as_view(), name="committee_add_member"),
    path("committee/<int:pk>/deactivate/", views.AdminDeactivateView.as_view(), name="committee_deactivate"),
    path("committee/<int:pk>/reactivate/", views.AdminReactivateView.as_view(), name="committee_reactivate"),
```

- [ ] **Step 7: Add the templates**

Create `admin_panel/templates/admin_panel/committee_list.html`:

```html
{% extends "admin_panel/base.html" %}

{% block title %}Committee · NAIFT Admin{% endblock %}

{% block content %}
<div class="page-header">
    <div>
        <h1 class="page-header__title">ELECOM Committee</h1>
        <p class="page-header__sub">Manage who has access to the admin dashboard.</p>
    </div>
    <div class="flex gap-2">
        {% if user.is_superuser %}
        <a href="{% url 'admin_panel:committee_add_chairman' %}" class="btn btn-primary">+ Add Chairman</a>
        {% endif %}
        <a href="{% url 'admin_panel:committee_add_member' %}" class="btn btn-primary">+ Add Member</a>
    </div>
</div>

<dialog id="confirm-modal" class="fixed top-1/2 left-1/2 m-0 -translate-x-1/2 -translate-y-1/2 max-w-sm w-full rounded-lg border border-brand-purple/20 p-6">
    <p id="confirm-modal-message" class="mb-6 text-brand-black"></p>
    <div class="flex justify-end gap-3">
        <button type="button" data-confirm-cancel class="text-brand-black/70 hover:underline">Cancel</button>
        <button type="button" data-confirm-accept class="bg-brand-purple text-brand-white px-4 py-2 rounded hover:opacity-90">Confirm</button>
    </div>
</dialog>

{% if superusers %}
<h2 class="mt-8 mb-3 text-sm font-semibold uppercase tracking-wider text-neutral-500">Superusers</h2>
<div class="table-wrap">
    <table class="table">
        <thead>
            <tr><th>Username</th><th>Email</th></tr>
        </thead>
        <tbody>
            {% for superuser in superusers %}
            <tr>
                <td class="font-medium text-brand-black">{{ superuser.username }}</td>
                <td class="text-neutral-600">{{ superuser.email|default:"—" }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endif %}

<h2 class="mt-8 mb-3 text-sm font-semibold uppercase tracking-wider text-neutral-500">Chairman</h2>
{% if chairmen %}
<div class="table-wrap">
    <table class="table">
        <thead>
            <tr><th>Username</th><th>Status</th><th></th></tr>
        </thead>
        <tbody>
            {% for profile in chairmen %}
            <tr>
                <td class="font-medium text-brand-black">{{ profile.user.username }}</td>
                <td>
                    {% if profile.is_active %}
                        <span class="badge badge-success">Active</span>
                    {% else %}
                        <span class="badge">Deactivated</span>
                    {% endif %}
                </td>
                <td>
                    {% if user.is_superuser and profile.user_id != user.id %}
                    <div class="table-actions">
                        {% if profile.is_active %}
                            <form method="post" action="{% url 'admin_panel:committee_deactivate' profile.pk %}"
                                  id="deactivate-{{ profile.pk }}">
                                {% csrf_token %}
                            </form>
                            <button type="button" class="danger cursor-pointer"
                                    data-confirm-form="deactivate-{{ profile.pk }}"
                                    data-confirm-message="Deactivate {{ profile.user.username|escapejs }}?">Deactivate</button>
                        {% else %}
                            <form method="post" action="{% url 'admin_panel:committee_reactivate' profile.pk %}">
                                {% csrf_token %}
                                <button type="submit" class="cursor-pointer">Reactivate</button>
                            </form>
                        {% endif %}
                    </div>
                    {% endif %}
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% else %}
<p class="text-neutral-500">No Chairman has been appointed yet.</p>
{% endif %}

<h2 class="mt-8 mb-3 text-sm font-semibold uppercase tracking-wider text-neutral-500">Members</h2>
{% if members %}
<div class="table-wrap">
    <table class="table">
        <thead>
            <tr><th>Username</th><th>Status</th><th></th></tr>
        </thead>
        <tbody>
            {% for profile in members %}
            <tr>
                <td class="font-medium text-brand-black">{{ profile.user.username }}</td>
                <td>
                    {% if profile.is_active %}
                        <span class="badge badge-success">Active</span>
                    {% else %}
                        <span class="badge">Deactivated</span>
                    {% endif %}
                </td>
                <td>
                    {% if profile.user_id != user.id %}
                    <div class="table-actions">
                        {% if profile.is_active %}
                            <form method="post" action="{% url 'admin_panel:committee_deactivate' profile.pk %}"
                                  id="deactivate-{{ profile.pk }}">
                                {% csrf_token %}
                            </form>
                            <button type="button" class="danger cursor-pointer"
                                    data-confirm-form="deactivate-{{ profile.pk }}"
                                    data-confirm-message="Deactivate {{ profile.user.username|escapejs }}?">Deactivate</button>
                        {% else %}
                            <form method="post" action="{% url 'admin_panel:committee_reactivate' profile.pk %}">
                                {% csrf_token %}
                                <button type="submit" class="cursor-pointer">Reactivate</button>
                            </form>
                        {% endif %}
                    </div>
                    {% endif %}
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% else %}
<p class="text-neutral-500">No Members yet.</p>
{% endif %}

{% include "admin_panel/_confirm_modal_script.html" %}
{% endblock %}
```

Create `admin_panel/templates/admin_panel/committee_admin_form.html`:

```html
{% extends "admin_panel/base.html" %}

{% block title %}Add {{ role_label }} · NAIFT Admin{% endblock %}

{% block content %}
<a href="{% url 'admin_panel:committee_list' %}"
   class="mb-4 inline-block text-sm font-medium text-brand-purple hover:underline">
    ← Back to Committee
</a>

<div class="page-header">
    <h1 class="page-header__title">Add {{ role_label }}</h1>
</div>

<form method="post" class="max-w-xl border border-neutral-200 bg-white p-6 sm:p-8">
    {% csrf_token %}

    {% if form.non_field_errors %}
        <div class="alert alert-error mb-4">{{ form.non_field_errors.0 }}</div>
    {% endif %}

    <div class="flex flex-col gap-5">
        {% for field in form %}
            <div class="form-field">
                <label class="form-label" for="{{ field.id_for_label }}">
                    {{ field.label }}{% if field.field.required %} <span class="req">*</span>{% endif %}
                </label>
                <input type="{{ field.field.widget.input_type|default:'text' }}"
                       name="{{ field.html_name }}"
                       id="{{ field.id_for_label }}"
                       {% if field.field.widget.input_type != 'password' %}value="{{ field.value|default_if_none:'' }}"{% endif %}
                       class="form-input"
                       {% if field.field.required %}required{% endif %}>
                {% if field.help_text %}<p class="form-help">{{ field.help_text|safe }}</p>{% endif %}
                {% if field.errors %}<p class="form-error">{{ field.errors.0 }}</p>{% endif %}
            </div>
        {% endfor %}
    </div>

    <div class="mt-8 flex flex-wrap items-center justify-between gap-3 border-t border-neutral-200 pt-6">
        <a href="{% url 'admin_panel:committee_list' %}" class="btn btn-ghost">Cancel</a>
        <button type="submit" class="btn btn-primary">Save {{ role_label }}</button>
    </div>
</form>
{% endblock %}
```

Note the `{% if field.field.widget.input_type != 'password' %}` guard around `value=` — password fields must never echo a submitted value back into the rendered HTML on a validation error (e.g. a password-mismatch resubmit), unlike every other field type on this form.

- [ ] **Step 8: Run the new tests to verify they pass**

Run: `python manage.py test admin_panel.tests.CommitteeManagementTests -v 2`
Expected: PASS (11 tests).

- [ ] **Step 9: Run the full test suite**

Run: `python manage.py test admin_panel core elections voting -v 1`
Expected: no new failures.

- [ ] **Step 10: Commit**

```bash
git add admin_panel/mixins.py admin_panel/forms.py admin_panel/views.py admin_panel/urls.py admin_panel/templates/admin_panel/committee_list.html admin_panel/templates/admin_panel/committee_admin_form.html admin_panel/tests.py
git commit -m "Add ELECOM Committee management page"
```

---

### Task 4: Nav visibility via context processor

**Files:**
- Create: `admin_panel/context_processors.py`
- Modify: `web/settings.py`
- Modify: `admin_panel/templates/admin_panel/base.html`
- Modify: `admin_panel/tests.py`

- [ ] **Step 1: Write failing tests**

Add this new test class to the end of `admin_panel/tests.py`:

```python
class AdminRoleFlagsContextProcessorTests(TestCase):
    def test_member_cannot_see_elections_or_committee_links(self):
        user = User.objects.create_user(username="nav_member", password="pass12345")
        AdminProfile.objects.create(user=user, role=AdminProfile.ROLE_MEMBER, is_active=True)
        self.client.force_login(user)
        response = self.client.get(reverse("admin_panel:dashboard"))
        self.assertNotContains(response, reverse("admin_panel:election_list"))
        self.assertNotContains(response, reverse("admin_panel:committee_list"))

    def test_chairman_sees_elections_and_committee_links(self):
        user = User.objects.create_user(username="nav_chairman", password="pass12345")
        AdminProfile.objects.create(user=user, role=AdminProfile.ROLE_CHAIRMAN, is_active=True)
        self.client.force_login(user)
        response = self.client.get(reverse("admin_panel:dashboard"))
        self.assertContains(response, reverse("admin_panel:election_list"))
        self.assertContains(response, reverse("admin_panel:committee_list"))

    def test_superuser_sees_elections_and_committee_links(self):
        user = User.objects.create_superuser(username="nav_super", password="pass12345", email="s@example.com")
        self.client.force_login(user)
        response = self.client.get(reverse("admin_panel:dashboard"))
        self.assertContains(response, reverse("admin_panel:election_list"))
        self.assertContains(response, reverse("admin_panel:committee_list"))
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `python manage.py test admin_panel.tests.AdminRoleFlagsContextProcessorTests -v 2`
Expected: FAIL — `can_manage_elections`/`can_manage_committee` don't exist, so the "Elections" link always renders (visible for Member too) and "Committee" never renders (not visible for Chairman/Superuser either, since the link doesn't exist in the template yet).

- [ ] **Step 3: Create the context processor**

Create `admin_panel/context_processors.py`:

```python
from .models import AdminProfile


def admin_role_flags(request):
    user = request.user
    if not user.is_authenticated:
        return {"can_manage_elections": False, "can_manage_committee": False}
    if user.is_superuser:
        return {"can_manage_elections": True, "can_manage_committee": True}
    profile = getattr(user, "adminprofile", None)
    is_chairman = bool(profile and profile.is_active and profile.role == AdminProfile.ROLE_CHAIRMAN)
    return {"can_manage_elections": is_chairman, "can_manage_committee": is_chairman}
```

- [ ] **Step 4: Register it in settings**

In `web/settings.py`, inside `TEMPLATES[0]['OPTIONS']['context_processors']`, add a new line after `'elections.context_processors.election_status',`:

```python
                'admin_panel.context_processors.admin_role_flags',
```

- [ ] **Step 5: Update the desktop nav in `admin_panel/base.html`**

Change:

```html
                <a href="{% url 'admin_panel:election_list' %}"
                   class="px-3 py-2 font-medium text-white/70 transition-colors hover:text-white
                          {% if 'election' in current %}text-white{% endif %}">Elections</a>
            </nav>
            {% endwith %}
```

to:

```html
                {% if can_manage_elections %}
                <a href="{% url 'admin_panel:election_list' %}"
                   class="px-3 py-2 font-medium text-white/70 transition-colors hover:text-white
                          {% if 'election' in current %}text-white{% endif %}">Elections</a>
                {% endif %}
                {% if can_manage_committee %}
                <a href="{% url 'admin_panel:committee_list' %}"
                   class="px-3 py-2 font-medium text-white/70 transition-colors hover:text-white
                          {% if 'committee' in current %}text-white{% endif %}">Committee</a>
                {% endif %}
            </nav>
            {% endwith %}
```

- [ ] **Step 6: Update the mobile drawer in `admin_panel/base.html`**

Change:

```html
                    <li>
                        <a href="{% url 'admin_panel:election_list' %}"
                           class="flex items-center justify-between border-l-2 px-3 py-3 font-medium transition-colors
                                  {% if 'election' in current %}
                                      border-brand-purple bg-white/10 text-white
                                  {% else %}
                                      border-transparent text-white/70 hover:bg-white/5 hover:text-white
                                  {% endif %}">
                            Elections
                        </a>
                    </li>
                </ul>

                <p class="mt-6 px-2 pb-2 text-[11px] font-semibold uppercase tracking-wider text-white/40">Site</p>
```

to:

```html
                    {% if can_manage_elections %}
                    <li>
                        <a href="{% url 'admin_panel:election_list' %}"
                           class="flex items-center justify-between border-l-2 px-3 py-3 font-medium transition-colors
                                  {% if 'election' in current %}
                                      border-brand-purple bg-white/10 text-white
                                  {% else %}
                                      border-transparent text-white/70 hover:bg-white/5 hover:text-white
                                  {% endif %}">
                            Elections
                        </a>
                    </li>
                    {% endif %}
                    {% if can_manage_committee %}
                    <li>
                        <a href="{% url 'admin_panel:committee_list' %}"
                           class="flex items-center justify-between border-l-2 px-3 py-3 font-medium transition-colors
                                  {% if 'committee' in current %}
                                      border-brand-purple bg-white/10 text-white
                                  {% else %}
                                      border-transparent text-white/70 hover:bg-white/5 hover:text-white
                                  {% endif %}">
                            Committee
                        </a>
                    </li>
                    {% endif %}
                </ul>

                <p class="mt-6 px-2 pb-2 text-[11px] font-semibold uppercase tracking-wider text-white/40">Site</p>
```

- [ ] **Step 7: Run the new tests to verify they pass**

Run: `python manage.py test admin_panel.tests.AdminRoleFlagsContextProcessorTests -v 2`
Expected: PASS (3 tests).

- [ ] **Step 8: Run the full test suite**

Run: `python manage.py test admin_panel core elections voting -v 1`
Expected: no new failures. In particular, `AdminNavTests` (which only checks Public Site and Students links) should be unaffected.

- [ ] **Step 9: Commit**

```bash
git add admin_panel/context_processors.py web/settings.py admin_panel/templates/admin_panel/base.html admin_panel/tests.py
git commit -m "Hide Elections/Committee nav links from Members"
```

---

### Task 5: Final verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite one more time**

Run: `python manage.py test admin_panel core elections voting -v 1`
Expected: every test added across Tasks 1-4 passes; no regressions versus the Task 1 "before you start" baseline.

- [ ] **Step 2: Run Django's migration check**

Run: `python manage.py makemigrations --check --dry-run`
Expected: "No changes detected" — confirms the hand-written migration in Task 1 fully captures the model state.

- [ ] **Step 3: Flag the manual follow-up step to the user**

This plan cannot determine, from code alone, which existing account (if any) should hold the Chairman role after this ships to an environment with real pre-existing `AdminProfile` data — the migration in Task 1 safely defaults every existing admin to `role=member`. After deploying, a Superuser must log in and use the new Committee page (`/committee/` under the admin panel) to promote the correct person to Chairman. Note this for the user; it is not something a subagent or this plan can complete on its own.

- [ ] **Step 4: Flag the manual browser smoke-test step to the user**

As with every prior sub-project in this session, a subagent cannot fully verify the UI in a real browser. Note for the user: manually log in as a Member and confirm the Elections/Committee nav links are absent and direct URL access redirects to the dashboard; log in as a Superuser (or promote a Chairman via `/admin/` → set `is_superuser=True` on a test account) and confirm the Committee page, Chairman creation (with demotion), Member creation, and deactivate/reactivate all work end-to-end in the browser.
