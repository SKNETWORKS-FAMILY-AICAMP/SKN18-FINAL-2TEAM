# Lambda Layer 배포 준비 체크리스트

## ✅ 빌드 완료 확인

### 빌드 크기 (최종)
```
42M    CoreInfraStack/          (Lambda Layers 포함)
544K   NihLambdaStack/          (이전 34G → 544K, 99.998% 감소!)
1.0M   ProtocolsLambdaStack/   (이전 120G → 1.0M, 99.999% 감소!)
```

### Lambda Layer 빌드 확인
- ✅ CommonLambdaLayer: 2.6M
- ✅ ProtocolsLambdaLayer: 23M
- ✅ NihLambdaLayer: 17M

### Lambda 함수 빌드 확인
- ✅ Protocols Lambda 함수 7개: 각 ~100-150KB
- ✅ NIH Lambda 함수 2개: 각 ~200-300KB

---

## ✅ 구성 확인

### 1. Lambda Layer 정의 (core-infra.yaml)
- ✅ CommonLambdaLayer: `../lambda_layers/common/`
- ✅ ProtocolsLambdaLayer: `../lambda_layers/protocols/`
- ✅ NihLambdaLayer: `../lambda_layers/nih/`
- ✅ Outputs에 Layer ARN 포함

### 2. Lambda 함수 Layer 연결
- ✅ Protocols Lambda (7개): `CommonLayerArn` + `ProtocolsLayerArn`
- ✅ NIH Lambda (2개): `CommonLayerArn` + `NihLayerArn`

### 3. 부모 템플릿 (skn18-final-infra-cf.yaml)
- ✅ CoreInfraStack → ProtocolsLambdaStack: Layer ARN 전달
- ✅ CoreInfraStack → NihLambdaStack: Layer ARN 전달

### 4. 빌드 프로세스
- ✅ `prepare_build.sh` 실행하여 필요한 파일만 복사
- ✅ CodeUri: `../lambda_build/protocols` 또는 `../lambda_build/nih`
- ✅ BuildCommand: 캐시 파일만 정리 (prepare_build.sh가 이미 필요한 파일만 복사)

---

## 📋 배포 전 필수 확인 사항

### 1. Parameter Store 파라미터 확인
```bash
# 필수 파라미터 확인
aws ssm get-parameter --name /skn18/key-name --region ap-northeast-2
aws ssm get-parameter --name /skn18/instance-type --region ap-northeast-2
aws ssm get-parameter --name /skn18/allowed-cidr --region ap-northeast-2
aws ssm get-parameter --name /skn18/postgres-db-name --region ap-northeast-2
aws ssm get-parameter --name /skn18/postgres-user --region ap-northeast-2
aws ssm get-parameter --name /skn18/postgres-password --with-decryption --region ap-northeast-2
aws ssm get-parameter --name /skn18/postgres-port --region ap-northeast-2
aws ssm get-parameter --name /skn18/s3-bucket-name --region ap-northeast-2
aws ssm get-parameter --name /skn18/client-access-token --with-decryption --region ap-northeast-2
aws ssm get-parameter --name /skn18/openai-api-key --with-decryption --region ap-northeast-2
aws ssm get-parameter --name /skn18/lambda-timeout --region ap-northeast-2
aws ssm get-parameter --name /skn18/lambda-memory-size --region ap-northeast-2
aws ssm get-parameter --name /skn18/nih-cleanse-chunk-memory-size --region ap-northeast-2
aws ssm get-parameter --name /skn18/pgvector-ami-id --region ap-northeast-2
```

### 2. AMI 확인 (Packer로 빌드된 AMI)
```bash
# AMI ID 확인
aws ssm get-parameter --name /skn18/pgvector-ami-id --region ap-northeast-2

# AMI가 없으면 Packer로 빌드 필요
cd infra/aws/packer
packer build -var "vpc_id=vpc-xxxxx" -var "subnet_id=subnet-xxxxx" packer.pkr.hcl
```

### 3. AWS 자격 증명 확인
```bash
aws sts get-caller-identity
```

---

## 🚀 배포 명령어

### 1. 빌드 및 패키징
```bash
cd infra/aws/lambda_build
./prepare_build.sh

cd ../cloudformation
rm -rf .aws-sam
sam build -t skn18-final-infra-cf.yaml

# SAM 패키징 (중요!)
sam package \
  --template-file .aws-sam/build/template.yaml \
  --output-template-file packaged.yaml \
  --resolve-s3 \
  --region ap-northeast-2
```

### 2. 배포

**자동 배포 스크립트 사용 (권장):**
```bash
cd infra/aws/cloudformation
./deploy.sh
```

**수동 배포:**
```bash
cd infra/aws/cloudformation

# SAM 빌드
rm -rf .aws-sam
sam build -t skn18-final-infra-cf.yaml

# SAM 패키징 (중요: Nested Stack 템플릿과 CodeUri를 S3 URL로 변환)
sam package \
  --template-file .aws-sam/build/template.yaml \
  --output-template-file packaged.yaml \
  --resolve-s3 \
  --region ap-northeast-2

# CloudFormation 배포
aws cloudformation deploy \
  --template-file packaged.yaml \
  --stack-name skn18-final-infra \
  --capabilities CAPABILITY_AUTO_EXPAND \
  --region ap-northeast-2
```

> **중요**: Nested Stack 구조에서는 `sam deploy` 대신 `sam package` + `aws cloudformation deploy`를 사용해야 합니다. `sam deploy`는 루트 템플릿만 S3에 업로드하므로, Nested Stack 템플릿 내부의 `CodeUri`가 로컬 경로로 남아 Lambda 코드를 찾을 수 없습니다.

### 3. 배포 확인
```bash
# 스택 상태 확인
aws cloudformation describe-stacks --stack-name skn18-final-infra --region ap-northeast-2

# Lambda 함수 확인
aws lambda list-functions --region ap-northeast-2 | grep skn18

# Lambda Layer 확인
aws lambda list-layers --region ap-northeast-2 | grep skn18
```

---

## 📊 배포 후 확인 사항

### 1. Lambda Layer 확인
- [ ] CommonLambdaLayer ARN 확인
- [ ] ProtocolsLambdaLayer ARN 확인
- [ ] NihLambdaLayer ARN 확인

### 2. Lambda 함수 확인
- [ ] Protocols Lambda 함수 7개 생성 확인
- [ ] NIH Lambda 함수 2개 생성 확인
- [ ] 각 Lambda 함수에 Layer 연결 확인

### 3. EventBridge 규칙 확인
- [ ] Protocols Lambda 스케줄 규칙 7개 확인
- [ ] NIH Lambda 스케줄 규칙 2개 확인

### 4. 테스트
- [ ] Lambda 함수 수동 실행 테스트
- [ ] EventBridge 스케줄 동작 확인

---

## 🎉 배포 준비 완료!

모든 빌드가 성공적으로 완료되었고, Lambda Layer와 Lambda 함수가 올바르게 구성되었습니다.

**주요 개선 사항:**
- 빌드 크기: 120G + 34G → 1.0M + 544K (99.99% 감소!)
- Lambda Layer를 통한 의존성 관리
- `prepare_build.sh`를 통한 효율적인 빌드 프로세스

이제 배포할 준비가 되었습니다! 🚀

