#!/bin/bash
set -e

# ========================================
# Parameter Store에서 설정값 읽기 (PostgreSQL, RabbitMQ)
# ========================================
echo "Loading configuration from Parameter Store..."

# AWS 리전 확인 (EC2 메타데이터에서 가져오기)
AWS_REGION="${AWS_REGION:-$(curl -s --max-time 5 http://169.254.169.254/latest/meta-data/placement/region 2>/dev/null || echo 'ap-northeast-2')}"

# CloudFormation 스택 이름 (환경 변수 또는 기본값)
# 메인 스택 이름 (중첩 스택 구조)
STACK_NAME="${STACK_NAME:-skn18-final-infra}"

# AWS CLI가 설치되어 있고 IAM Role이 있는지 확인
if command -v aws &> /dev/null; then
  echo "AWS CLI found. Fetching configuration from Parameter Store and CloudFormation..."
  
  # ========================================
  # 1. CloudFormation에서 PostgreSQL EC2 IP 가져오기
  # 메인 스택의 PublicIp Output (CoreInfraStack에서 전달됨)
  # ========================================
  POSTGRES_HOST=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$AWS_REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`PublicIp`].OutputValue' \
    --output text 2>/dev/null || echo "")
  
  # CloudFormation에서 가져오지 못한 경우, Parameter Store에서 직접 읽기 시도
  if [ -z "$POSTGRES_HOST" ]; then
    echo "⚠ Could not get POSTGRES_HOST from CloudFormation, trying Parameter Store..."
    POSTGRES_HOST=$(aws ssm get-parameter \
      --name /skn18/postgres-host \
      --region "$AWS_REGION" \
      --query 'Parameter.Value' \
      --output text 2>/dev/null || echo "")
  fi
  
  # ========================================
  # 2. CloudFormation에서 RabbitMQ EC2 IP 가져오기
  # 메인 스택의 RabbitMQPublicIp Output (RabbitMQInfraStack에서 전달됨)
  # ========================================
  RABBITMQ_HOST=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$AWS_REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`RabbitMQPublicIp`].OutputValue' \
    --output text 2>/dev/null || echo "")
  
  # CloudFormation에서 가져오지 못한 경우, Parameter Store에서 직접 읽기 시도
  if [ -z "$RABBITMQ_HOST" ]; then
    echo "⚠ Could not get RABBITMQ_HOST from CloudFormation, trying Parameter Store..."
    RABBITMQ_HOST=$(aws ssm get-parameter \
      --name /skn18/rabbitmq-host \
      --region "$AWS_REGION" \
      --query 'Parameter.Value' \
      --output text 2>/dev/null || echo "")
  fi
  
  # ========================================
  # 3. Parameter Store에서 PostgreSQL 설정 가져오기
  # ========================================
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
  
  # ========================================
  # 4. Parameter Store에서 RabbitMQ 설정 가져오기
  # ========================================
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
  
  if [ -z "$RABBITMQ_PORT" ]; then
    RABBITMQ_PORT=$(aws ssm get-parameter \
      --name /skn18/rabbitmq-port \
      --region "$AWS_REGION" \
      --query 'Parameter.Value' \
      --output text 2>/dev/null || echo "5672")
  fi
  
  # ========================================
  # 5. 기타 Django 설정도 Parameter Store에서 가져오기
  # ========================================
  if [ -z "$DJANGO_SECRET_KEY" ]; then
    DJANGO_SECRET_KEY=$(aws ssm get-parameter \
      --name /skn18/django-secret-key \
      --with-decryption \
      --region "$AWS_REGION" \
      --query 'Parameter.Value' \
      --output text 2>/dev/null || echo "")
  fi
  
  if [ -z "$OPENAI_API_KEY" ]; then
    OPENAI_API_KEY=$(aws ssm get-parameter \
      --name /skn18/openai-api-key \
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
  [ -n "$RABBITMQ_PORT" ] && export RABBITMQ_PORT
  [ -n "$DJANGO_SECRET_KEY" ] && export DJANGO_SECRET_KEY
  [ -n "$OPENAI_API_KEY" ] && export OPENAI_API_KEY
  
  echo "✓ Configuration loaded from Parameter Store"
  echo "  POSTGRES_HOST: ${POSTGRES_HOST:-(not set)}"
  echo "  RABBITMQ_HOST: ${RABBITMQ_HOST:-(not set)}"
  echo "  POSTGRES_DB: ${POSTGRES_DB:-(not set)}"
  echo "  POSTGRES_USER: ${POSTGRES_USER:-(not set)}"
else
  echo "⚠ AWS CLI not found. Using environment variables from container environment."
fi

# ========================================
# 필수 환경 변수 검증
# ========================================
if [ -z "$POSTGRES_HOST" ]; then
  echo "ERROR: POSTGRES_HOST is not set!"
  exit 1
fi

if [ -z "$POSTGRES_DB" ] || [ -z "$POSTGRES_USER" ] || [ -z "$POSTGRES_PASSWORD" ]; then
  echo "ERROR: PostgreSQL configuration is incomplete!"
  echo "  POSTGRES_DB: ${POSTGRES_DB:-(not set)}"
  echo "  POSTGRES_USER: ${POSTGRES_USER:-(not set)}"
  echo "  POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:+***}"
  exit 1
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

