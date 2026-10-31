import csv

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError

from voting.models import Student


class Command(BaseCommand):
    help = (
        "Bulk-import students from a CSV file (columns: first_name,last_name,matric_number,level). "
        "Matches existing students by matric_number — re-running with corrected data does NOT "
        "update existing rows, it only adds new ones."
    )

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str)

    def handle(self, *args, **options):
        csv_path = options["csv_path"]
        created_count = 0
        skipped_count = 0
        try:
            with open(csv_path, newline="", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)
                for row_number, row in enumerate(reader, start=2):
                    try:
                        first_name = row["first_name"].strip()
                        last_name = row["last_name"].strip()
                        matric_number = row["matric_number"].strip()
                        level = row["level"].strip()
                    except (KeyError, AttributeError) as exc:
                        self.stderr.write(f"Row {row_number}: missing or blank column ({exc}) — skipped.")
                        skipped_count += 1
                        continue

                    student = Student(
                        first_name=first_name,
                        last_name=last_name,
                        matric_number=matric_number,
                        level=level,
                    )
                    try:
                        student.clean_fields()
                    except ValidationError as exc:
                        self.stderr.write(f"Row {row_number}: {exc.messages[0]} — skipped.")
                        skipped_count += 1
                        continue

                    try:
                        _, created = Student.objects.get_or_create(
                            matric_number=matric_number,
                            defaults={
                                "first_name": first_name,
                                "last_name": last_name,
                                "level": level,
                            },
                        )
                    except IntegrityError as exc:
                        self.stderr.write(f"Row {row_number}: {exc} — skipped.")
                        skipped_count += 1
                        continue

                    if created:
                        created_count += 1
        except FileNotFoundError:
            raise CommandError(f"CSV file not found: {csv_path}")
        self.stdout.write(
            self.style.SUCCESS(f"Imported {created_count} new student(s), skipped {skipped_count} row(s).")
        )
