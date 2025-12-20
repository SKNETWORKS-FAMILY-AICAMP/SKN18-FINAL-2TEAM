# Generated manually - Migrate pinned data to favorite

from django.db import migrations


def migrate_pinned_to_favorite(apps, schema_editor):
    """Copy all pinned='Y' data to favorite='Y'"""
    Chat = apps.get_model('chat', 'Chat')
    updated_count = Chat.objects.filter(pinned='Y').update(favorite='Y')
    print(f"Migrated {updated_count} chats from pinned to favorite")


def reverse_migration(apps, schema_editor):
    """Reverse: Clear favorite field"""
    Chat = apps.get_model('chat', 'Chat')
    Chat.objects.filter(favorite='Y').update(favorite='N')
    print("Reversed migration: favorite data cleared")


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0003_chat_favorite'),
    ]

    operations = [
        migrations.RunPython(migrate_pinned_to_favorite, reverse_migration),
    ]
