from django.test import TestCase

from .models import Executive


class ExecutiveModelTests(TestCase):
    def test_string_representation(self):
        executive = Executive(name="Jane Doe", position="President")
        self.assertEqual(str(executive), "Jane Doe (President)")
