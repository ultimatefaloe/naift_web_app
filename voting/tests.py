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

    def test_matric_number_accepts_varying_digit_group_widths(self):
        student = Student(
            first_name="Jane", last_name="Doe", matric_number="2022/12/9CF", level="300"
        )
        student.full_clean()
