# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0008_conversationmemory'),
    ]

    operations = [
        migrations.AddField(
            model_name='chatmessage',
            name='case_type',
            field=models.CharField(
                blank=True,
                db_column='case_type',
                help_text='LangGraph에서 분류한 질의 타입 (NO_RELATION, BIO_Q, SIMULATION_Q, PROTOCOL_Q, INFERENCE_Q, USER_INFO)',
                max_length=50,
                null=True
            ),
        ),
    ]

