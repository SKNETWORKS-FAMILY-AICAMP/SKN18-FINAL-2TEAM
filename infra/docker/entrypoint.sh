#!/bin/bash
set -e

# ========================================
# Parameter Store에서 설정값 읽기 (PostgreSQL, RabbitMQ)
# ========================================
echo "Loading configuration from Parameter Store..."

# AWS 리전 확인 (EC2 메타데이터에서 가져오기)
AWS_REGION="${AWS_REGION:-$(curl -s --max-time 5 http://169.254.169.254/latest/meta-data/placement/region 2>/dev/null || echo 'ap-northeast-2')}"

# CloudFormation 스택 이름 (환경 변수 또는 기본값)
STACK_NAME="${STACK_NAME:-skn18-final-infra}"

# AWS CLI가 설치되어 있고 IAM Role이 있는지 확인
if command -v aws &> /dev/null; then
  echo "AWS CLI found. Fetching configuration from Parameter Store..."
  
  # CloudFormation에서 PostgreSQL EC2 IP 가져오기
  POSTGRES_HOST=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$AWS_REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`PublicIp`].OutputValue' \
    --output text 2>/dev/null || echo "")
  
  # CloudFormation에서 RabbitMQ EC2 IP 가져오기
  RABBITMQ_HOST=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$AWS_REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`RabbitMQPublicIp`].OutputValue' \
    --output text 2>/dev/null || echo "")
  
  # Parameter Store에서 PostgreSQL 설정 가져오기
  if [ -z "$POSTGRES_DB" ]; then
    POSTGRES_DB=$(aws ssm get-parameter \
      --name /skn18/postgres-db-name \
      --region "$AWS_REGION" \
      --query 'Parameter.Value' \
      --output text 2>/dev/null || echo "")
  fi
  
  if [ -z "$POSTGRES_USER" ]; then
    POSTGRES_USER=$(aws ssm get-parameter \
      --name /skn18/postgres-user \
      --region "$AWS_REGION" \
      --query 'Parameter.Value' \
      --output text 2>/dev/null || echo "")
  fi
  
  if [ -z "$POSTGRES_PASSWORD" ]; then
    POSTGRES_PASSWORD=$(aws ssm get-parameter \
      --name /skn18/postgres-password \
      --with-decryption \
      --region "$AWS_REGION" \
      --query 'Parameter.Value' \
      --output text 2>/dev/null || echo "")
  fi
  
  if [ -z "$POSTGRES_PORT" ]; then
    POSTGRES_PORT=$(aws ssm get-parameter \
      --name /skn18/postgres-port \
      --region "$AWS_REGION" \
      --query 'Parameter.Value' \
      --output text 2>/dev/null || echo "5432")
  fi
  
  # Parameter Store에서 RabbitMQ 설정 가져오기
  if [ -z "$RABBITMQ_USER" ]; then
    RABBITMQ_USER=$(aws ssm get-parameter \
      --name /skn18/rabbitmq-user \
      --region "$AWS_REGION" \
      --query 'Parameter.Value' \
      --output text 2>/dev/null || echo "guest")
  fi
  
  if [ -z "$RABBITMQ_PASSWORD" ]; then
    RABBITMQ_PASSWORD=$(aws ssm get-parameter \
      --name /skn18/rabbitmq-password \
      --with-decryption \
      --region "$AWS_REGION" \
      --query 'Parameter.Value' \
      --output text 2>/dev/null || echo "")
  fi
  
  # 환경 변수로 export (이미 설정된 경우 덮어쓰지 않음)
  [ -n "$POSTGRES_HOST" ] && export POSTGRES_HOST
  [ -n "$POSTGRES_DB" ] && export POSTGRES_DB
  [ -n "$POSTGRES_USER" ] && export POSTGRES_USER
  [ -n "$POSTGRES_PASSWORD" ] && export POSTGRES_PASSWORD
  [ -n "$POSTGRES_PORT" ] && export POSTGRES_PORT
  [ -n "$RABBITMQ_HOST" ] && export RABBITMQ_HOST
  [ -n "$RABBITMQ_USER" ] && export RABBITMQ_USER
  [ -n "$RABBITMQ_PASSWORD" ] && export RABBITMQ_PASSWORD
  
  echo "✓ Configuration loaded from Parameter Store"
  echo "  POSTGRES_HOST: ${POSTGRES_HOST:-(not set)}"
  echo "  RABBITMQ_HOST: ${RABBITMQ_HOST:-(not set)}"
else
  echo "⚠ AWS CLI not found. Using environment variables from .env file or container environment."
fi

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

