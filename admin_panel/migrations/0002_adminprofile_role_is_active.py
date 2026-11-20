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
            sql="""
                UPDATE admin_panel_adminprofile ap
                SET role = CASE WHEN au.is_superuser THEN NULL ELSE 'member' END,
                    is_active = ap.is_admin
                FROM auth_user au
                WHERE au.id = ap.user_id;
            """,
            reverse_sql="UPDATE admin_panel_adminprofile SET role = NULL;",
        ),
        migrations.RemoveField(
            model_name="adminprofile",
            name="is_admin",
        ),
    ]
