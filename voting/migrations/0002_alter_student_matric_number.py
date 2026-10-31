import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('voting', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='student',
            name='matric_number',
            field=models.CharField(max_length=30, unique=True, validators=[django.core.validators.RegexValidator(message='Matric number must be in the format YYYY/<digits>/<digits>CF (e.g. 2022/1/90976CF).', regex='^\\d{4}/\\d+/\\d+CF$')]),
        ),
    ]
