from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("schedule", "0007_schedulerecurrence_scheduleexception"),
    ]

    operations = [
        migrations.AddField(
            model_name="schedule",
            name="calendar",
            field=models.ForeignKey(
                blank=True,
                db_column="calendar_sid",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="schedules",
                to="schedule.usercalendar",
            ),
        ),
        migrations.AddField(
            model_name="usercalendar",
            name="source_type",
            field=models.CharField(
                choices=[("local", "로컬"), ("google", "Google")],
                db_column="source_type",
                default="local",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="usercalendar",
            name="external_id",
            field=models.CharField(
                blank=True,
                db_column="external_id",
                max_length=255,
                null=True,
            ),
        ),
    ]
