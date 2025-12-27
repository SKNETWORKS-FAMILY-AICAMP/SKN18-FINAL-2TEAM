# EC2 SSH 접속 및 PostgreSQL 확인 가이드

이 문서는 CloudFormation으로 배포된 EC2 인스턴스에 SSH 접속하고, Docker로 실행 중인 PostgreSQL이 정상 동작하는지 확인하는 방법을 설명합니다.

## 목차

1. [EC2 SSH 접속](#1-ec2-ssh-접속)
2. [PostgreSQL 확인](#2-postgresql-확인)
3. [문제 해결](#3-문제-해결)

---

## 1. EC2 SSH 접속

### 1.1 사전 준비

#### EC2 Public IP 확인
```bash
# CloudFormation 스택 출력에서 Public IP 확인
cd infra/aws/cloudformation
aws cloudformation describe-stacks \
  --stack-name skn18-final-infra \
  --region ap-northeast-2 \
  --query 'Stacks[0].Outputs[?OutputKey==`PublicIp`].OutputValue' \
  --output text

# 또는 check-status.sh 사용
./check-status.sh
```

#### SSH Key 파일 확인
```bash
# Parameter Store에서 Key 이름 확인
aws ssm get-parameter \
  --name /skn18/key-name \
  --region ap-northeast-2 \
  --query 'Parameter.Value' \
  --output text

# 일반적으로 키 파일은 ~/.ssh/ 디렉토리에 있습니다
# 예: ~/.ssh/skn18-final-2team-key.pem
```

#### SSH Key 권한 설정
```bash
# SSH Key 파일 권한 설정 (필수!)
chmod 400 ~/.ssh/skn18-final-2team-key.pem
# 또는
chmod 400 ~/.ssh/<your-key-name>.pem
```

### 1.2 SSH 접속

#### 기본 SSH 접속
```bash
# Public IP를 변수로 저장 (위에서 확인한 IP 사용)
PUBLIC_IP=$(aws cloudformation describe-stacks \
  --stack-name skn18-final-infra \
  --region ap-northeast-2 \
  --query 'Stacks[0].Outputs[?OutputKey==`PublicIp`].OutputValue' \
  --output text)

# SSH 접속
ssh -i ~/.ssh/skn18-final-2team-key.pem ec2-user@$PUBLIC_IP

# 또는 직접 IP 입력
ssh -i ~/.ssh/skn18-final-2team-key.pem ec2-user@<PUBLIC_IP>
```

#### SSH 접속 예시
```bash
# 예시: Public IP가 43.202.53.52인 경우
ssh -i ~/.ssh/skn18-final-2team-key.pem ec2-user@43.202.53.52
```

#### SSH 접속 확인 사항
- ✅ 연결 성공 시 `ec2-user@ip-xxx-xxx-xxx-xxx` 프롬프트가 표시됩니다
- ✅ 연결 실패 시 Security Group 설정 확인 필요

---

## 2. PostgreSQL 확인

### 2.1 Docker 컨테이너 상태 확인

#### 컨테이너 실행 상태 확인
```bash
# EC2에 SSH 접속한 후
docker ps

# 예상 출력:
# CONTAINER ID   IMAGE                      STATUS         NAMES
# xxxxxxxxxxxx   pgvector/pgvector:pg18    Up X minutes   pg-db-final
```

#### 컨테이너 상세 정보 확인
```bash
# 컨테이너 상태 및 로그 확인
docker inspect pg-db-final

# 컨테이너 로그 확인
docker logs pg-db-final

# 실시간 로그 확인
docker logs -f pg-db-final
```

#### 컨테이너 Health Check 확인
```bash
# Health Check 상태 확인
docker inspect pg-db-final --format='{{.State.Health.Status}}'

# 예상 출력: healthy
```

### 2.2 PostgreSQL 연결 테스트

#### Parameter Store에서 연결 정보 확인
```bash
# 로컬에서 실행
cd infra/aws/cloudformation

# PostgreSQL 포트 확인
POSTGRES_PORT=$(aws ssm get-parameter \
  --name /skn18/postgres-port \
  --region ap-northeast-2 \
  --query 'Parameter.Value' \
  --output text)

# PostgreSQL 사용자 확인
POSTGRES_USER=$(aws ssm get-parameter \
  --name /skn18/postgres-user \
  --region ap-northeast-2 \
  --query 'Parameter.Value' \
  --output text)

# PostgreSQL 데이터베이스 이름 확인
POSTGRES_DB=$(aws ssm get-parameter \
  --name /skn18/postgres-db-name \
  --region ap-northeast-2 \
  --query 'Parameter.Value' \
  --output text)

# Public IP 확인
PUBLIC_IP=$(aws cloudformation describe-stacks \
  --stack-name skn18-final-infra \
  --region ap-northeast-2 \
  --query 'Stacks[0].Outputs[?OutputKey==`PublicIp`].OutputValue' \
  --output text)

echo "PostgreSQL 연결 정보:"
echo "  Host: $PUBLIC_IP"
echo "  Port: $POSTGRES_PORT"
echo "  User: $POSTGRES_USER"
echo "  Database: $POSTGRES_DB"
```

#### EC2 내부에서 PostgreSQL 연결 테스트
```bash
# EC2에 SSH 접속한 후

# PostgreSQL 비밀번호 확인 (Parameter Store에서)
POSTGRES_PASSWORD=$(aws ssm get-parameter \
  --name /skn18/postgres-password \
  --with-decryption \
  --region ap-northeast-2 \
  --query 'Parameter.Value' \
  --output text)

# Docker 컨테이너 내부에서 PostgreSQL 연결 테스트
docker exec -it pg-db-final psql -U postgres -d sknfinaldb -c "SELECT version();"

# 또는 환경 변수 사용
docker exec -it pg-db-final \
  psql -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT version();"
```

#### 로컬에서 PostgreSQL 연결 테스트

##### 방법 1: psql 직접 연결
```bash
# PostgreSQL 비밀번호 확인
POSTGRES_PASSWORD=$(aws ssm get-parameter \
  --name /skn18/postgres-password \
  --with-decryption \
  --region ap-northeast-2 \
  --query 'Parameter.Value' \
  --output text)

# Public IP 확인
PUBLIC_IP=$(aws cloudformation describe-stacks \
  --stack-name skn18-final-infra \
  --region ap-northeast-2 \
  --query 'Stacks[0].Outputs[?OutputKey==`PublicIp`].OutputValue' \
  --output text)

# PostgreSQL 포트 확인
POSTGRES_PORT=$(aws ssm get-parameter \
  --name /skn18/postgres-port \
  --region ap-northeast-2 \
  --query 'Parameter.Value' \
  --output text)

# PostgreSQL 사용자 확인
POSTGRES_USER=$(aws ssm get-parameter \
  --name /skn18/postgres-user \
  --region ap-northeast-2 \
  --query 'Parameter.Value' \
  --output text)

# PostgreSQL 데이터베이스 이름 확인
POSTGRES_DB=$(aws ssm get-parameter \
  --name /skn18/postgres-db-name \
  --region ap-northeast-2 \
  --query 'Parameter.Value' \
  --output text)

# psql 연결 (비밀번호 입력 필요)
PGPASSWORD=$POSTGRES_PASSWORD psql \
  -h $PUBLIC_IP \
  -p $POSTGRES_PORT \
  -U $POSTGRES_USER \
  -d $POSTGRES_DB \
  -c "SELECT version();"
```

##### 방법 2: psql 대화형 모드
```bash
# 위에서 확인한 정보로 연결
PGPASSWORD=$POSTGRES_PASSWORD psql \
  -h $PUBLIC_IP \
  -p $POSTGRES_PORT \
  -U $POSTGRES_USER \
  -d $POSTGRES_DB

# 연결 성공 시 PostgreSQL 프롬프트가 표시됩니다:
# sknfinaldb=#
```

##### 방법 3: 연결 문자열 사용
```bash
# CloudFormation 출력에서 연결 문자열 확인
aws cloudformation describe-stacks \
  --stack-name skn18-final-infra \
  --region ap-northeast-2 \
  --query 'Stacks[0].Outputs[?OutputKey==`ConnectionStringExample`].OutputValue' \
  --output text

# 출력 예시: psql postgresql://helixops:[PASSWORD]@43.202.53.52:5432/sknfinaldb
# [PASSWORD] 부분을 실제 비밀번호로 교체하여 사용
```

### 2.3 PostgreSQL 기능 확인

#### pgvector 확장 확인
```bash
# EC2에 SSH 접속한 후
docker exec -it pg-db-final \
  psql -U postgres -d sknfinaldb -c "CREATE EXTENSION IF NOT EXISTS vector;"

# pgvector 버전 확인
docker exec -it pg-db-final \
  psql -U postgres -d sknfinaldb -c "SELECT extversion FROM pg_extension WHERE extname = 'vector';"
```

#### 데이터베이스 목록 확인
```bash
docker exec -it pg-db-final \
  psql -U postgres -c "\l"
```

#### 테이블 목록 확인
```bash
docker exec -it pg-db-final \
  psql -U postgres -d sknfinaldb -c "\dt"
```

#### 연결 상태 확인
```bash
# 활성 연결 확인
docker exec -it pg-db-final \
  psql -U postgres -d sknfinaldb -c "SELECT count(*) FROM pg_stat_activity;"
```

---

## 3. 문제 해결

### 3.1 SSH 접속 실패

#### 문제: "Permission denied (publickey)"
**원인**: SSH Key 파일 권한 문제 또는 잘못된 Key 파일

**해결 방법**:
```bash
# 1. Key 파일 권한 확인 및 수정
chmod 400 ~/.ssh/skn18-final-2team-key.pem

# 2. Key 파일 경로 확인
ls -la ~/.ssh/skn18-final-2team-key.pem

# 3. Key 이름 확인 (Parameter Store와 일치하는지)
aws ssm get-parameter \
  --name /skn18/key-name \
  --region ap-northeast-2 \
  --query 'Parameter.Value' \
  --output text
```

#### 문제: "Connection timed out"
**원인**: Security Group 설정 문제 또는 잘못된 IP

**해결 방법**:
```bash
# 1. Security Group 확인
aws ec2 describe-security-groups \
  --region ap-northeast-2 \
  --filters "Name=tag:Name,Values=skn18-pgvector-sg" \
  --query 'SecurityGroups[0].IpPermissions'

# 2. 현재 IP 확인
curl ifconfig.me

# 3. Security Group에 현재 IP 추가 (필요 시)
# AWS 콘솔에서 Security Group 수정 또는 CloudFormation 템플릿 수정 후 재배포
```

### 3.2 PostgreSQL 연결 실패

#### 문제: Docker 컨테이너가 실행되지 않음
**확인 방법**:
```bash
# EC2에 SSH 접속한 후

# 1. 모든 컨테이너 확인 (실행 중 + 중지된 것 모두)
docker ps -a

# 2. pg-db-final 컨테이너 확인
docker ps -a | grep pg-db-final

# 3. Docker 서비스 상태 확인
sudo systemctl status docker

# 4. UserData 스크립트 실행 로그 확인
sudo cat /var/log/cloud-init-output.log | tail -100

# 5. UserData 실행 상태 확인
sudo cat /var/lib/cloud/instance/scripts/runcmd 2>/dev/null || echo "UserData 스크립트 없음"
```

**해결 방법**:

##### 방법 1: 자동 수정 스크립트 사용 (권장)

스크립트를 EC2로 복사하고 실행:

```bash
# 로컬에서 실행
# Public IP 확인
PUBLIC_IP=$(aws cloudformation describe-stacks \
  --stack-name skn18-final-infra \
  --region ap-northeast-2 \
  --query 'Stacks[0].Outputs[?OutputKey==`PublicIp`].OutputValue' \
  --output text)

# 또는 직접 IP 입력
# PUBLIC_IP="43.202.53.52"

# 스크립트를 EC2로 복사
scp -i ~/.ssh/skn18-final-2team-key.pem \
  infra/aws/cloudformation/shells/fix-postgres-container.sh \
  ec2-user@$PUBLIC_IP:~/

# EC2에 SSH 접속
ssh -i ~/.ssh/skn18-final-2team-key.pem ec2-user@$PUBLIC_IP

# EC2에서 스크립트 실행
chmod +x fix-postgres-container.sh
./fix-postgres-container.sh
```

**스크립트 실행 중 문제 발생 시:**

만약 스크립트가 Parameter Store 접근에 실패하면, 기본값으로 계속 진행하거나 아래 "방법 2"를 사용하세요.

##### 방법 2: UserData 스크립트 수동 실행
```bash
# EC2에 SSH 접속한 후

# 1. Docker 서비스 시작 (필요 시)
sudo systemctl start docker
sudo systemctl enable docker

# 2. Parameter Store에서 연결 정보 가져오기
REGION=$(curl -s http://169.254.169.254/latest/meta-data/placement/region || echo "ap-northeast-2")
POSTGRES_PASSWORD=$(aws ssm get-parameter --name /skn18/postgres-password --with-decryption --region "$REGION" --query 'Parameter.Value' --output text 2>&1)
if [ $? -ne 0 ] || [ -z "$POSTGRES_PASSWORD" ]; then
  echo "ERROR: Failed to retrieve PostgreSQL password from Parameter Store"
  echo "Error details: $POSTGRES_PASSWORD"
  POSTGRES_PASSWORD="s18f2t!@#"  # 임시 기본값
fi

# 3. PostgreSQL 데이터 디렉토리 준비
mkdir -p /var/lib/postgresql
chown ec2-user:ec2-user /var/lib/postgresql

# 4. 기존 컨테이너 정리
docker stop pg-db-final || true
docker rm -f pg-db-final || true

# 5. Docker 컨테이너 실행
# Parameter Store에서 실제 값 가져오기 (CloudFormation 템플릿 참고)
POSTGRES_DB=$(aws ssm get-parameter --name /skn18/postgres-db-name --region "$REGION" --query 'Parameter.Value' --output text)
POSTGRES_USER=$(aws ssm get-parameter --name /skn18/postgres-user --region "$REGION" --query 'Parameter.Value' --output text)
POSTGRES_PORT=$(aws ssm get-parameter --name /skn18/postgres-port --region "$REGION" --query 'Parameter.Value' --output text)

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

# 6. 컨테이너 상태 확인
docker ps | grep pg-db-final
docker logs pg-db-final
```

##### 방법 2: EC2 인스턴스 재시작
```bash
# 로컬에서 실행
aws ec2 reboot-instances \
  --instance-ids <INSTANCE_ID> \
  --region ap-northeast-2

# Instance ID 확인
aws cloudformation describe-stacks \
  --stack-name skn18-final-infra \
  --region ap-northeast-2 \
  --query 'Stacks[0].Outputs[?OutputKey==`InstanceId`].OutputValue' \
  --output text
```

##### 방법 4: CloudFormation 스택 업데이트 (UserData 재실행)
```bash
# 로컬에서 실행
cd infra/aws/cloudformation
./deploy.sh
```

#### 문제: "Connection refused"
**원인**: PostgreSQL 포트가 열리지 않았거나 컨테이너가 정상 실행되지 않음

**확인 방법**:
```bash
# EC2에 SSH 접속한 후

# 1. 컨테이너 상태 확인
docker ps | grep pg-db-final

# 2. 포트 리스닝 확인
sudo netstat -tlnp | grep 5432
# 또는
sudo ss -tlnp | grep 5432

# 3. 컨테이너 로그 확인
docker logs pg-db-final
```

**해결 방법**:
```bash
# 컨테이너 재시작
docker restart pg-db-final

# 또는 컨테이너 재생성
docker stop pg-db-final
docker rm pg-db-final
# UserData 스크립트가 자동으로 재생성하거나 수동으로 실행
```

#### 문제: "password authentication failed"
**원인**: Parameter Store의 비밀번호와 실제 비밀번호 불일치

**해결 방법**:
```bash
# 1. Parameter Store 비밀번호 확인
aws ssm get-parameter \
  --name /skn18/postgres-password \
  --with-decryption \
  --region ap-northeast-2 \
  --query 'Parameter.Value' \
  --output text

# 2. EC2에서 실제 사용 중인 비밀번호 확인 (UserData 로그 확인)
# EC2에 SSH 접속 후
sudo cat /var/log/cloud-init-output.log | grep POSTGRES_PASSWORD
```

### 3.3 Health Check 실패

#### Health Check 상태 확인
```bash
# EC2에 SSH 접속한 후
docker inspect pg-db-final --format='{{.State.Health.Status}}'

# unhealthy인 경우
docker inspect pg-db-final --format='{{json .State.Health}}' | jq
```

**해결 방법**:
```bash
# 컨테이너 재시작
docker restart pg-db-final

# Health Check 대기 (최대 50초)
sleep 60
docker inspect pg-db-final --format='{{.State.Health.Status}}'
```

---

## 4. 유용한 명령어 모음

### 4.1 빠른 확인 스크립트

```bash
#!/bin/bash
# EC2 SSH 접속 및 PostgreSQL 확인 스크립트

STACK_NAME="skn18-final-infra"
REGION="ap-northeast-2"

# Public IP 확인
PUBLIC_IP=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --region $REGION \
  --query 'Stacks[0].Outputs[?OutputKey==`PublicIp`].OutputValue' \
  --output text)

echo "EC2 Public IP: $PUBLIC_IP"

# SSH 접속
echo "SSH 접속 중..."
ssh -i ~/.ssh/skn18-final-2team-key.pem ec2-user@$PUBLIC_IP << 'EOF'
  echo "=== Docker 컨테이너 상태 ==="
  docker ps | grep pg-db-final
  
  echo ""
  echo "=== PostgreSQL 버전 확인 ==="
  docker exec pg-db-final psql -U postgres -d sknfinaldb -c "SELECT version();"
  
  echo ""
  echo "=== Health Check 상태 ==="
  docker inspect pg-db-final --format='{{.State.Health.Status}}'
EOF
```

### 4.2 로컬에서 PostgreSQL 연결 스크립트

```bash
#!/bin/bash
# 로컬에서 PostgreSQL 연결 스크립트

STACK_NAME="skn18-final-infra"
REGION="ap-northeast-2"

# 연결 정보 가져오기
PUBLIC_IP=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --region $REGION \
  --query 'Stacks[0].Outputs[?OutputKey==`PublicIp`].OutputValue' \
  --output text)

POSTGRES_PORT=$(aws ssm get-parameter \
  --name /skn18/postgres-port \
  --region $REGION \
  --query 'Parameter.Value' \
  --output text)

POSTGRES_USER=$(aws ssm get-parameter \
  --name /skn18/postgres-user \
  --region $REGION \
  --query 'Parameter.Value' \
  --output text)

POSTGRES_DB=$(aws ssm get-parameter \
  --name /skn18/postgres-db-name \
  --region $REGION \
  --query 'Parameter.Value' \
  --output text)

POSTGRES_PASSWORD=$(aws ssm get-parameter \
  --name /skn18/postgres-password \
  --with-decryption \
  --region $REGION \
  --query 'Parameter.Value' \
  --output text)

# PostgreSQL 연결
PGPASSWORD=$POSTGRES_PASSWORD psql \
  -h $PUBLIC_IP \
  -p $POSTGRES_PORT \
  -U $POSTGRES_USER \
  -d $POSTGRES_DB
```

---

## 참고 자료

- [README_cf.md](./README_cf.md) - CloudFormation 템플릿 구조
- [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) - 일반적인 문제 해결
- [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) - 배포 가이드

