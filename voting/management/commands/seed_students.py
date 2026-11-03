import csv

from django.core.management.base import BaseCommand, CommandError

from voting.csv_import import import_students


class Command(BaseCommand):
    help = (
        "Bulk-import students from a CSV file (columns: first_name,last_name,matric_number,level). "
        "Existing students are matched by matric_number and have their name/level updated; "
        "new matric numbers create new students."
    )

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str)

    def handle(self, *args, **options):
        csv_path = options["csv_path"]
        try:
            with open(csv_path, newline="", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)
                result = import_students(enumerate(reader, start=2))
        except FileNotFoundError:
            raise CommandError(f"CSV file not found: {csv_path}")
        for row_number, reason in result["skipped"]:
            self.stderr.write(f"Row {row_number}: {reason} — skipped.")
        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {result['created']} new student(s), "
                f"updated {result['updated']} existing student(s), "
                f"skipped {len(result['skipped'])} row(s)."
            )
        )
