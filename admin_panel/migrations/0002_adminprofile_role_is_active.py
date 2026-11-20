from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("admin_panel", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="adminprofile",
            name="role",
            field=models.CharField(
                blank=True,
                choices=[("chairman", "Chairman"), ("member", "Member")],
                max_length=10,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="adminprofile",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
        migrations.RunSQL(
            sql="UPDATE admin_panel_adminprofile SET role = 'member', is_active = is_admin;",
            reverse_sql="UPDATE admin_panel_adminprofile SET role = NULL;",
        ),
        migrations.RemoveField(
            model_name="adminprofile",
            name="is_admin",
        ),
    ]
