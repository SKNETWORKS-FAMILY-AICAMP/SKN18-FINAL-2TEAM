# CloudFormation 배포 오류 및 해결 과정

이 문서는 SKN18-FINAL-2TEAM 프로젝트의 CloudFormation 배포 과정에서 발생한 오류들과 해결 방법을 정리한 것입니다.

## 목차

1. [Lambda Layer 빌드 오류](#1-lambda-layer-빌드-오류)
2. [SAM 빌드 오류](#2-sam-빌드-오류)
3. [Packer AMI 빌드 오류](#3-packer-ami-빌드-오류)
4. [CloudFormation 배포 오류](#4-cloudformation-배포-오류)
5. [Lambda 함수 생성 실패](#5-lambda-함수-생성-실패)

---

## 1. Lambda Layer 빌드 오류

### 오류 1-1: requirements.txt 파일 없음

**증상:**
```
Building layer 'CoreInfraStack/CommonLambdaLayer'
Running PythonPipBuilder:ResolveDependencies
requirements.txt file not found. Continuing the build without dependencies.
```

**원인:**
- SAM의 `PythonPipBuilder`는 `requirements.txt` 파일을 찾아야 의존성을 설치할 수 있음
- Lambda Layer 디렉토리(`infra/aws/lambda_layers/common/`)에 `requirements.txt`가 없고 `requirements-layer-common.txt`만 존재

**해결 방법:**
각 Lambda Layer 디렉토리에 `requirements.txt` 심볼릭 링크 생성:
```bash
cd infra/aws/lambda_layers/common
ln -s requirements-layer-common.txt requirements.txt

cd ../protocols
ln -s requirements-layer-protocols.txt requirements.txt

cd ../nih
ln -s requirements-layer-nih.txt requirements.txt
```

**참고:**
- 이후 Lambda Layer 구조 변경으로 심볼릭 링크는 제거됨
- Lambda Layer는 각 디렉토리에 직접 `requirements.txt` 파일을 두는 방식으로 변경

---

### 오류 1-2: PythonPipBuilder에서 pip를 찾을 수 없음

**증상:**
```
Error: PythonPipBuilder:ResolveDependencies - Failed to find a Python runtime containing pip on the PATH.
```

**원인:**
- 로컬 환경에 `pip`가 설치되어 있지 않거나 PATH에 없음
- SAM의 `PythonPipBuilder`가 로컬 Python 환경을 사용하려고 시도

**해결 방법:**
1. **옵션 1: Docker 컨테이너 사용 (권장)**
   ```bash
   sam build --use-container -t skn18-final-infra-cf.yaml
   ```

2. **옵션 2: 로컬에 pip 설치**
   ```bash
   # Python 3.12가 설치되어 있다면
   python3.12 -m ensurepip --upgrade
   ```

**참고:**
- `--use-container` 옵션을 사용하면 Lambda와 동일한 환경에서 빌드할 수 있어 더 안전함

---

## 2. SAM 빌드 오류

### 오류 2-1: Lambda 함수 빌드 디렉토리 없음

**증상:**
```
Error: [Errno 2] No such file or directory: '/Users/.../infra/lambda_build/protocols'
```

**원인:**
- `CodeUri` 경로가 잘못 설정됨
- `prepare_build.sh` 스크립트가 실행되지 않아 빌드 디렉토리가 생성되지 않음

**해결 방법:**
1. `prepare_build.sh` 실행:
   ```bash
   cd infra/aws/lambda_build
   ./prepare_build.sh
   ```

2. `CodeUri` 경로 확인 및 수정:
   - `lambdas-protocols.yaml`: `CodeUri: ../lambda_build/protocols`
   - `lambdas-nih.yaml`: `CodeUri: ../lambda_build/nih`

---

### 오류 2-2: 빌드 아티팩트 크기 과다

**증상:**
```bash
du -sh .aws-sam/build/*/
42M    .aws-sam/build/CoreInfraStack/
103G   .aws-sam/build/ProtocolsLambdaStack/  # 너무 큼!
29G    .aws-sam/build/NihLambdaStack/       # 너무 큼!
```

**원인:**
- `CodeUri: ../../..`로 설정되어 프로젝트 전체가 복사됨
- `BuildCommand`가 불필요한 파일을 제거하지 않음
- `.samignore`가 충분히 많은 파일을 제외하지 않음

**해결 방법:**
1. **CodeUri 변경:**
   - 프로젝트 루트 대신 `prepare_build.sh`로 준비된 빌드 디렉토리 사용
   - `CodeUri: ../lambda_build/protocols` 또는 `CodeUri: ../lambda_build/nih`

2. **BuildCommand 최적화:**
   ```yaml
   BuildCommand: |
     find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
     find . -name "*.pyc" -delete 2>/dev/null || true
   ```

3. **`.samignore` 강화:**
   ```
   # 개발 파일
   *.md
   *.txt
   !requirements.txt
   .git/
   .venv/
   node_modules/
   data/
   infra/neo4j/
   ```

**결과:**
```bash
du -sh .aws-sam/build/*/
42M    .aws-sam/build/CoreInfraStack/
1.0M   .aws-sam/build/ProtocolsLambdaStack/  # 대폭 감소!
544K   .aws-sam/build/NihLambdaStack/        # 대폭 감소!
```

---

## 3. Packer AMI 빌드 오류

### 오류 3-1: Unknown source type amazon-ebs

**증상:**
```
Error: Unknown source type amazon-ebs
```

**원인:**
- Packer의 `amazon` 플러그인이 초기화되지 않음
- `packer.pkr.hcl`에 `required_plugins` 블록이 없음

**해결 방법:**
`packer.pkr.hcl`에 다음 블록 추가:
```hcl
packer {
  required_plugins {
    amazon = {
      source  = "github.com/hashicorp/amazon"
      version = "~> 1"
    }
  }
}
```

그 후 플러그인 초기화:
```bash
packer init packer.pkr.hcl
```

---

### 오류 3-2: AMI를 찾을 수 없음

**증상:**
```
No AMI was found matching filters: ...
```

**원인:**
- `source_ami_filter`의 패턴이 너무 좁게 설정됨
- 해당 리전에 해당 패턴의 AMI가 존재하지 않음

**해결 방법:**
1. **AMI 필터 패턴 확대:**
   ```hcl
   source_ami_filter {
     filters = {
       name                = "al2023-ami-*x86_64"
       virtualization-type = "hvm"
     }
     most_recent = true
     owners      = ["amazon"]
   }
   ```

2. **사용 가능한 AMI 확인:**
   ```bash
   # check-ami.sh 스크립트 사용
   ./check-ami.sh ap-northeast-2
   ```

3. **직접 AMI ID 지정 (선택사항):**
   ```hcl
   # source_ami = "ami-0a04a4c757a2f0593"  # Amazon Linux 2023
   ```

---

### 오류 3-3: Free Tier 호환되지 않는 인스턴스 타입

**증상:**
```
api error InvalidParameterCombination: The specified instance type is not eligible for Free Tier.
```

**원인:**
- `instance_type`이 `t3.medium`으로 설정되어 Free Tier에 포함되지 않음

**해결 방법:**
`packer.pkr.hcl`에서 인스턴스 타입 변경:
```hcl
variable "instance_type" {
  type    = string
  default = "t2.micro"  # Free Tier 호환
}
```

---

### 오류 3-4: VPC가 지정되지 않음

**증상:**
```
api error VPCIdNotSpecified: No default VPC for this user
```

**원인:**
- AWS 계정에 기본 VPC가 없음
- Packer가 VPC와 서브넷을 명시적으로 지정해야 함

**해결 방법:**
1. **VPC 및 서브넷 찾기:**
   ```bash
   # find-vpc.sh 스크립트 사용 또는
   aws ec2 describe-vpcs --query 'Vpcs[?IsDefault==`true`].[VpcId]' --output text
   aws ec2 describe-subnets --filters "Name=vpc-id,Values=vpc-xxxxx" --query 'Subnets[0].SubnetId' --output text
   ```

2. **Packer 빌드 시 변수 전달:**
   ```bash
   packer build \
     -var 'vpc_id=vpc-xxxxx' \
     -var 'subnet_id=subnet-xxxxx' \
     packer.pkr.hcl
   ```

---

## 4. CloudFormation 배포 오류

### 오류 4-1: Unrecognized parameter type: SecureString

**증상:**
```
Template format error: Unrecognized parameter type: SecureString
```

**원인:**
- CloudFormation은 `AWS::SSM::Parameter::Value<SecureString>` 타입을 직접 지원하지 않음
- Parameter Store의 `SecureString` 타입을 CloudFormation 파라미터로 직접 참조할 수 없음

**해결 방법:**
1. **파라미터 타입을 String으로 변경:**
   ```yaml
   PostgresPassword:
     Type: "AWS::SSM::Parameter::Value<String>"
     Default: "/skn18/postgres-password"
   ```

2. **EC2 UserData에서 직접 가져오기:**
   ```bash
   # UserData 스크립트에서
   POSTGRES_PASSWORD=$(aws ssm get-parameter \
     --name /skn18/postgres-password \
     --with-decryption \
     --region $REGION \
     --query 'Parameter.Value' \
     --output text)
   ```

3. **Lambda 함수에서는 환경 변수로 Parameter Store 경로 전달:**
   ```yaml
   Environment:
     Variables:
       OPENAI_API_KEY_PARAMETER_PATH: !Ref OpenAiApiKeyParameterPath
   ```
   Lambda 코드에서 직접 Parameter Store에서 가져오기

---

### 오류 4-2: Parameter Store 타입 불일치

**증상:**
```
Types for SSM parameters [/skn18/postgres-port] defined in CFN template and SSM are incompatible
```

**원인:**
- CloudFormation 템플릿에서 `Number` 타입으로 정의했지만 Parameter Store에는 `String` 타입으로 저장됨
- 또는 그 반대

**해결 방법:**
1. **CloudFormation 템플릿 타입을 String으로 변경:**
   ```yaml
   PostgresPort:
     Type: "AWS::SSM::Parameter::Value<String>"
     Default: "/skn18/postgres-port"
   ```

2. **또는 Parameter Store 값을 String으로 변경:**
   ```bash
   aws ssm put-parameter \
     --name /skn18/postgres-port \
     --value "5432" \
     --type String \
     --overwrite
   ```

**참고:**
- Lambda의 `Timeout`과 `MemorySize`도 Number 타입이지만, Parameter Store에서 읽을 때는 String으로 읽어야 함
- 최종적으로는 Parameter Store를 사용하지 않고 직접 Number 타입 기본값 사용으로 변경:
  ```yaml
  LambdaTimeout:
    Type: Number
    Default: 900
  ```

---

### 오류 4-3: CAPABILITY_AUTO_EXPAND 필요

**증상:**
```
Requires capabilities : [CAPABILITY_AUTO_EXPAND]
```

**원인:**
- SAM 템플릿이 `AWS::Serverless-2016-10-31` Transform을 사용
- CloudFormation이 자동으로 확장해야 하는 리소스가 있음

**해결 방법:**
`sam deploy` 명령에 capability 추가:
```bash
sam deploy --capabilities CAPABILITY_AUTO_EXPAND
```

---

### 오류 4-4: CAPABILITY_NAMED_IAM 필요

**증상:**
```
Requires capabilities : [CAPABILITY_NAMED_IAM]
```

**원인:**
- IAM 역할에 명시적인 `RoleName`이 지정되어 있음
- CloudFormation이 명명된 IAM 리소스를 생성해야 함

**해결 방법:**
1. **옵션 1: Capability 추가 (권장하지 않음):**
   ```bash
   sam deploy --capabilities CAPABILITY_AUTO_EXPAND CAPABILITY_NAMED_IAM
   ```

2. **옵션 2: RoleName 제거 (권장):**
   ```yaml
   LambdaExecutionRole:
     Type: AWS::IAM::Role
     Properties:
       # RoleName: skn18-lambda-etl-role  # 제거
       AssumeRolePolicyDocument: ...
   ```
   CloudFormation이 자동으로 고유한 이름 생성

**최종 해결:**
- `RoleName`과 `InstanceProfileName` 제거
- CloudFormation이 자동으로 고유한 이름 생성하도록 변경

---

### 오류 4-5: IAM 역할 생성 실패

**증상:**
```
The following resource(s) failed to create: [LambdaExecutionRole, PgVectorInstance].
```

**원인:**
- 동일한 이름의 IAM 역할이 이미 존재함
- `RoleName: skn18-lambda-etl-role`이 이미 다른 스택에서 사용 중

**해결 방법:**
1. **기존 역할 확인:**
   ```bash
   aws iam get-role --role-name skn18-lambda-etl-role
   ```

2. **RoleName 제거:**
   ```yaml
   LambdaExecutionRole:
     Type: AWS::IAM::Role
     Properties:
       # RoleName: skn18-lambda-etl-role  # 제거
       ...
   ```

3. **InstanceProfileName도 제거:**
   ```yaml
   Ec2InstanceProfile:
     Type: AWS::IAM::InstanceProfile
     Properties:
       # InstanceProfileName: skn18-ec2-parameter-store-profile  # 제거
       Roles:
         - !Ref Ec2ParameterStoreRole
   ```

---

### 오류 4-6: EC2 인스턴스 생성 실패 - KeyName 불일치

**증상:**
```
The following resource(s) failed to create: [PgVectorInstance].
```

**원인:**
- Parameter Store의 `/skn18/key-name` 값이 `my-keypair`로 설정되어 있음
- 실제 키 페어 이름은 `skn18-final-2team-key`

**해결 방법:**
Parameter Store 값 업데이트:
```bash
aws ssm put-parameter \
  --name /skn18/key-name \
  --value "skn18-final-2team-key" \
  --type String \
  --overwrite \
  --region ap-northeast-2
```

---

### 오류 4-7: Lambda Layer ARN 참조 오류

**증상:**
```
Requested attribute Arn does not exist in schema for AWS::Lambda::LayerVersion
```

**원인:**
- `AWS::Serverless::LayerVersion` 리소스에서 `!GetAtt`로 ARN을 가져오려고 시도
- `AWS::Serverless::LayerVersion`은 `!Ref`로 ARN을 반환함

**해결 방법:**
`!GetAtt`를 `!Ref`로 변경:
```yaml
# Before
Outputs:
  CommonLayerArn:
    Value: !GetAtt CommonLambdaLayer.Arn

# After
Outputs:
  CommonLayerArn:
    Value: !Ref CommonLambdaLayer
```

---

## 5. Lambda 함수 생성 실패

### 오류 5-1: Handler 경로를 찾을 수 없음

**증상:**
```
The following resource(s) failed to create: [NihIngestLambda, NihCleanseChunkLambda].
```

**원인:**
- Handler 경로: `infra.aws.lambda_functions.trigger_etl.nih.nih_ingest.lambda_handler`
- Python 모듈 import를 위해 각 디렉토리에 `__init__.py` 파일이 필요
- `infra/`, `infra/aws/`, `infra/aws/lambda_functions/`, `infra/aws/lambda_functions/trigger_etl/`, `infra/aws/lambda_functions/trigger_etl/nih/` 디렉토리에 `__init__.py` 파일이 없음

**해결 방법:**

1. **prepare_build.sh에서 __init__.py 생성:**
   ```bash
   # NIH Lambda
   touch "$NIH_DIR/infra/__init__.py"
   touch "$NIH_DIR/infra/aws/__init__.py"
   touch "$NIH_DIR/infra/aws/lambda_functions/__init__.py"
   touch "$NIH_DIR/infra/aws/lambda_functions/trigger_etl/__init__.py"
   touch "$NIH_DIR/infra/aws/lambda_functions/trigger_etl/nih/__init__.py"
   
   # Protocols Lambda
   touch "$PROTOCOLS_DIR/infra/__init__.py"
   touch "$PROTOCOLS_DIR/infra/aws/__init__.py"
   touch "$PROTOCOLS_DIR/infra/aws/lambda_functions/__init__.py"
   touch "$PROTOCOLS_DIR/infra/aws/lambda_functions/trigger_etl/__init__.py"
   touch "$PROTOCOLS_DIR/infra/aws/lambda_functions/trigger_etl/protocols/__init__.py"
   ```

2. **BuildCommand에서 __init__.py 생성 (대안):**
   ```yaml
   BuildCommand: |
     mkdir -p infra/aws/lambda_functions/trigger_etl/nih
     touch infra/__init__.py
     touch infra/aws/__init__.py
     touch infra/aws/lambda_functions/__init__.py
     touch infra/aws/lambda_functions/trigger_etl/__init__.py
     touch infra/aws/lambda_functions/trigger_etl/nih/__init__.py
   ```

3. **수동 생성 (임시 해결책):**
   ```bash
   cd infra/aws/lambda_build
   
   # NIH
   touch nih/infra/__init__.py
   touch nih/infra/aws/__init__.py
   touch nih/infra/aws/lambda_functions/__init__.py
   touch nih/infra/aws/lambda_functions/trigger_etl/__init__.py
   touch nih/infra/aws/lambda_functions/trigger_etl/nih/__init__.py
   
   # Protocols
   touch protocols/infra/__init__.py
   touch protocols/infra/aws/__init__.py
   touch protocols/infra/aws/lambda_functions/__init__.py
   touch protocols/infra/aws/lambda_functions/trigger_etl/__init__.py
   touch protocols/infra/aws/lambda_functions/trigger_etl/protocols/__init__.py
   ```

**최종 해결:**
- `prepare_build.sh`에 `__init__.py` 파일 생성 로직 추가
- `lambdas-nih.yaml`과 `lambdas-protocols.yaml`의 BuildCommand에도 `__init__.py` 생성 로직 추가 (이중 안전장치)

---

### 오류 5-2: Nested Stack의 CodeUri가 S3로 변환되지 않음 ⚠️ **중요**

**증상:**
```
The following resource(s) failed to create: [NihIngestLambda, NihCleanseChunkLambda].
```

**원인:**
- Nested Stack 구조에서 `TemplateURL: lambdas-nih.yaml`로 로컬 파일을 직접 참조
- SAM `build`는 Nested Stack 템플릿의 `CodeUri`를 변환하지만 (`../lambda_build/nih` → `NihIngestLambda`)
- SAM `deploy`는 **루트 템플릿만 S3에 업로드**하고, Nested Stack 템플릿은 `.aws-sam/build/` 디렉토리의 상대 경로로 참조됨
- CloudFormation이 Nested Stack을 생성할 때, 로컬 경로(`lambdas-nih.yaml`)를 참조하거나, S3에 업로드되지 않은 템플릿을 참조하여 Lambda 코드를 찾을 수 없음

**문제 확인:**
```yaml
# skn18-final-infra-cf.yaml (원본)
NihLambdaStack:
  Type: AWS::CloudFormation::Stack
  Properties:
    TemplateURL: lambdas-nih.yaml  # ❌ 로컬 파일 경로

# .aws-sam/build/template.yaml (SAM 빌드 결과)
NihLambdaStack:
  Type: AWS::CloudFormation::Stack
  Properties:
    TemplateURL: NihLambdaStack/template.yaml  # ⚠️ 상대 경로 (S3 URL 아님)
```

**해결 방법:**

#### 옵션 1: SAM이 빌드한 템플릿 사용 (권장)

SAM `build`는 Nested Stack 템플릿을 `.aws-sam/build/` 디렉토리에 생성하고, `sam deploy`가 이를 자동으로 S3에 업로드합니다. 하지만 루트 템플릿에서 빌드 결과를 참조해야 합니다.

**현재 상태 확인:**
- ✅ SAM 빌드 결과: `.aws-sam/build/template.yaml`에서 `TemplateURL: NihLambdaStack/template.yaml`로 변환됨
- ✅ Nested Stack 템플릿: `.aws-sam/build/NihLambdaStack/template.yaml`에 `CodeUri: NihIngestLambda`로 변환됨
- ⚠️ **문제**: `sam deploy`가 Nested Stack 템플릿을 S3에 업로드하는지 확인 필요

**해결 방법 (최종):**

`sam deploy`는 Nested Stack 템플릿을 S3에 업로드하지만, Nested Stack 템플릿 내부의 `CodeUri`가 로컬 경로로 남아있을 수 있습니다. 따라서 **`sam package`를 사용하여 명시적으로 패키징**한 후 `aws cloudformation deploy`를 사용해야 합니다:

```bash
# 1. prepare_build.sh 실행 (필수)
cd infra/aws/lambda_build
./prepare_build.sh

# 2. SAM 빌드
cd ../cloudformation
rm -rf .aws-sam
sam build -t skn18-final-infra-cf.yaml

# 3. SAM 패키징 (중요: Nested Stack 템플릿과 CodeUri를 모두 S3 URL로 변환)
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

**또는 자동 배포 스크립트 사용:**
```bash
cd infra/aws/cloudformation
./deploy.sh
```

**참고:**
- ETL 데이터 버킷(`skn18-etl-data`)과는 별도로 SAM 배포용 버킷 사용 (자동 생성됨)
- `--resolve-s3`를 사용하면 SAM이 자동으로 `aws-sam-cli-managed-*` 형태의 버킷을 생성하거나 기존 버킷 사용
- `sam package`는 루트 템플릿과 모든 Nested Stack 템플릿, 그리고 모든 `CodeUri`를 S3 URL로 변환합니다

#### 옵션 2: 루트 템플릿에 Lambda 직접 선언

Nested Stack을 사용하지 않고 루트 템플릿에 모든 Lambda 함수를 직접 선언:
- 장점: SAM이 모든 `CodeUri`를 자동으로 S3 URL로 변환
- 단점: 템플릿이 커지고 관리가 복잡해짐

#### 옵션 3: AWS::Serverless::Application 사용

SAM의 `AWS::Serverless::Application` 리소스를 사용하여 Nested Stack을 관리:
```yaml
NihLambdaStack:
  Type: AWS::Serverless::Application
  Properties:
    Location: lambdas-nih.yaml
    Parameters:
      S3BucketName: !GetAtt CoreInfraStack.Outputs.EtlDataBucketName
      ...
```

**참고:**
- SAM은 `AWS::Serverless::Application`을 사용할 때 자동으로 템플릿을 S3에 업로드하고 URL로 변환
- 하지만 `AWS::CloudFormation::Stack`을 사용할 때는 수동으로 처리해야 할 수 있음

**현재 상태:**
- ✅ **`sam package` 후 확인 결과:**
  - `TemplateURL`이 S3 URL로 변환됨 ✅
  - Nested Stack 템플릿 내부의 `CodeUri`도 S3 URL로 변환됨 ✅
  - Handler 경로 정상: `infra.aws.lambda_functions.trigger_etl.nih.nih_ingest.lambda_handler` ✅
  - **S3에 업로드된 코드 패키지 확인 결과: `__init__.py` 파일들이 모두 포함됨 ✅**
- ⚠️ **하지만 여전히 Lambda 함수 생성 실패**
- **가능한 원인 (Handler 경로 문제는 해결됨):**
  1. Lambda 함수 코드 자체의 import 오류 (런타임 오류)
  2. 권한 문제 (Lambda 실행 역할이 S3에서 코드를 다운로드할 수 없음)
  3. Lambda Layer 문제 (Layer가 제대로 연결되지 않음)
  4. Lambda 함수 코드 패키지 크기 문제
  5. 다른 설정 문제 (Timeout, MemorySize 등)
- **추가 확인 필요**: 실제 CloudFormation 오류 메시지 확인 필요

**오류 로그 확인 방법:**

1. **중첩 스택의 상세 오류 확인 (가장 중요):**
   ```bash
   # deploy.log에서 스택 이름 확인 후 (예: skn18-final-infra-NihLambdaStack-1TUJLYYZ216WT)
   # 스택이 삭제되지 않았다면:
   aws cloudformation describe-stack-events \
     --stack-name skn18-final-infra-NihLambdaStack-1TUJLYYZ216WT \
     --region ap-northeast-2 \
     --max-items 50 \
     --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`].[Timestamp,LogicalResourceId,ResourceStatusReason]' \
     --output table
   
   # 스택이 삭제되었다면, 메인 스택에서 최근 이벤트 확인:
   aws cloudformation describe-stack-events \
     --stack-name skn18-final-infra \
     --region ap-northeast-2 \
     --max-items 100 \
     --query 'StackEvents[?contains(ResourceStatusReason, `NihIngestLambda`) || contains(ResourceStatusReason, `NihCleanseChunkLambda`)].{Time:Timestamp,Resource:LogicalResourceId,Status:ResourceStatus,Reason:ResourceStatusReason}' \
     --output table
   ```

2. **메인 스택의 이벤트 확인 (스택이 삭제된 경우):**
   ```bash
   # 메인 스택의 최근 이벤트 확인
   aws cloudformation describe-stack-events \
     --stack-name skn18-final-infra \
     --region ap-northeast-2 \
     --max-items 100 \
     --query 'StackEvents[?contains(ResourceStatusReason, `NihIngestLambda`) || contains(ResourceStatusReason, `NihCleanseChunkLambda`) || contains(ResourceStatusReason, `CREATE_FAILED`)].{Time:Timestamp,Resource:LogicalResourceId,Status:ResourceStatus,Reason:ResourceStatusReason}' \
     --output table
   ```

2. **다음 배포 시 실시간 로그 확인:**
   ```bash
   # 배포 시 상세 로그 출력
   sam deploy \
     --template-file packaged.yaml \
     --stack-name skn18-final-infra \
     --capabilities CAPABILITY_AUTO_EXPAND CAPABILITY_NAMED_IAM \
     --region ap-northeast-2 \
     --debug
   ```

3. **AWS 콘솔에서 확인:**
   - CloudFormation → `skn18-final-infra` 스택
   - Events 탭에서 최근 실패한 이벤트 확인
   - 실패한 중첩 스택을 클릭하여 상세 오류 확인

4. **배포 로그를 파일로 저장:**
   ```bash
   sam deploy \
     --template-file packaged.yaml \
     --stack-name skn18-final-infra \
     --capabilities CAPABILITY_AUTO_EXPAND CAPABILITY_NAMED_IAM \
     --region ap-northeast-2 \
     2>&1 | tee deploy.log
   ```

---

## 배포 체크리스트

배포 전 확인사항:

- [ ] `prepare_build.sh` 실행 완료
- [ ] Lambda Layer `requirements.txt` 파일 존재 확인 (심볼릭 링크 또는 실제 파일)
- [ ] Parameter Store 값 확인:
  - [ ] `/skn18/postgres-password` (SecureString 타입)
  - [ ] `/skn18/postgres-port` (String 타입)
  - [ ] `/skn18/key-name` (실제 키 페어 이름과 일치)
  - [ ] `/skn18/pgvector-ami-id` (AMI ID)
- [ ] SAM 빌드 성공:
  ```bash
  sam build -t skn18-final-infra-cf.yaml
  ```
- [ ] 빌드 아티팩트 크기 확인 (너무 크지 않은지):
  ```bash
  du -sh .aws-sam/build/*/
  ```
- [ ] **SAM 패키징 (중요!)**:
  ```bash
  sam package \
    --template-file .aws-sam/build/template.yaml \
    --output-template-file packaged.yaml \
    --resolve-s3 \
    --region ap-northeast-2
  ```
- [ ] 배포 명령어:
  ```bash
  aws cloudformation deploy \
    --template-file packaged.yaml \
    --stack-name skn18-final-infra \
    --capabilities CAPABILITY_AUTO_EXPAND \
    --region ap-northeast-2
  ```

**또는 자동 배포 스크립트 사용:**
```bash
cd infra/aws/cloudformation
./deploy.sh
```

---

## 참고 자료

- [AWS SAM 문서](https://docs.aws.amazon.com/serverless-application-model/)
- [CloudFormation 파라미터 타입](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/parameters-section-structure.html)
- [Lambda Layer 가이드](https://docs.aws.amazon.com/lambda/latest/dg/configuration-layers.html)
- [Packer 문서](https://www.packer.io/docs)

---

**작성일:** 2025-12-25  
**최종 업데이트:** 2025-12-25

