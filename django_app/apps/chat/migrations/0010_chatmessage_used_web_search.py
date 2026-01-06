# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0009_chatmessage_case_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='chatmessage',
            name='used_web_search',
            field=models.BooleanField(
                default=False,
                db_column='used_web_search',
                help_text='웹 검색을 사용했는지 여부 (RAG 실패 시 fallback)'
            ),
        ),
    ]

