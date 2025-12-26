# Packer AMI 빌드 가이드

이 디렉토리는 **SKN18 pgvector EC2 인스턴스를 위한 Golden AMI**를 빌드하는 Packer 설정을 포함합니다.

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
├── packer.pkr.hcl       # Packer 빌드 설정 파일
├── init.sql             # PostgreSQL 초기화 스크립트 (infra/db/init.sql과 동일)
└── README_packer.md     # 이 파일
```

## 🔧 사전 요구사항

### 1. Packer 설치

**macOS (권장):**
```bash
# 방법 1: HashiCorp tap을 통한 설치 (권장)
brew tap hashicorp/tap
brew install hashicorp/tap/packer

# 방법 2: 직접 바이너리 다운로드
# https://developer.hashicorp.com/packer/downloads 에서 다운로드
# 또는
brew install --cask packer
```

**Linux:**
```bash
# HashiCorp 공식 저장소 추가
curl -fsSL https://apt.releases.hashicorp.com/gpg | sudo apt-key add -
sudo apt-add-repository "deb [arch=amd64] https://apt.releases.hashicorp.com $(lsb_release -cs) main"
sudo apt-get update && sudo apt-get install packer
```

**Windows:**
[공식 다운로드 페이지](https://developer.hashicorp.com/packer/downloads)에서 다운로드 또는 Chocolatey 사용:
```bash
choco install packer
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

### 1. AMI 빌드

```bash
cd infra/aws/packer

# Packer 초기화 (필요한 플러그인 다운로드)
packer init packer.pkr.hcl

# 빌드 실행
packer build packer.pkr.hcl
# or vpc 지정해서 빌드 실행
packer build \
  -var 'vpc_id=vpc-0f1b51bb58b066269' \
  -var 'subnet_id=subnet-04907324da7aa7635' \
  packer.pkr.hcl
```

**빌드 옵션 지정:**
```bash
# Region 변경
packer build -var 'aws_region=us-east-1' packer.pkr.hcl

# 인스턴스 타입 변경
packer build -var 'instance_type=t3.large' packer.pkr.hcl

# AMI 이름 prefix 변경
packer build -var 'ami_name_prefix=my-custom-ami' packer.pkr.hcl
```

### 2. 빌드 결과 확인

빌드가 완료되면 다음과 같은 정보가 출력됩니다:

```
==> Builds finished. The artifacts of successful builds are shown below.
--> amazon-ebs.skn18-pgvector-ami: AMIs were created:
ap-northeast-2: ami-xxxxxxxxxxxxxxxxx

--> amazon-ebs.skn18-pgvector-ami: AMI tags were created:
--> amazon-ebs.skn18-pgvector-ami: AMI: ami-xxxxxxxxxxxxxxxxx
--> amazon-ebs.skn18-pgvector-ami:   Name: skn18-pgvector-ami
--> amazon-ebs.skn18-pgvector-ami:   Project: SKN18
...
```

**생성된 AMI ID를 복사하세요!** (예: `ami-0123456789abcdef0`)

### 3. Parameter Store에 AMI ID 등록

CloudFormation에서 사용할 수 있도록 Parameter Store에 AMI ID를 저장합니다:

```bash
# 생성된 AMI ID를 Parameter Store에 저장
aws ssm put-parameter \
  --region ap-northeast-2 \
  --name "/skn18/pgvector-ami-id" \
  --type "String" \
  --value "ami-xxxxxxxxxxxxxxxxx" \
  --overwrite
```

### 4. CloudFormation 템플릿 업데이트

`core-infra.yaml`의 `LatestAmiId` Parameter가 이미 Parameter Store를 참조하도록 설정되어 있습니다:

```yaml
LatestAmiId:
  Type: "AWS::SSM::Parameter::Value<AWS::EC2::Image::Id>"
  Default: "/skn18/pgvector-ami-id"  # ← 여기를 업데이트하거나
  Description: "AMI ID for pgvector EC2 instance"
```

기본값을 변경하지 않았다면 위 명령어로 `/skn18/pgvector-ami-id`에 저장하면 자동으로 사용됩니다.

## 📦 AMI에 포함된 내용

빌드된 AMI에는 다음이 포함됩니다:

1. **Docker 설치 및 설정**
   - Docker 서비스 설치 및 활성화
   - `ec2-user`가 `docker` 그룹에 추가됨 (sudo 없이 docker 사용 가능)

2. **PostgreSQL 데이터 디렉토리 준비**
   - `/var/lib/postgresql` 디렉토리 생성 및 권한 설정

3. **init.sql 파일**
   - `/home/ec2-user/init.sql`에 pgvector 초기화 스크립트 포함
   - `docker-compose.yml`과 동일한 스키마

4. **Docker 시작 스크립트**
   - `/usr/local/bin/start-pgvector-docker.sh` 스크립트 준비
   - 런타임에 PostgreSQL 컨테이너를 시작하는데 사용

## 🔄 CloudFormation에서 사용 방법

### 기존 방식 (UserData 사용)

```yaml
PgVectorInstance:
  Type: AWS::EC2::Instance
  Properties:
    ImageId: !Ref LatestAmiId
    UserData:
      Fn::Base64: !Sub |
        #!/bin/bash
        # Docker 설치 및 설정... (많은 스크립트)
```

### 새로운 방식 (AMI 사용)

```yaml
PgVectorInstance:
  Type: AWS::EC2::Instance
  Properties:
    ImageId: !Ref LatestAmiId  # Packer로 빌드된 AMI ID
    UserData:
      Fn::Base64: !Sub |
        #!/bin/bash
        # 간단한 런타임 설정만 수행
        /usr/local/bin/start-pgvector-docker.sh || true
        
        # 환경 변수 기반 Docker 컨테이너 실행
        docker run -d \
          --name pg-db-final \
          -e POSTGRES_DB=${PostgresDbName} \
          -e POSTGRES_USER=${PostgresUser} \
          -e POSTGRES_PASSWORD=${PostgresPassword} \
          -p ${PostgresPort}:5432 \
          -v /var/lib/postgresql:/var/lib/postgresql \
          -v /home/ec2-user/init.sql:/docker-entrypoint-initdb.d/init.sql \
          --restart unless-stopped \
          pgvector/pgvector:pg18
```

## 🔍 AMI 관리

### AMI 목록 조회

```bash
# 특정 이름의 AMI 검색
aws ec2 describe-images \
  --region ap-northeast-2 \
  --owners self \
  --filters "Name=name,Values=skn18-pgvector-ami-*" \
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
PACKER_LOG=1 packer build packer.pkr.hcl

# 특정 빌드 단계만 실행 (테스트용)
packer build -only=amazon-ebs.skn18-pgvector packer.pkr.hcl
```

## 📝 참고 자료

- [Packer 공식 문서](https://www.packer.io/docs)
- [Packer AWS Builder 문서](https://www.packer.io/docs/builders/amazon)
- [Amazon Linux 2023 AMI](https://aws.amazon.com/linux/amazon-linux-2023/)

