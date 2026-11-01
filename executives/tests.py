from django.test import TestCase
from django.urls import reverse

from .models import Executive


class ExecutiveModelTests(TestCase):
    def test_string_representation(self):
        executive = Executive(name="Jane Doe", position="President")
        self.assertEqual(str(executive), "Jane Doe (President)")


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

    def test_past_executives_render_grouped_and_grayscale(self):
        response = self.client.get(reverse("executives:current"))
        self.assertContains(response, "Past Executive — 2025/2026")
        self.assertContains(response, "John Smith")
        self.assertContains(response, "grayscale")

    def test_current_and_past_sections_both_render_together(self):
        response = self.client.get(reverse("executives:current"))
        self.assertContains(response, "Current Executive")
        self.assertContains(response, "Jane Doe")
        self.assertContains(response, "Past Executive — 2025/2026")
        self.assertContains(response, "John Smith")

    def test_no_past_executives_shows_no_past_section(self):
        self.past.delete()
        response = self.client.get(reverse("executives:current"))
        self.assertNotContains(response, "Past Executives")
