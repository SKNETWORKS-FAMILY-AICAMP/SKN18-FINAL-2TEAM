# CloudFormation 배포 가이드

이 문서는 SKN18-FINAL-2TEAM 프로젝트의 CloudFormation 배포 방법을 설명합니다.

## 중요 사항

### Nested Stack 구조의 특수성

이 프로젝트는 Nested Stack 구조를 사용합니다:
- 루트 템플릿: `skn18-final-infra-cf.yaml`
- Nested Stack: `core-infra.yaml`, `lambdas-protocols.yaml`, `lambdas-nih.yaml`

**중요**: Nested Stack 구조에서는 `sam deploy` 대신 `sam package` + `aws cloudformation deploy`를 사용해야 합니다.

**이유:**
- `sam deploy`는 루트 템플릿만 S3에 업로드합니다
- Nested Stack 템플릿 내부의 `CodeUri: ../lambda_build/...` 경로가 로컬 경로로 남아있어 CloudFormation이 Lambda 코드를 찾을 수 없습니다
- `sam package`는 모든 템플릿과 `CodeUri`를 S3 URL로 변환합니다

## 배포 방법

### 방법 1: 자동 배포 스크립트 사용 (권장)

```bash
cd infra/aws/cloudformation
./deploy.sh
```

이 스크립트는 다음을 자동으로 수행합니다:
1. Lambda Layer `requirements.txt` 확인
2. `prepare_build.sh` 실행
3. `sam build` 실행
4. `sam package` 실행 (중요!)
5. `aws cloudformation deploy` 실행

### 방법 2: 수동 배포

```bash
# 1. Lambda 빌드 디렉토리 준비 (필수!)
cd infra/aws/lambda_build
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
aws cloudformation deploy \
  --template-file packaged.yaml \
  --stack-name skn18-final-infra \
  --capabilities CAPABILITY_AUTO_EXPAND \
  --region ap-northeast-2
```

## 배포 전 확인 사항

### 1. Lambda Layer requirements.txt 확인

```bash
cd infra/aws/lambda_layers
ls -la */requirements.txt

# 심볼릭 링크가 없으면 생성
./create-symlinks.sh
```

### 2. Parameter Store 파라미터 확인

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
- `/skn18/client-access-token` (SecureString, Protocols용)
- `/skn18/openai-api-key` (SecureString, NIH용)

확인 방법:
```bash
aws ssm get-parameter --name /skn18/key-name --region ap-northeast-2
aws ssm get-parameter --name /skn18/postgres-password --with-decryption --region ap-northeast-2
```

### 3. AMI 확인

Packer로 빌드된 AMI ID가 Parameter Store에 저장되어 있어야 합니다:
```bash
aws ssm get-parameter --name /skn18/pgvector-ami-id --region ap-northeast-2
```

AMI가 없으면 Packer로 빌드:
```bash
cd infra/aws/packer
packer build -var "vpc_id=vpc-xxxxx" -var "subnet_id=subnet-xxxxx" packer.pkr.hcl
```

## 배포 후 확인

### 1. 스택 상태 확인

```bash
aws cloudformation describe-stacks \
  --stack-name skn18-final-infra \
  --region ap-northeast-2 \
  --query 'Stacks[0].StackStatus'
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

## 문제 해결

배포 중 문제가 발생하면 다음을 확인하세요:

1. **TROUBLESHOOTING.md** 참고
2. **deploy.log** 파일 확인 (배포 스크립트가 자동으로 생성)
3. CloudFormation 콘솔에서 스택 이벤트 확인
4. Nested Stack의 상세 오류 확인

### 일반적인 오류

#### Lambda 함수 생성 실패
- `prepare_build.sh`가 실행되었는지 확인
- `sam package`가 실행되었는지 확인 (`packaged.yaml` 파일 존재 확인)
- Lambda Layer가 올바르게 연결되었는지 확인

#### Nested Stack 실패
- `packaged.yaml`에서 `TemplateURL`이 S3 URL인지 확인
- Nested Stack 템플릿 내부의 `CodeUri`가 S3 URL인지 확인

## 참고 자료

- [README_cf.md](./README_cf.md) - 템플릿 구조 설명
- [DEPLOY_CHECKLIST.md](./DEPLOY_CHECKLIST.md) - 배포 체크리스트
- [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) - 문제 해결 가이드

