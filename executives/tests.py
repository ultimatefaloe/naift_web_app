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
