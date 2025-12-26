#!/bin/bash
# EC2에서 PostgreSQL Docker 컨테이너를 수동으로 시작하는 스크립트
# EC2에 SSH 접속한 후 실행

set -e

echo "=========================================="
echo "  PostgreSQL Docker Container Setup"
echo "=========================================="
echo ""

# 리전 확인
REGION=$(curl -s --max-time 2 http://169.254.169.254/latest/meta-data/placement/region 2>/dev/null || echo "")
if [ -z "$REGION" ]; then
    REGION="ap-northeast-2"
    echo "⚠️  Could not retrieve region from metadata, using default: $REGION"
else
    echo "Region: $REGION"
fi
echo ""

# 1. Docker 서비스 확인 및 시작
echo "1. Checking Docker service..."
if ! systemctl is-active --quiet docker; then
    echo "   Starting Docker service..."
    sudo systemctl start docker
    sudo systemctl enable docker
    echo "   ✓ Docker service started"
else
    echo "   ✓ Docker service is running"
fi

# 2. Parameter Store에서 연결 정보 가져오기
echo ""
echo "2. Retrieving configuration from Parameter Store..."

# AWS CLI 자격 증명 확인
if ! aws sts get-caller-identity --region "$REGION" >/dev/null 2>&1; then
    echo "   ⚠️  WARNING: AWS CLI credentials not configured or IAM role not attached"
    echo "   Using default values"
    POSTGRES_PASSWORD="s18f2t!@#"
    POSTGRES_DB="sknfinaldb"
    POSTGRES_USER="helixops"
    POSTGRES_PORT="5432"
else
    echo "   ✓ AWS credentials verified"
    
    POSTGRES_PASSWORD=$(aws ssm get-parameter --name /skn18/postgres-password --with-decryption --region "$REGION" --query 'Parameter.Value' --output text 2>&1)
    if [ $? -ne 0 ] || [ -z "$POSTGRES_PASSWORD" ] || [[ "$POSTGRES_PASSWORD" == *"error"* ]] || [[ "$POSTGRES_PASSWORD" == *"Error"* ]]; then
        echo "   ⚠️  WARNING: Failed to retrieve PostgreSQL password from Parameter Store"
        echo "   Error details: $POSTGRES_PASSWORD"
        echo "   Using fallback password for debugging"
        POSTGRES_PASSWORD="s18f2t!@#"
    else
        echo "   ✓ PostgreSQL password retrieved"
    fi
    
    POSTGRES_DB=$(aws ssm get-parameter --name /skn18/postgres-db-name --region "$REGION" --query 'Parameter.Value' --output text 2>/dev/null || echo "sknfinaldb")
    POSTGRES_USER=$(aws ssm get-parameter --name /skn18/postgres-user --region "$REGION" --query 'Parameter.Value' --output text 2>/dev/null || echo "helixops")
    POSTGRES_PORT=$(aws ssm get-parameter --name /skn18/postgres-port --region "$REGION" --query 'Parameter.Value' --output text 2>/dev/null || echo "5432")
fi

echo "   Database: $POSTGRES_DB"
echo "   User: $POSTGRES_USER"
echo "   Port: $POSTGRES_PORT"
echo ""

# 3. PostgreSQL 데이터 디렉토리 준비
echo "3. Preparing PostgreSQL data directory..."
mkdir -p /var/lib/postgresql
chown ec2-user:ec2-user /var/lib/postgresql
echo "   ✓ Data directory prepared"
echo ""

# 4. init.sql 파일 확인
echo "4. Checking init.sql file..."
if [ ! -f /home/ec2-user/init.sql ]; then
    echo "   ⚠️  WARNING: /home/ec2-user/init.sql not found"
    echo "   Creating empty init.sql file..."
    touch /home/ec2-user/init.sql
    chown ec2-user:ec2-user /home/ec2-user/init.sql
fi
echo "   ✓ init.sql file ready"
echo ""

# 5. 기존 컨테이너 정리
echo "5. Cleaning up existing containers..."
docker stop pg-db-final 2>/dev/null || true
docker rm -f pg-db-final 2>/dev/null || true
echo "   ✓ Existing containers cleaned up"
echo ""

# 6. Docker 컨테이너 실행
echo "6. Starting PostgreSQL Docker container..."
echo "   Configuration:"
echo "     Database: $POSTGRES_DB"
echo "     User: $POSTGRES_USER"
echo "     Port: $POSTGRES_PORT"
echo ""

# init.sql 파일 확인 (없으면 빈 파일 생성)
if [ ! -f /home/ec2-user/init.sql ]; then
    touch /home/ec2-user/init.sql
    chown ec2-user:ec2-user /home/ec2-user/init.sql
fi

docker run -d \
  --name pg-db-final \
  -e POSTGRES_DB=$POSTGRES_DB \
  -e POSTGRES_USER=$POSTGRES_USER \
  -e POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
  -p $POSTGRES_PORT:5432 \
  -v /var/lib/postgresql:/var/lib/postgresql \
  -v /home/ec2-user/init.sql:/docker-entrypoint-initdb.d/init.sql \
  --restart unless-stopped \
  --health-cmd "pg_isready -d $POSTGRES_DB -U $POSTGRES_USER" \
  --health-interval=10s \
  --health-timeout=5s \
  --health-retries=5 \
  --health-start-period=10s \
  pgvector/pgvector:pg18

DOCKER_EXIT_CODE=$?

if [ $DOCKER_EXIT_CODE -eq 0 ]; then
    echo "   ✓ Container started successfully"
else
    echo "   ✗ Failed to start container (exit code: $DOCKER_EXIT_CODE)"
    echo "   Checking for errors..."
    docker logs pg-db-final 2>&1 | tail -20 || true
    exit 1
fi

echo ""

# 7. 컨테이너 상태 확인
echo "7. Checking container status..."
sleep 5
docker ps | grep pg-db-final

echo ""
echo "8. Container logs (last 20 lines):"
docker logs --tail 20 pg-db-final

echo ""
echo "9. Health check status:"
docker inspect pg-db-final --format='{{.State.Health.Status}}' 2>/dev/null || echo "Health check not available yet"

echo ""
echo "=========================================="
echo "✓ PostgreSQL container setup completed!"
echo "=========================================="
echo ""
echo "To check container status:"
echo "  docker ps | grep pg-db-final"
echo ""
echo "To view logs:"
echo "  docker logs -f pg-db-final"
echo ""
echo "To test PostgreSQL connection:"
echo "  docker exec -it pg-db-final psql -U $POSTGRES_USER -d $POSTGRES_DB -c \"SELECT version();\""

