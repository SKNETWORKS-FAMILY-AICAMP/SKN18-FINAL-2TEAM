from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Feedback",
            fields=[
                ("feedback_sid", models.AutoField(db_column="feedback_sid", primary_key=True, serialize=False)),
                ("category", models.CharField(choices=[("G", "일반"), ("B", "버그 리포트"), ("F", "기능 제안"), ("I", "개선 사항")], db_column="category", max_length=1)),
                ("feedback_content", models.TextField(db_column="feedback_content")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_column="created_at")),
                ("created_id", models.CharField(db_column="created_id", max_length=60)),
                ("updated_at", models.DateTimeField(auto_now=True, db_column="updated_at")),
                ("updated_id", models.CharField(db_column="updated_id", max_length=60)),
            ],
            options={
                "verbose_name": "피드백",
                "verbose_name_plural": "피드백 목록",
                "db_table": "t_feedback",
                "ordering": ["-created_at"],
            },
        ),
    ]
