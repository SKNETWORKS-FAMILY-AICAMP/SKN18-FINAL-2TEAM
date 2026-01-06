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
  # 1. PostgreSQL EC2 IP 가져오기
  # 우선순위: 환경 변수 > CloudFormation > Parameter Store
  # ========================================
  if [ -z "$POSTGRES_HOST" ]; then
    # CloudFormation에서 PostgreSQL EC2 IP 가져오기
    # 메인 스택의 PublicIp Output (CoreInfraStack에서 전달됨)
    POSTGRES_HOST=$(aws cloudformation describe-stacks \
      --stack-name "$STACK_NAME" \
      --region "$AWS_REGION" \
      --query 'Stacks[0].Outputs[?OutputKey==`PublicIp`].OutputValue' \
      --output text 2>/dev/null || echo "")
    
    # CloudFormation에서 가져오지 못한 경우, Parameter Store에서 직접 읽기 시도
    if [ -z "$POSTGRES_HOST" ] || [ "$POSTGRES_HOST" = "None" ]; then
      echo "⚠ Could not get POSTGRES_HOST from CloudFormation, trying Parameter Store..."
      POSTGRES_HOST=$(aws ssm get-parameter \
        --name /skn18/postgres-host \
        --region "$AWS_REGION" \
        --query 'Parameter.Value' \
        --output text 2>/dev/null || echo "")
    fi
  else
    echo "✓ Using POSTGRES_HOST from environment variable: $POSTGRES_HOST"
  fi
  
  # ========================================
  # 2. RabbitMQ EC2 IP 가져오기
  # 우선순위: 환경 변수 > CloudFormation > Parameter Store
  # ========================================
  if [ -z "$RABBITMQ_HOST" ]; then
    # CloudFormation에서 RabbitMQ EC2 IP 가져오기
    # 메인 스택의 RabbitMQPublicIp Output (RabbitMQInfraStack에서 전달됨)
    RABBITMQ_HOST=$(aws cloudformation describe-stacks \
      --stack-name "$STACK_NAME" \
      --region "$AWS_REGION" \
      --query 'Stacks[0].Outputs[?OutputKey==`RabbitMQPublicIp`].OutputValue' \
      --output text 2>/dev/null || echo "")
    
    # CloudFormation에서 가져오지 못한 경우, Parameter Store에서 직접 읽기 시도
    if [ -z "$RABBITMQ_HOST" ] || [ "$RABBITMQ_HOST" = "None" ]; then
      echo "⚠ Could not get RABBITMQ_HOST from CloudFormation, trying Parameter Store..."
      RABBITMQ_HOST=$(aws ssm get-parameter \
        --name /skn18/rabbitmq-host \
        --region "$AWS_REGION" \
        --query 'Parameter.Value' \
        --output text 2>/dev/null || echo "")
    fi
  else
    echo "✓ Using RABBITMQ_HOST from environment variable: $RABBITMQ_HOST"
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
  # 5. Neo4j 설정 가져오기 (환경 변수 → Parameter Store → CloudFormation 순서)
  # ========================================
  if [ -z "$NEO4J_BOLT_HOST" ]; then
    # 1순위: Parameter Store에서 가져오기 (이미 등록된 /skn18/neo4j-host 사용)
    NEO4J_BOLT_HOST=$(aws ssm get-parameter \
      --name /skn18/neo4j-host \
      --region "$AWS_REGION" \
      --query 'Parameter.Value' \
      --output text 2>/dev/null || echo "")
    
    # 2순위: Parameter Store에서 가져오지 못한 경우, CloudFormation Output에서 가져오기
    if [ -z "$NEO4J_BOLT_HOST" ] || [ "$NEO4J_BOLT_HOST" = "None" ]; then
      echo "⚠ Could not get NEO4J_BOLT_HOST from Parameter Store, trying CloudFormation..."
      NEO4J_BOLT_HOST=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$AWS_REGION" \
        --query 'Stacks[0].Outputs[?OutputKey==`Neo4jPublicIp`].OutputValue' \
        --output text 2>/dev/null || echo "")
      if [ -n "$NEO4J_BOLT_HOST" ] && [ "$NEO4J_BOLT_HOST" != "None" ]; then
        echo "✓ Using NEO4J_BOLT_HOST from CloudFormation: $NEO4J_BOLT_HOST"
      else
        echo "⚠ NEO4J_BOLT_HOST could not be retrieved from Parameter Store or CloudFormation"
      fi
    else
      echo "✓ Using NEO4J_BOLT_HOST from Parameter Store: $NEO4J_BOLT_HOST"
    fi
  else
    echo "✓ Using NEO4J_BOLT_HOST from environment variable: $NEO4J_BOLT_HOST"
  fi
  
  if [ -z "$NEO4J_BOLT_PORT" ]; then
    NEO4J_BOLT_PORT=$(aws ssm get-parameter \
      --name /skn18/neo4j-bolt-port \
      --region "$AWS_REGION" \
      --query 'Parameter.Value' \
      --output text 2>/dev/null || echo "7687")
  fi
  
  if [ -z "$NEO4J_USER" ] && [ -z "$NEO4J_USERNAME" ]; then
    NEO4J_USER=$(aws ssm get-parameter \
      --name /skn18/neo4j-user \
      --region "$AWS_REGION" \
      --query 'Parameter.Value' \
      --output text 2>/dev/null || echo "neo4j")
    NEO4J_USERNAME="$NEO4J_USER"  # NEO4J_USERNAME도 동일하게 설정
  elif [ -z "$NEO4J_USERNAME" ]; then
    NEO4J_USERNAME="$NEO4J_USER"
  elif [ -z "$NEO4J_USER" ]; then
    NEO4J_USER="$NEO4J_USERNAME"
  fi
  
  if [ -z "$NEO4J_PASSWORD" ]; then
    NEO4J_PASSWORD=$(aws ssm get-parameter \
      --name /skn18/neo4j-password \
      --with-decryption \
      --region "$AWS_REGION" \
      --query 'Parameter.Value' \
      --output text 2>/dev/null || echo "")
  fi
  
  # NEO4J_URI 구성 (bolt://host:port 형식)
  if [ -n "$NEO4J_BOLT_HOST" ] && [ -n "$NEO4J_BOLT_PORT" ]; then
    NEO4J_URI="bolt://${NEO4J_BOLT_HOST}:${NEO4J_BOLT_PORT}"
  fi
  
  # ========================================
  # 6. 기타 Django 설정도 Parameter Store에서 가져오기
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
  
  # TAVILY_API_KEY 가져오기
  if [ -z "$TAVILY_API_KEY" ]; then
    TAVILY_API_KEY=$(aws ssm get-parameter \
      --name /skn18/tavily-api-key \
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
  [ -n "$NEO4J_BOLT_HOST" ] && export NEO4J_BOLT_HOST
  [ -n "$NEO4J_BOLT_PORT" ] && export NEO4J_BOLT_PORT
  [ -n "$NEO4J_USER" ] && export NEO4J_USER
  [ -n "$NEO4J_USERNAME" ] && export NEO4J_USERNAME
  [ -n "$NEO4J_PASSWORD" ] && export NEO4J_PASSWORD
  [ -n "$NEO4J_URI" ] && export NEO4J_URI
  [ -n "$DJANGO_SECRET_KEY" ] && export DJANGO_SECRET_KEY
  [ -n "$OPENAI_API_KEY" ] && export OPENAI_API_KEY
  [ -n "$TAVILY_API_KEY" ] && export TAVILY_API_KEY
  
  echo "✓ Configuration loaded from Parameter Store"
  echo "  POSTGRES_HOST: ${POSTGRES_HOST:-(not set)}"
  echo "  RABBITMQ_HOST: ${RABBITMQ_HOST:-(not set)}"
  echo "  NEO4J_BOLT_HOST: ${NEO4J_BOLT_HOST:-(not set)}"
  echo "  NEO4J_BOLT_PORT: ${NEO4J_BOLT_PORT:-(not set)}"
  echo "  NEO4J_USER: ${NEO4J_USER:-(not set)}"
  echo "  NEO4J_URI: ${NEO4J_URI:-(not set)}"
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

# ========================================
# CrossEncoder 모델 사전 다운로드 (첫 실행 시 지연 방지)
# ========================================
echo "Checking CrossEncoder model..."
if [ ! -f "/app/models/.cross-encoder-ready" ]; then
  echo "CrossEncoder model not found. Pre-downloading..."
  python -c "
import os
os.makedirs('/app/models', exist_ok=True)
os.environ['SENTENCE_TRANSFORMERS_HOME'] = '/app/models'
os.environ['HF_HOME'] = '/app/models'
os.environ['HF_HUB_DOWNLOAD_TIMEOUT'] = '180'

try:
    from sentence_transformers import CrossEncoder
    print('[CrossEncoder] Downloading model: cross-encoder/ms-marco-MiniLM-L-6-v2')
    model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2', cache_folder='/app/models')
    print('[CrossEncoder] Model downloaded successfully')
    # 다운로드 완료 표시
    with open('/app/models/.cross-encoder-ready', 'w') as f:
        f.write('ready')
    print('[CrossEncoder] Model pre-download complete')
except Exception as e:
    print(f'[CrossEncoder] Warning: Model pre-download failed: {e}')
    print('[CrossEncoder] Model will be downloaded on first use (may cause delay)')
" || echo "Warning: Model pre-download failed (will download on first use)"
else
  echo "CrossEncoder model already available (skipping download)"
fi

# CMD로 전달된 명령어 실행
exec "$@"

