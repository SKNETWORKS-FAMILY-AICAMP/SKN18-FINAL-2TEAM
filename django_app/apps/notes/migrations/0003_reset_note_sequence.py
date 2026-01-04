# Generated migration to reset PostgreSQL sequence

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('notes', '0002_note_is_public'),
    ]

    operations = [
        migrations.RunSQL(
            # 시퀀스를 현재 테이블의 최대값으로 재설정
            sql="""
                SELECT setval(
                    pg_get_serial_sequence('t_note', 'note_sid'),
                    COALESCE((SELECT MAX(note_sid) FROM t_note), 1),
                    true
                );
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]

