# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notes', '0004_note_content_preview'),
    ]

    operations = [
        migrations.AddField(
            model_name='notecomment',
            name='status',
            field=models.CharField(
                choices=[('E', '사용'), ('D', 'Disabled'), ('R', 'Removed')],
                db_column='status',
                default='E',
                max_length=1
            ),
        ),
    ]

