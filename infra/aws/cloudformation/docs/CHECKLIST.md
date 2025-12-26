# CloudFormation SAM Build 전 체크리스트

## ✅ 확인 완료 사항

1. **Nested Stack 구조**
   - ✅ 부모 스택 (`skn18-final-infra-cf.yaml`)에서 자식 스택들을 올바르게 참조
   - ✅ Parameters 전달이 올바름
   - ✅ Outputs 전달이 올바름

2. **Parameter Store 참조**
   - ✅ `core-infra.yaml`에서 모든 파라미터가 Parameter Store를 참조
   - ✅ `lambdas-protocols.yaml`과 `lambdas-nih.yaml`에서 필요한 파라미터들이 Parameter Store 참조

3. **Lambda Layers**
   - ✅ Common, Protocols, NIH Layer가 모두 정의됨
   - ✅ 각 Lambda 함수에서 올바른 Layer를 참조
   - ✅ Outputs에서 Layer ARN이 올바르게 전달됨

4. **AMI 설정**
   - ✅ `LatestAmiId`가 Parameter Store 경로 `/skn18/pgvector-ami-id`를 참조
   - ✅ UserData가 AMI 기반으로 간소화됨
   - ✅ Packer로 빌드된 AMI ID가 Parameter Store에 등록됨

5. **IAM 역할**
   - ✅ Lambda Execution Role이 정의되고 올바른 권한 포함
   - ✅ S3, Lambda Invoke 권한 포함

6. **Lambda MemorySize 설정**
   - ✅ `lambdas-nih.yaml`의 MemorySize 하드코딩 제거 완료
   - ✅ `LambdaMemorySize` 파라미터 추가 완료
   - ✅ `NihCleanseChunkMemorySize` 파라미터 추가 완료 (NIH 전용)
   - ✅ 모든 Lambda 함수가 Parameter Store 참조 사용

## 📝 Parameter Store 파라미터 확인

배포 전에 다음 파라미터들이 Parameter Store에 등록되어 있는지 확인:

### 필수 파라미터 (Core Infrastructure)
- ✅ `/skn18/pgvector-ami-id` - Packer로 빌드된 AMI ID
- `/skn18/key-name` - EC2 SSH KeyPair 이름
- `/skn18/instance-type` - EC2 인스턴스 타입
- `/skn18/allowed-cidr` - DB 접근 가능한 CIDR
- `/skn18/postgres-db-name` - PostgreSQL 데이터베이스 이름
- `/skn18/postgres-user` - PostgreSQL 사용자 이름
- `/skn18/postgres-password` - PostgreSQL 비밀번호 (SecureString)
- `/skn18/postgres-port` - PostgreSQL 포트
- `/skn18/s3-bucket-name` - ETL 데이터 저장용 S3 버킷 이름

### Lambda 설정 파라미터
- `/skn18/lambda-timeout` - Lambda 함수 타임아웃 (초)
- `/skn18/lambda-memory-size` - Lambda 함수 기본 메모리 크기 (MB)

### Lambda별 전용 파라미터
- `/skn18/nih-cleanse-chunk-memory-size` - NIH Cleansing + Chunking Lambda 메모리 크기 (MB, 선택사항)
  - 설정하지 않으면 `/skn18/lambda-memory-size` 사용
  - NIH는 메모리 사용량이 많아 더 큰 값 권장 (5120MB ~ 10240MB)

### 인증 정보 (SecureString)
- `/skn18/client-access-token` - Protocols.io Client Access Token (SecureString)
- `/skn18/openai-api-key` - OpenAI API Key (SecureString)

## 🔍 SAM Build 전 확인 명령어

```bash
# 1. Parameter Store 파라미터 목록 확인
aws ssm describe-parameters --region ap-northeast-2 \
  --parameter-filters "Key=Name,Values=/skn18/" \
  --query 'Parameters[*].[Name,Type]' --output table

# 2. 필수 파라미터 개별 확인
aws ssm get-parameter --region ap-northeast-2 --name "/skn18/pgvector-ami-id" --query 'Parameter.Value' --output text
aws ssm get-parameter --region ap-northeast-2 --name "/skn18/lambda-memory-size" --query 'Parameter.Value' --output text

# 3. NIH 전용 메모리 설정 (선택사항, 더 큰 값 필요 시)
./set-nih-memory.sh 10240  # 10240MB (최대값) 또는 원하는 값

# 4. 템플릿 유효성 검사
sam validate -t skn18-final-infra-cf.yaml
```

## 🚀 배포 절차

### 1. 사전 준비
```bash
cd infra/aws/cloudformation

# Parameter Store 파라미터 확인
aws ssm describe-parameters --region ap-northeast-2 \
  --parameter-filters "Key=Name,Values=/skn18/" \
  --query 'Parameters[*].Name' --output table

# 필수 파라미터가 모두 있는지 확인
# 없으면 create-parameters.sh 스크립트 참고하여 생성
```

### 2. SAM Build
```bash
# 빌드 디렉토리 준비 (Lambda 빌드 필요 시)
cd ../../lambda_build
./prepare_build.sh  # 필요 시

# CloudFormation 빌드
cd ../cloudformation
sam build -t skn18-final-infra-cf.yaml
```

### 3. SAM Deploy
```bash
# samconfig.toml 파일 없을 때 (첫 배포)
sam deploy --guided

# samconfig.toml이 설정되어 있으면
sam deploy
```

## ⚙️ 설정 가이드

### NIH Lambda MemorySize 늘리기

NIH Cleansing + Chunking Lambda는 메모리 사용량이 많아 더 큰 메모리가 필요할 수 있습니다.

**방법 1: 스크립트 사용 (권장)**
```bash
cd infra/aws/cloudformation
./set-nih-memory.sh 10240  # 10240MB (최대값)
```

**방법 2: 수동 설정**
```bash
aws ssm put-parameter \
  --region ap-northeast-2 \
  --name "/skn18/nih-cleanse-chunk-memory-size" \
  --type "String" \
  --value "10240" \
  --overwrite
```

**Lambda MemorySize 제약사항:**
- 최소: 128MB
- 최대: 10240MB (10GB)
- 단위: 64MB 단위

**권장 메모리 크기:**
- NIH Ingest: 2048MB (기본값 유지)
- NIH Cleansing + Chunking: 5120MB ~ 10240MB

## 📌 주의사항

1. **Parameter Store 파라미터**
   - SecureString 타입 파라미터 (`postgres-password`, `client-access-token`, `openai-api-key`)는 수동으로 설정해야 합니다
   - KMS 키 권한이 필요할 수 있습니다

2. **AMI ID**
   - Packer로 빌드한 AMI ID가 Parameter Store에 등록되어 있어야 합니다
   - AMI ID 확인: `aws ssm get-parameter --region ap-northeast-2 --name "/skn18/pgvector-ami-id"`

3. **VPC 및 네트워크**
   - CloudFormation이 자동으로 VPC를 생성합니다
   - 기존 VPC를 사용하려면 템플릿 수정 필요

4. **Lambda Layer 빌드**
   - SAM build 시 Lambda Layer가 자동으로 빌드됩니다
   - Layer 빌드 시간이 소요될 수 있습니다

5. **첫 배포 시간**
   - Lambda Layer 생성: 약 5-10분
   - EC2 인스턴스 생성 및 Docker 컨테이너 시작: 약 3-5분
   - 총 예상 시간: 약 10-15분

## ✅ 최종 체크리스트

배포 전 다음을 확인하세요:

- [ ] 모든 Parameter Store 파라미터가 등록되어 있음
- [ ] Packer AMI ID가 Parameter Store에 등록됨
- [ ] SecureString 파라미터들이 설정됨 (비밀번호, API 키)
- [ ] NIH 전용 메모리 설정 필요 시 설정 완료
- [ ] SAM validate 통과
- [ ] SAM build 성공
