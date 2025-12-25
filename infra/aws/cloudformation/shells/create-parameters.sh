#!/bin/bash
# Parameter Store에 필요한 파라미터들을 생성하는 스크립트
# “설정값(비민감)” = SSM Parameter + CFN로 생성/관리 가능
# “비밀(민감)” = Secrets Manager(권장) 또는 SSM SecureString(별도 생성) + CFN은 참조만

set -e

REGION="${AWS_REGION:-ap-northeast-2}"
PREFIX="/skn18"

echo "Creating Parameter Store parameters in region: $REGION"
echo "Prefix: $PREFIX"
echo ""

# 일반 String 파라미터들
aws ssm put-parameter \
  --region "$REGION" \
  --name "${PREFIX}/key-name" \
  --type "String" \
  --value "my-keypair" \
  --description "EC2 SSH KeyPair 이름" \
  --overwrite 2>/dev/null || echo "  ✓ ${PREFIX}/key-name (이미 존재하거나 생성됨)"

aws ssm put-parameter \
  --region "$REGION" \
  --name "${PREFIX}/instance-type" \
  --type "String" \
  --value "t3.medium" \
  --description "EC2 인스턴스 타입" \
  --overwrite 2>/dev/null || echo "  ✓ ${PREFIX}/instance-type (이미 존재하거나 생성됨)"

aws ssm put-parameter \
  --region "$REGION" \
  --name "${PREFIX}/allowed-cidr" \
  --type "String" \
  --value "0.0.0.0/0" \
  --description "DB에 접근 가능한 CIDR" \
  --overwrite 2>/dev/null || echo "  ✓ ${PREFIX}/allowed-cidr (이미 존재하거나 생성됨)"

aws ssm put-parameter \
  --region "$REGION" \
  --name "${PREFIX}/postgres-db-name" \
  --type "String" \
  --value "sknfinaldb" \
  --description "PostgreSQL 데이터베이스 이름" \
  --overwrite 2>/dev/null || echo "  ✓ ${PREFIX}/postgres-db-name (이미 존재하거나 생성됨)"

aws ssm put-parameter \
  --region "$REGION" \
  --name "${PREFIX}/postgres-user" \
  --type "String" \
  --value "helixops" \
  --description "PostgreSQL 사용자 이름" \
  --overwrite 2>/dev/null || echo "  ✓ ${PREFIX}/postgres-user (이미 존재하거나 생성됨)"

aws ssm put-parameter \
  --region "$REGION" \
  --name "${PREFIX}/postgres-port" \
  --type "String" \
  --value "5432" \
  --description "PostgreSQL 포트" \
  --overwrite 2>/dev/null || echo "  ✓ ${PREFIX}/postgres-port (이미 존재하거나 생성됨)"

aws ssm put-parameter \
  --region "$REGION" \
  --name "${PREFIX}/s3-bucket-name" \
  --type "String" \
  --value "skn18-etl-data" \
  --description "ETL 데이터 저장용 S3 버킷 이름" \
  --overwrite 2>/dev/null || echo "  ✓ ${PREFIX}/s3-bucket-name (이미 존재하거나 생성됨)"

aws ssm put-parameter \
  --region "$REGION" \
  --name "${PREFIX}/lambda-timeout" \
  --type "String" \
  --value "900" \
  --description "Lambda 함수 타임아웃 (초)" \
  --overwrite 2>/dev/null || echo "  ✓ ${PREFIX}/lambda-timeout (이미 존재하거나 생성됨)"

aws ssm put-parameter \
  --region "$REGION" \
  --name "${PREFIX}/lambda-memory-size" \
  --type "String" \
  --value "2048" \
  --description "Lambda 함수 메모리 크기 (MB)" \
  --overwrite 2>/dev/null || echo "  ✓ ${PREFIX}/lambda-memory-size (이미 존재하거나 생성됨)"

# SecureString 파라미터들 (비밀번호, API 키 등)
echo ""
echo "Creating SecureString parameters..."
echo "⚠️  다음 파라미터들은 수동으로 설정해야 합니다:"
echo "   - ${PREFIX}/postgres-password"
echo "   - ${PREFIX}/client-access-token"
echo "   - ${PREFIX}/openai-api-key"
echo ""
echo "예시 명령어:"
echo "  aws ssm put-parameter --region $REGION --name ${PREFIX}/postgres-password --type SecureString --value 'your-password'"
echo "  aws ssm put-parameter --region $REGION --name ${PREFIX}/client-access-token --type SecureString --value 'your-token'"
echo "  aws ssm put-parameter --region $REGION --name ${PREFIX}/openai-api-key --type SecureString --value 'your-api-key'"
echo ""

echo "✓ Parameter Store 파라미터 생성 완료!"
echo ""
echo "다음 단계:"
echo "1. SecureString 파라미터들을 위의 명령어로 설정하세요"
echo "2. CloudFormation 스택을 배포하세요"


