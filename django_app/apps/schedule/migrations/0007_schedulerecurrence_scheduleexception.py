# Generated manually for recurring schedules
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("schedule", "0006_googlesyncedevent"),
    ]

    operations = [
        migrations.CreateModel(
            name="ScheduleRecurrence",
            fields=[
                (
                    "schedule",
                    models.OneToOneField(
                        db_column="schedule_sid",
                        on_delete=django.db.models.deletion.CASCADE,
                        primary_key=True,
                        related_name="recurrence",
                        serialize=False,
                        to="schedule.schedule",
                    ),
                ),
                (
                    "freq",
                    models.CharField(
                        choices=[
                            ("DAILY", "매일"),
                            ("WEEKLY", "매주"),
                            ("MONTHLY", "매월"),
                            ("YEARLY", "매년"),
                        ],
                        db_column="freq",
                        max_length=20,
                    ),
                ),
                (
                    "interval",
                    models.PositiveIntegerField(db_column="interval", default=1),
                ),
                (
                    "week_days",
                    models.JSONField(blank=True, db_column="week_days", default=list),
                ),
                (
                    "month_days",
                    models.JSONField(blank=True, db_column="month_days", default=list),
                ),
                ("count", models.PositiveIntegerField(blank=True, db_column="count", null=True)),
                ("until", models.DateTimeField(blank=True, db_column="until", null=True)),
                (
                    "timezone",
                    models.CharField(db_column="timezone", default="Asia/Seoul", max_length=64),
                ),
                (
                    "metadata",
                    models.JSONField(blank=True, db_column="metadata", default=dict),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, db_column="created_at"),
                ),
                ("updated_at", models.DateTimeField(auto_now=True, db_column="updated_at")),
            ],
            options={
                "db_table": "t_schedule_recurrence",
            },
        ),
        migrations.CreateModel(
            name="ScheduleException",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "exception_date",
                    models.DateField(db_column="exception_date"),
                ),
                (
                    "note",
                    models.CharField(blank=True, db_column="note", max_length=255),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, db_column="created_at"),
                ),
                (
                    "recurrence",
                    models.ForeignKey(
                        db_column="recurrence_sid",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="exceptions",
                        to="schedule.schedulerecurrence",
                    ),
                ),
            ],
            options={
                "db_table": "t_schedule_exception",
            },
        ),
        migrations.AlterUniqueTogether(
            name="scheduleexception",
            unique_together={("recurrence", "exception_date")},
        ),
    ]
