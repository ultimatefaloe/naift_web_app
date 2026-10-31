import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('elections', '0003_contestant'),
        ('voting', '0002_alter_student_matric_number'),
    ]

    operations = [
        migrations.CreateModel(
            name='Vote',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('voted_at', models.DateTimeField(auto_now_add=True)),
                ('contestant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='votes', to='elections.contestant')),
                ('election', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='votes', to='elections.election')),
                ('position', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='votes', to='elections.position')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='votes', to='voting.student')),
            ],
            options={
                'unique_together': {('student', 'election', 'position')},
            },
        ),
    ]
