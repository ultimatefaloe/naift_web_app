from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from .models import Student


def import_students(reader, start=2):
    """Create-or-update Student rows from `reader` (e.g. a csv.DictReader),
    each row a dict with first_name/last_name/matric_number/level keys.
    `start` is the row number reported for the first row (default 2, matching
    a CSV's header being row 1) — callers pass the reader directly, they do
    NOT pre-enumerate it themselves. Existing students are matched by
    matric_number; only first_name/last_name/level are updated on an existing
    match — matric_number itself is never changed by this importer, since
    it's the match key.

    Returns {"created": int, "updated": int, "skipped": [(row_number, reason), ...]}.
    """
    created_count = 0
    updated_count = 0
    skipped = []
    for row_number, row in enumerate(reader, start=start):
        try:
            first_name = row["first_name"].strip()
            last_name = row["last_name"].strip()
            matric_number = row["matric_number"].strip()
            level = row["level"].strip()
        except (KeyError, AttributeError) as exc:
            skipped.append((row_number, f"missing or blank column ({exc})"))
            continue

        candidate = Student(
            first_name=first_name, last_name=last_name, matric_number=matric_number, level=level
        )
        try:
            candidate.clean_fields()
        except ValidationError as exc:
            skipped.append((row_number, exc.messages[0]))
            continue

        try:
            with transaction.atomic():
                existing = Student.objects.filter(matric_number=matric_number).first()
                if existing is not None:
                    existing.first_name = first_name
                    existing.last_name = last_name
                    existing.level = level
                    existing.save(update_fields=["first_name", "last_name", "level"])
                    updated_count += 1
                else:
                    Student.objects.create(
                        first_name=first_name, last_name=last_name, matric_number=matric_number, level=level
                    )
                    created_count += 1
        except IntegrityError:
            skipped.append((row_number, "a student with this matric number already exists"))
            continue
    return {"created": created_count, "updated": updated_count, "skipped": skipped}
