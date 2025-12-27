## 구조
**1. core-infra.yaml (변경 적은 인프라)**
- VPC/Subnet/IGW/RouteTable
- S3 Bucket
- Security Group
- EC2 Instance (pgvector)
- Lambda IAM Role (공용)
- Outputs: BucketName, RoleArn, SGId, SubnetId, VpcId, DB 연결 정보 등
- 모든 파라미터를 Parameter Store에서 읽도록 변경
- 민감 정보(비밀번호)는 SecureString 타입 사용
- Parameter Store 경로:
```
  /skn18/key-name
  /skn18/instance-type
  /skn18/allowed-cidr
  /skn18/postgres-db-name
  /skn18/postgres-user
  /skn18/postgres-password (SecureString)
  /skn18/postgres-port
  /skn18/s3-bucket-name
``` 

**2. lambdas-protocols.yaml (Protocols Lambda 7개 + Step Function)**
- Lambda 함수 7개 (Protein, Cell, DNA, RNA, vivo, mouse, cleanse-chunk)
- Step Function State Machine 1개 (6개 Ingest Lambda 병렬 실행)
- Step Function 실행 역할 (IAM Role) 1개
- EventBridge Step Function 실행 역할 (IAM Role) 1개
- EventBridge Rule 1개 (Step Function 실행, 기존 6개 Rule은 비활성화)
- Lambda Permissions 7개
- Parameters: Core에서 받을 값들 (BucketName, RoleArn, DB 정보 등)
- ClientAccessToken, LambdaTimeout, LambdaMemorySize를 Parameter Store에서 읽도록 변경
- Parameter Store 경로:
```
/skn18/client-access-token (SecureString)
/skn18/lambda-timeout
/skn18/lambda-memory-size
```

**3. lambdas-nih.yaml (NIH Lambda 2개)**
- Lambda 함수 2개 (ingest, cleanse-chunk)
- EventBridge Rules 2개
- Lambda Permissions 2개
- Parameters: Core에서 받을 값들
- OpenAiApiKey, LambdaTimeout을 Parameter Store에서 읽도록 변경
- Parameter Store 경로:
```
/skn18/openai-api-key (SecureString)
/skn18/lambda-timeout
```
  
**4. 부모 템플릿 (skn18-final-infra-cf.yaml)**
- 모든 Parameters 정의
- Nested Stack 3개 (AWS::CloudFormation::Stack)
- 최종 Outputs
- Parameter Store를 직접 참조하도록 단순화

## 배포 방법

### 배포 전 필수 확인 사항

#### 1. Lambda Layer requirements.txt 확인
```bash
cd infra/aws/lambda_layers
ls -la */requirements.txt

# 심볼릭 링크가 없으면 생성
./create-symlinks.sh
```

#### 2. Parameter Store 파라미터 확인
필수 파라미터가 모두 등록되어 있는지 확인:
```bash
# 필수 파라미터 목록 확인
aws ssm describe-parameters --region ap-northeast-2 \
  --parameter-filters "Key=Name,Values=/skn18/" \
  --query 'Parameters[*].Name' --output table
```

필수 파라미터:
- `/skn18/key-name` (String)
- `/skn18/instance-type` (String)
- `/skn18/allowed-cidr` (String)
- `/skn18/postgres-db-name` (String)
- `/skn18/postgres-user` (String)
- `/skn18/postgres-password` (SecureString)
- `/skn18/postgres-port` (String)
- `/skn18/s3-bucket-name` (String)
- `/skn18/pgvector-ami-id` (String)
- `/skn18/lambda-timeout` (String)
- `/skn18/lambda-memory-size` (String)
- `/skn18/client-access-token` (SecureString, Protocols용)
- `/skn18/openai-api-key` (SecureString, NIH용)

파라미터 생성 스크립트:
```bash
cd infra/aws/cloudformation
./shells/create-parameters.sh
```

### 자동 배포 스크립트 사용 (권장)
```bash
cd infra/aws/cloudformation
./deploy.sh
```

이 스크립트는 다음을 자동으로 수행합니다:
1. Lambda Layer `requirements.txt` 확인 및 생성
2. `prepare_build.sh` 실행
3. `sam build` 실행
4. `sam package` 실행 (중요!)
5. `aws cloudformation deploy` 실행

### 수동 배포
```bash
# 0. Lambda Layer requirements.txt 확인 (필수!)
cd infra/aws/lambda_layers
ls -la */requirements.txt
# 없으면: ./create-symlinks.sh

# 1. Lambda 빌드 디렉토리 준비 (필수!)
cd ../lambda_build
./prepare_build.sh

# 2. SAM 빌드
cd ../cloudformation
rm -rf .aws-sam
sam build -t skn18-final-infra-cf.yaml

# 3. SAM 패키징 (중요: Nested Stack 템플릿과 CodeUri를 S3 URL로 변환)
sam package \
  --template-file .aws-sam/build/template.yaml \
  --output-template-file packaged.yaml \
  --resolve-s3 \
  --region ap-northeast-2

# 4. CloudFormation 배포
# ⚠️ 중요: CAPABILITY_IAM이 필수입니다 (IAM Role/InstanceProfile 생성 때문)
aws cloudformation deploy \
  --template-file packaged.yaml \
  --stack-name skn18-final-infra \
  --capabilities CAPABILITY_AUTO_EXPAND CAPABILITY_IAM \
  --region ap-northeast-2 \
  --no-fail-on-empty-changeset
```

> **중요**: Nested Stack 구조에서는 `sam deploy` 대신 `sam package` + `aws cloudformation deploy`를 사용해야 합니다. `sam deploy`는 루트 템플릿만 S3에 업로드하므로, Nested Stack 템플릿 내부의 `CodeUri`가 로컬 경로로 남아 Lambda 코드를 찾을 수 없습니다.


## 사용 방법

### 1. Parameter Store 파라미터 생성
```bash
cd infra/aws/cloudformation
./shells/create-parameters.sh
```

### 2. SecureString 파라미터 수동 설정
```bash
aws ssm put-parameter \
  --region ap-northeast-2 \
  --name /skn18/postgres-password \
  --type SecureString \
  --value 'your-password'

aws ssm put-parameter \
  --region ap-northeast-2 \
  --name /skn18/client-access-token \
  --type SecureString \
  --value 'your-token'

aws ssm put-parameter \
  --region ap-northeast-2 \
  --name /skn18/openai-api-key \
  --type SecureString \
  --value 'your-api-key'
```


```bash
# 파라미터 변경 할 경우
aws ssm put-parameter --overwrite
# 저장 된 파라미터 확인 할 경우
aws ssm get-parameter --with-decryption
```


### 3. CloudFormation 스택 배포
```bash
# 자동 배포 스크립트 사용 (권장)
cd infra/aws/cloudformation
./deploy.sh

# 또는 수동 배포 (위의 "배포 방법" 섹션 참고)
```

---

## Lambda Layer

**1. Lambda Layer 디렉토리 구조**
```
infra/aws/lambda_layers/
├── common/
│   └── requirements-layer-common.txt (requests, python-dateutil, python-dotenv)
├── protocols/
│   └── requirements-layer-protocols.txt (beautifulsoup4, lxml, psycopg2-binary)
└── nih/
    └── requirements-layer-nih.txt (tiktoken, nltk + NLTK 데이터)
```
**2. core-infra.yaml**
- 3개의 Lambda Layer 리소스 추가:
  - CommonLambdaLayer: 공통 라이브러리
  - ProtocolsLambdaLayer: Protocols 전용 라이브러리
  - NihLambdaLayer: NIH 전용 라이브러리 (NLTK 데이터 포함)
- Outputs에 Layer ARN 추가

**3. lambdas-protocols.yaml**
- 모든 Lambda 함수에 Layer 연결:
  - CommonLayerArn + ProtocolsLayerArn
- BuildCommand 수정: Layer에 포함된 패키지 제거 로직 추가
  
**4. lambdas-nih.yaml**
- 모든 Lambda 함수에 Layer 연결:
  - CommonLayerArn + NihLayerArn
- BuildCommand 수정: Layer에 포함된 패키지 제거 및 NLTK 데이터 다운로드 제거

**5. 부모 템플릿 (skn18-final-infra-cf.yaml)**
- Protocols/NIH 스택에 Layer ARN 전달 추가
  








---

## StepFunction 추가

### 개요
Protocols Ingest Lambda 6개(Cell, DNA, Mouse, Protein, RNA, Vivo)를 병렬로 실행하기 위해 Step Function을 사용합니다.

### 구조
- **Step Function State Machine**: `skn18-protocols-ingest-parallel`
  - 6개 Lambda 함수를 `Parallel` 상태로 병렬 실행
  - 각 Lambda는 독립적으로 실행되며 서로 영향을 주지 않음
- **EventBridge Rule**: 하루에 한 번 Step Function 실행
  - 기존 6개 개별 EventBridge Rule은 `DISABLED` 상태로 유지 (백업용)
- **IAM 역할**:
  - `StepFunctionExecutionRole`: Step Function이 Lambda 함수를 호출할 수 있는 권한
  - `EventBridgeStepFunctionRole`: EventBridge가 Step Function을 실행할 수 있는 권한

### 장점
1. **병렬 실행**: 6개 Lambda가 동시에 실행되어 처리 시간 단축
2. **중앙 관리**: 하나의 EventBridge Rule로 모든 Ingest Lambda 관리
3. **실행 추적**: Step Function 콘솔에서 전체 실행 상태 모니터링 가능
4. **에러 처리**: Step Function에서 각 Lambda의 성공/실패 상태 추적 가능

### 배포 후 확인
```bash
# Step Function State Machine 확인
aws stepfunctions list-state-machines \
  --region ap-northeast-2 \
  --query 'stateMachines[?starts_with(name, `skn18-`)].name' \
  --output table

# EventBridge Rule 확인
aws events list-rules \
  --region ap-northeast-2 \
  --name-prefix skn18-protocols-ingest \
  --query 'Rules[*].[Name,State]' \
  --output table
```

## 실행

자동 배포 스크립트 사용을 권장합니다:
```bash
cd infra/aws/cloudformation
./deploy.sh
```

수동 배포 방법은 위의 "배포 방법" 섹션을 참고하세요.

---



## 빌드 및 배포 방법

### 중요: 빌드 전 필수 단계

**옵션 1 방식 사용**: `prepare_build.sh`를 사용하여 필요한 파일만 선별 복사합니다.

```bash
# 0. Lambda Layer requirements.txt 확인 (필수!)
cd infra/aws/lambda_layers
ls -la */requirements.txt
# 없으면: ./create-symlinks.sh

# 1. Lambda 빌드 디렉토리 준비 (필수!)
cd ../lambda_build
./prepare_build.sh

# 2. SAM 빌드
cd ../cloudformation
rm -rf .aws-sam  # 기존 빌드 캐시 제거
sam build -t skn18-final-infra-cf.yaml

# 3. 빌드 크기 확인
du -sh .aws-sam/build/*/

# 4. SAM 패키징 (중요: Nested Stack 템플릿과 CodeUri를 S3 URL로 변환)
sam package \
  --template-file .aws-sam/build/template.yaml \
  --output-template-file packaged.yaml \
  --resolve-s3 \
  --region ap-northeast-2

# 5. CloudFormation 배포
# ⚠️ 중요: CAPABILITY_IAM이 필수입니다 (IAM Role/InstanceProfile 생성 때문)
aws cloudformation deploy \
  --template-file packaged.yaml \
  --stack-name skn18-final-infra \
  --capabilities CAPABILITY_AUTO_EXPAND CAPABILITY_IAM \
  --region ap-northeast-2 \
  --no-fail-on-empty-changeset
```

### 빌드 프로세스 설명

1. **prepare_build.sh 실행**: 
   - `infra/aws/lambda_build/protocols/` 디렉토리에 Protocols Lambda에 필요한 파일만 복사
   - `infra/aws/lambda_build/nih/` 디렉토리에 NIH Lambda에 필요한 파일만 복사
   - 필요한 파일: `rag/etl/`, `infra/aws/lambda_functions/trigger_etl/`, `rag/config/` 등

2. **SAM 빌드**:
   - `CodeUri: ../../lambda_build/protocols` 또는 `../../lambda_build/nih`를 사용
   - BuildCommand는 캐시 파일만 정리 (prepare_build.sh가 이미 필요한 파일만 복사했으므로)

3. **예상 빌드 크기**:
   - CoreInfraStack: ~42M (Lambda Layers)
   - ProtocolsLambdaStack: ~100-300MB (이전 120G에서 대폭 감소)
   - NihLambdaStack: ~100-300MB (이전 34G에서 대폭 감소)

### 기존 방식 (사용 안 함)

```bash
# 이 방식은 사용하지 않습니다 (전체 프로젝트가 복사되어 빌드 크기가 매우 큼)
cd infra/aws/cloudformation
sam build -t skn18-final-infra-cf.yaml  # ❌ 사용 안 함
```

## 배포 후 확인

### 1. 스택 상태 확인
```bash
cd infra/aws/cloudformation
./check-status.sh

# 또는 직접 확인
aws cloudformation describe-stacks \
  --stack-name skn18-final-infra \
  --region ap-northeast-2 \
  --query 'Stacks[0].StackStatus' \
  --output text
```

### 2. Lambda 함수 확인
```bash
aws lambda list-functions \
  --region ap-northeast-2 \
  --query 'Functions[?starts_with(FunctionName, `skn18-`)].FunctionName' \
  --output table
```

### 3. Lambda Layer 확인
```bash
aws lambda list-layers \
  --region ap-northeast-2 \
  --query 'Layers[?starts_with(LayerName, `skn18-`)].LayerName' \
  --output table
```

### 4. 스택 출력 확인
```bash
aws cloudformation describe-stacks \
  --stack-name skn18-final-infra \
  --region ap-northeast-2 \
  --query 'Stacks[0].Outputs' \
  --output table
```

### 5. EC2 SSH 접속 및 데이터베이스 확인

#### PostgreSQL 확인
```bash
# 상세 가이드 참고
# [EC2_SSH_AND_POSTGRES.md](./EC2_SSH_AND_POSTGRES.md)
```

#### Neo4j 확인
```bash
# 상세 가이드 참고
# [EC2_SSH_AND_NEO4J.md](./EC2_SSH_AND_NEO4J.md)

# 자동 설치 문제 해결
# [NEO4J_TROUBLESHOOTING.md](./NEO4J_TROUBLESHOOTING.md)
```
