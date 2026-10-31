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
