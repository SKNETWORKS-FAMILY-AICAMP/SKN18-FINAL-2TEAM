# RabbitMQ Packer AMI 빌드 가이드

이 디렉토리는 **SKN18 RabbitMQ EC2 인스턴스를 위한 Golden AMI**를 빌드하는 Packer 설정을 포함합니다.

## 📋 개요

기존 UserData 스크립트 대신 **Packer로 미리 구성된 AMI**를 사용하면:

- ✅ **빠른 인스턴스 시작**: Docker 설치 및 설정이 이미 완료되어 시작 시간 단축
- ✅ **일관성 보장**: 동일한 AMI로 배포하여 환경 일관성 확보
- ✅ **테스트 용이**: 로컬에서 AMI를 먼저 테스트 가능
- ✅ **버전 관리**: AMI 태그를 통한 버전 관리 및 롤백 가능
- ✅ **보안**: 빌드 시점에 검증된 설정만 포함

## 📁 파일 구조

```
infra/aws/packer/
├── packer-rabbitmq.pkr.hcl          # RabbitMQ용 Packer 빌드 설정 파일
├── register-ami-rabbitmq.sh         # AMI ID를 Parameter Store에 등록하는 스크립트
├── find-vpc.sh                      # VPC와 Subnet을 찾는 스크립트
├── get-vpc-for-packer.sh            # Packer 빌드용 VPC/Subnet 자동 찾기 스크립트
└── README_packer_rabbitmq.md        # 이 파일
```

## 🔧 사전 요구사항

### 1. Packer 설치

**macOS (권장):**
```bash
brew tap hashicorp/tap
brew install hashicorp/tap/packer
```

**Linux:**
```bash
curl -fsSL https://apt.releases.hashicorp.com/gpg | sudo apt-key add -
sudo apt-add-repository "deb [arch=amd64] https://apt.releases.hashicorp.com $(lsb_release -cs) main"
sudo apt-get update && sudo apt-get install packer
```

**설치 확인:**
```bash
packer version
```

### 2. AWS 자격 증명 설정

Packer는 AWS CLI와 동일한 방식으로 자격 증명을 사용합니다:

```bash
# AWS CLI 자격 증명 설정
aws configure
# 또는 환경 변수
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_REGION="ap-northeast-2"
```

### 3. IAM 권한 확인

Packer를 실행하는 AWS 계정/사용자는 다음 권한이 필요합니다:

- `ec2:DescribeImages`
- `ec2:CopyImage`
- `ec2:CreateImage`
- `ec2:RunInstances`
- `ec2:TerminateInstances`
- `ec2:CreateTags`
- `ec2:DescribeInstances`
- `ec2:CreateSnapshot`
- `ec2:DeleteSnapshot`

## 🚀 사용 방법

### 1. VPC ID와 Subnet ID 찾기

Packer 빌드 전에 VPC ID와 Subnet ID를 확인해야 합니다.

#### 방법 1: find-vpc.sh 스크립트 사용 (가장 간단)

```bash
cd infra/aws/packer
./find-vpc.sh ap-northeast-2
```

출력 예시:
```
=== Finding available VPCs and Subnets in region: ap-northeast-2 ===

1. Available VPCs:
----------------------------------------------------------------
|                         DescribeVpcs                         |
+------------------------+--------------+--------+-------------+
|  vpc-0bfdde3d0d68a673d |  10.0.0.0/16 |  False |  skn18-vpc  |
+------------------------+--------------+--------+-------------+

2. Available Public Subnets (with internet gateway route):
------------------------------------------------------------------------------------------------------------------
|                                                 DescribeSubnets                                                |
+--------------------------+------------------------+--------------+-------------------+-------------------------+
|  subnet-056614abe2d000a0c|  vpc-0bfdde3d0d68a673d |  10.0.1.0/24 |  ap-northeast-2a  |  skn18-public-subnet-1  |
|  subnet-0cc2f43e09a0d4aac|  vpc-0bfdde3d0d68a673d |  10.0.2.0/24 |  ap-northeast-2b  |  skn18-public-subnet-2  |
+--------------------------+------------------------+--------------+-------------------+-------------------------+
```

#### 방법 2: get-vpc-for-packer.sh 스크립트 사용 (자동화)

```bash
cd infra/aws/packer
./get-vpc-for-packer.sh ap-northeast-2
```

이 스크립트는 CloudFormation 스택에서 자동으로 VPC/Subnet을 찾아서 Packer 빌드 명령어를 출력합니다.

#### 방법 3: CloudFormation 스택에서 가져오기

```bash
# CloudFormation 스택 이름 확인
aws cloudformation list-stacks \
  --region ap-northeast-2 \
  --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
  --query "StackSummaries[?contains(StackName, 'CoreInfra') || contains(StackName, 'skn18')].StackName" \
  --output table

# VPC ID와 Subnet ID 가져오기
STACK_NAME="skn18-final-infra-cf-CoreInfraStack-xxxxx"  # 실제 스택 이름으로 변경

VPC_ID=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region ap-northeast-2 \
  --query 'Stacks[0].Outputs[?OutputKey==`VpcId`].OutputValue' \
  --output text)

SUBNET_ID=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region ap-northeast-2 \
  --query 'Stacks[0].Outputs[?OutputKey==`SubnetId`].OutputValue' \
  --output text)

echo "VPC ID: $VPC_ID"
echo "Subnet ID: $SUBNET_ID"
```

#### Subnet이 2개인 이유

CloudFormation 템플릿에서 두 개의 Public Subnet을 생성합니다:

1. **skn18-public-subnet-1** (첫 번째 서브넷)
   - 가용 영역: `ap-northeast-2a`
   - CIDR: `10.0.1.0/24`

2. **skn18-public-subnet-2** (두 번째 서브넷)
   - 가용 영역: `ap-northeast-2b`
   - CIDR: `10.0.2.0/24`

**이유:**
- ✅ **고가용성(HA)**: 서로 다른 가용 영역에 배치하여 단일 AZ 장애에 대비
- ✅ **ALB/로드 밸런서**: 여러 서브넷에 타겟을 분산 배치
- ✅ **확장성**: 여러 인스턴스를 여러 AZ에 배치 가능

**Packer 빌드 시**: Packer는 단일 인스턴스만 빌드하므로, **두 서브넷 중 아무거나 사용해도 됩니다**. 일반적으로 **첫 번째 서브넷**을 사용하는 것을 권장합니다.

### 2. AMI 빌드

```bash
cd infra/aws/packer

# Packer 초기화 (필요한 플러그인 다운로드)
packer init packer-rabbitmq.pkr.hcl

# 빌드 실행 (기본 VPC 사용)
packer build packer-rabbitmq.pkr.hcl

# 또는 VPC 지정해서 빌드 실행 (권장)
packer build \
  -var 'vpc_id=vpc-0bfdde3d0d68a673d' \
  -var 'subnet_id=subnet-056614abe2d000a0c' \
  packer-rabbitmq.pkr.hcl
```

**실제 사용 예시:**
```bash
# find-vpc.sh로 확인한 값 사용
packer build \
  -var 'vpc_id=vpc-0bfdde3d0d68a673d' \
  -var 'subnet_id=subnet-056614abe2d000a0c' \
  packer-rabbitmq.pkr.hcl
```

**빌드 옵션 지정:**
```bash
# Region 변경
packer build -var 'aws_region=us-east-1' packer-rabbitmq.pkr.hcl

# 인스턴스 타입 변경
packer build -var 'instance_type=t3.large' packer-rabbitmq.pkr.hcl

# AMI 이름 prefix 변경
packer build -var 'ami_name_prefix=my-custom-rabbitmq-ami' packer-rabbitmq.pkr.hcl
```

### 3. 빌드 결과 확인

빌드가 완료되면 다음과 같은 정보가 출력됩니다:

```
==> Builds finished. The artifacts of successful builds are shown below.
--> amazon-ebs.skn18-rabbitmq-ami: AMIs were created:
ap-northeast-2: ami-xxxxxxxxxxxxxxxxx

--> amazon-ebs.skn18-rabbitmq-ami: AMI tags were created:
--> amazon-ebs.skn18-rabbitmq-ami: AMI: ami-xxxxxxxxxxxxxxxxx
--> amazon-ebs.skn18-rabbitmq-ami:   Name: skn18-rabbitmq-ami
--> amazon-ebs.skn18-rabbitmq-ami:   Project: SKN18
...
```

**생성된 AMI ID를 복사하세요!** (예: `ami-0123456789abcdef0`)

### 4. Parameter Store에 AMI ID 등록

CloudFormation에서 사용할 수 있도록 Parameter Store에 AMI ID를 저장합니다:

```bash
# 방법 1: 수동으로 등록
aws ssm put-parameter \
  --region ap-northeast-2 \
  --name "/skn18/rabbitmq-ami-id" \
  --type "String" \
  --value "ami-xxxxxxxxxxxxxxxxx" \
  --overwrite

# 방법 2: register-ami-rabbitmq.sh 스크립트 사용
./register-ami-rabbitmq.sh ami-xxxxxxxxxxxxxxxxx
```

### 5. RabbitMQ 설정 파라미터 등록

```bash
# RabbitMQ 사용자명 저장
aws ssm put-parameter \
  --region ap-northeast-2 \
  --name "/skn18/rabbitmq-user" \
  --type "String" \
  --value "admin" \
  --overwrite

# RabbitMQ 비밀번호 저장 (SecureString)
aws ssm put-parameter \
  --region ap-northeast-2 \
  --name "/skn18/rabbitmq-password" \
  --type "SecureString" \
  --value "your-secure-password" \
  --overwrite

# 인스턴스 타입 저장
aws ssm put-parameter \
  --region ap-northeast-2 \
  --name "/skn18/rabbitmq-instance-type" \
  --type "String" \
  --value "t3.medium" \
  --overwrite
```

## 📦 AMI에 포함된 내용

빌드된 AMI에는 다음이 포함됩니다:

1. **Docker 설치 및 설정**
   - Docker 서비스 설치 및 활성화
   - `ec2-user`가 `docker` 그룹에 추가됨 (sudo 없이 docker 사용 가능)

2. **RabbitMQ 데이터 디렉토리 준비**
   - `/var/lib/rabbitmq` 디렉토리 생성 및 권한 설정
   - `/var/log/rabbitmq` 디렉토리 생성 및 권한 설정

3. **Docker 시작 스크립트**
   - `/usr/local/bin/start-rabbitmq-docker.sh` 스크립트 준비
   - 런타임에 RabbitMQ 컨테이너를 시작하는데 사용

## 🔄 CloudFormation에서 사용 방법

### 기존 방식 (UserData 사용)

```yaml
RabbitMQInstance:
  Type: AWS::EC2::Instance
  Properties:
    ImageId: !Ref RabbitMQAmiId
    UserData:
      Fn::Base64: !Sub |
        #!/bin/bash
        # Docker 설치 및 설정... (많은 스크립트)
```

### 새로운 방식 (AMI 사용)

```yaml
RabbitMQInstance:
  Type: AWS::EC2::Instance
  Properties:
    ImageId: !Ref RabbitMQAmiId  # Packer로 빌드된 AMI ID
    UserData:
      Fn::Base64: !Sub |
        #!/bin/bash
        # 간단한 런타임 설정만 수행
        systemctl start docker
        docker run -d \
          --name rabbitmq-final \
          -e RABBITMQ_DEFAULT_USER="$RABBITMQ_USER" \
          -e RABBITMQ_DEFAULT_PASS="$RABBITMQ_PASSWORD" \
          -p 5672:5672 \
          -p 15672:15672 \
          -v /var/lib/rabbitmq:/var/lib/rabbitmq \
          -v /var/log/rabbitmq:/var/log/rabbitmq \
          --restart unless-stopped \
          rabbitmq:3.13-management-alpine
```

## 🔍 AMI 관리

### AMI 목록 조회

```bash
# 특정 이름의 AMI 검색
aws ec2 describe-images \
  --region ap-northeast-2 \
  --owners self \
  --filters "Name=name,Values=skn18-rabbitmq-ami-*" \
  --query 'Images[*].[ImageId,CreationDate,Name]' \
  --output table
```

### AMI 삭제

```bash
# AMI 삭제 (스냅샷은 별도로 삭제 필요)
aws ec2 deregister-image --region ap-northeast-2 --image-id ami-xxxxxxxxxxxxxxxxx

# 연결된 스냅샷 삭제
aws ec2 delete-snapshot --region ap-northeast-2 --snapshot-id snap-xxxxxxxxxxxxxxxxx
```

### AMI 공유

다른 AWS 계정과 AMI를 공유하려면:

```bash
aws ec2 modify-image-attribute \
  --region ap-northeast-2 \
  --image-id ami-xxxxxxxxxxxxxxxxx \
  --launch-permission "Add=[{UserId=123456789012}]"
```

## 🐛 문제 해결

### 빌드 실패 시

1. **권한 오류**: IAM 권한 확인
2. **네트워크 오류**: 보안 그룹 및 서브넷 확인
3. **빌드 시간 초과**: `instance_type`을 더 큰 타입으로 변경

### 디버깅

```bash
# Packer 디버그 모드
PACKER_LOG=1 packer build packer-rabbitmq.pkr.hcl

# 특정 빌드 단계만 실행 (테스트용)
packer build -only=amazon-ebs.skn18-rabbitmq packer-rabbitmq.pkr.hcl
```

## 📝 참고 자료

- [Packer 공식 문서](https://www.packer.io/docs)
- [Packer AWS Builder 문서](https://www.packer.io/docs/builders/amazon)
- [Amazon Linux 2023 AMI](https://aws.amazon.com/linux/amazon-linux-2023/)
- [RabbitMQ Docker 이미지](https://hub.docker.com/_/rabbitmq)

