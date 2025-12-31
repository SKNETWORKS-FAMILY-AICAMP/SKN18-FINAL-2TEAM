# Generated manually - Add new guide fields and help_text to ExperimentToolOption
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('experiments', '0002_load_default_tools'),
    ]

    operations = [
        # Add new guide fields to ExperimentTool
        migrations.AddField(
            model_name='experimenttool',
            name='guide_prerequisites',
            field=models.TextField(blank=True, db_column='guide_prerequisites', help_text='JSON array of prerequisites', null=True),
        ),
        migrations.AddField(
            model_name='experimenttool',
            name='guide_inputs',
            field=models.TextField(blank=True, db_column='guide_inputs', help_text='JSON array of inputs', null=True),
        ),
        migrations.AddField(
            model_name='experimenttool',
            name='guide_outputs',
            field=models.TextField(blank=True, db_column='guide_outputs', help_text='JSON array of outputs', null=True),
        ),
        migrations.AddField(
            model_name='experimenttool',
            name='guide_limitations',
            field=models.TextField(blank=True, db_column='guide_limitations', help_text='JSON array of limitations', null=True),
        ),
        migrations.AddField(
            model_name='experimenttool',
            name='guide_recommended_workflow',
            field=models.TextField(blank=True, db_column='guide_recommended_workflow', help_text='JSON array of recommended workflow steps', null=True),
        ),
        # Add help_text field to ExperimentToolOption
        migrations.AddField(
            model_name='experimenttooloption',
            name='help_text',
            field=models.TextField(blank=True, db_column='help_text', help_text='Help text for tooltip/description', null=True),
        ),
        # Update field_type choices to include textarea
        migrations.AlterField(
            model_name='experimenttooloption',
            name='field_type',
            field=models.CharField(
                choices=[
                    ('number', 'Number'),
                    ('select', 'Select'),
                    ('checkbox', 'Checkbox'),
                    ('text', 'Text'),
                    ('textarea', 'Textarea'),
                ],
                db_column='field_type',
                max_length=50
            ),
        ),
    ]

