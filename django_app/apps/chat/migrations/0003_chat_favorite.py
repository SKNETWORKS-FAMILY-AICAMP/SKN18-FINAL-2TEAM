# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0002_remove_papergraph_updated_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='chat',
            name='favorite',
            field=models.CharField(db_column='favorite', default='N', max_length=1),
        ),
    ]
