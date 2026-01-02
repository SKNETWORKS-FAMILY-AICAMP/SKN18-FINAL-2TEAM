from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notes", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="note",
            name="is_public",
            field=models.BooleanField(db_column="is_public", default=False),
        ),
    ]
