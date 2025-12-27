#!/bin/bash
set -e

# 데이터베이스 연결 대기
echo "Waiting for database to be ready..."
until python -c "
import sys
import psycopg
from django.conf import settings
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

try:
    conn = psycopg.connect(
        dbname=settings.DATABASES['default']['NAME'],
        user=settings.DATABASES['default']['USER'],
        password=settings.DATABASES['default']['PASSWORD'],
        host=settings.DATABASES['default']['HOST'],
        port=settings.DATABASES['default']['PORT'],
        connect_timeout=5
    )
    conn.close()
    print('Database is ready!')
    sys.exit(0)
except Exception as e:
    print(f'Database not ready: {e}')
    sys.exit(1)
" 2>/dev/null; do
  echo "Database is unavailable - sleeping"
  sleep 2
done

echo "Database is ready - executing migrations..."

# Django 마이그레이션 실행 (에러 발생 시 종료)
cd /app/django_app
if ! python manage.py migrate --noinput; then
  echo "ERROR: Migration failed!"
  exit 1
fi

# collectstatic 실행 (실패해도 계속 진행)
python manage.py collectstatic --noinput || echo "Warning: collectstatic failed (may not be critical)"

echo "Migrations completed. Starting application..."

# CMD로 전달된 명령어 실행
exec "$@"

