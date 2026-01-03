from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notes", "0003_reset_note_sequence"),
    ]

    operations = [
        migrations.AddField(
            model_name="note",
            name="content_preview",
            field=models.CharField(
                blank=True,
                db_column="content_preview",
                help_text="HTML 태그가 제거된 텍스트 미리보기 (최대 200자)",
                max_length=200,
                null=True,
            ),
        ),
    ]

