# Neo4j Packer AMI 빌드 가이드

이 디렉토리는 **SKN18 Neo4j EC2 인스턴스를 위한 Golden AMI**를 빌드하는 Packer 설정을 포함합니다.

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
├── packer-neo4j.pkr.hcl       # Neo4j용 Packer 빌드 설정 파일
├── register-ami-neo4j.sh      # AMI ID를 Parameter Store에 등록하는 스크립트
└── README_packer_neo4j.md     # 이 파일

infra/neo4j/
├── neo4j.conf                 # Neo4j 설정 파일
├── init.cypher                # Neo4j 초기화 스크립트
└── plugins/                   # Neo4j 플러그인 (apoc, graph-data-science)
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

### 1. VPC와 Subnet 확인 (필수)

기본 VPC가 없는 경우, VPC와 Subnet ID를 먼저 확인해야 합니다:

```bash
# VPC 목록 확인
aws ec2 describe-vpcs --region ap-northeast-2 \
  --query 'Vpcs[*].[VpcId,CidrBlock,IsDefault,Tags[?Key==`Name`].Value|[0]]' \
  --output table

# Public Subnet 확인
aws ec2 describe-subnets --region ap-northeast-2 \
  --filters "Name=map-public-ip-on-launch,Values=true" \
  --query 'Subnets[*].[SubnetId,VpcId,CidrBlock,AvailabilityZone]' \
  --output table
```

또는 `find-vpc.sh` 스크립트 사용:
```bash
./find-vpc.sh ap-northeast-2
```

### 2. AMI 빌드

```bash
cd infra/aws/packer

# Packer 초기화 (필요한 플러그인 다운로드)
packer init packer-neo4j.pkr.hcl

# 빌드 실행 (VPC 지정 - 필수!)
packer build \
  -var 'vpc_id=vpc-xxxxxxxxxxxxx' \
  -var 'subnet_id=subnet-xxxxxxxxxxxxx' \
  packer-neo4j.pkr.hcl
```

**주의**: 기본 VPC가 없는 경우 VPC ID와 Subnet ID를 반드시 지정해야 합니다.

**빌드 옵션 지정:**
```bash
# Region 변경
packer build -var 'aws_region=us-east-1' packer-neo4j.pkr.hcl

# 인스턴스 타입 변경
packer build -var 'instance_type=t3.large' packer-neo4j.pkr.hcl

# AMI 이름 prefix 변경
packer build -var 'ami_name_prefix=my-custom-neo4j-ami' packer-neo4j.pkr.hcl
```

### 3. 빌드 결과 확인

빌드가 완료되면 다음과 같은 정보가 출력됩니다:

```
==> Builds finished. The artifacts of successful builds are shown below.
--> amazon-ebs.skn18-neo4j-ami: AMIs were created:
ap-northeast-2: ami-xxxxxxxxxxxxxxxxx

--> amazon-ebs.skn18-neo4j-ami: AMI tags were created:
--> amazon-ebs.skn18-neo4j-ami: AMI: ami-xxxxxxxxxxxxxxxxx
--> amazon-ebs.skn18-neo4j-ami:   Name: skn18-neo4j-ami
--> amazon-ebs.skn18-neo4j-ami:   Project: SKN18
...
```

**생성된 AMI ID를 복사하세요!** (예: `ami-0123456789abcdef0`)

### 4. Parameter Store에 AMI ID 등록

CloudFormation에서 사용할 수 있도록 Parameter Store에 AMI ID를 저장합니다:

```bash
# 생성된 AMI ID를 Parameter Store에 저장
./register-ami-neo4j.sh ami-xxxxxxxxxxxxxxxxx ap-northeast-2
```

또는 직접 AWS CLI 사용:

```bash
aws ssm put-parameter \
  --region ap-northeast-2 \
  --name "/skn18/neo4j-ami-id" \
  --type "String" \
  --value "ami-xxxxxxxxxxxxxxxxx" \
  --overwrite
```

### 5. Neo4j 비밀번호 등록 (필수)

```bash
aws ssm put-parameter \
  --region ap-northeast-2 \
  --name "/skn18/neo4j-password" \
  --type "SecureString" \
  --value "your-neo4j-password" \
  --overwrite
```

### 6. 인스턴스 타입 등록 (선택사항)

기본값이 없으므로 등록 필요:

```bash
aws ssm put-parameter \
  --region ap-northeast-2 \
  --name "/skn18/neo4j-instance-type" \
  --type "String" \
  --value "t3.large" \
  --overwrite
```

### 7. CloudFormation 배포

`neo4j-infra.yaml` 템플릿을 사용하여 Neo4j EC2 인스턴스를 배포합니다:

```bash
cd infra/aws/cloudformation

# SAM 빌드 및 배포
sam build -t neo4j-infra.yaml
sam deploy --guided  # 첫 배포 시
# 또는
sam deploy  # 이미 설정된 경우
```

## 📦 AMI에 포함된 내용

빌드된 AMI에는 다음이 포함됩니다:

1. **Docker 설치 및 설정**
   - Docker 서비스 설치 및 활성화
   - `ec2-user`가 `docker` 그룹에 추가됨 (sudo 없이 docker 사용 가능)

2. **Neo4j 디렉토리 구조 준비**
   - `/var/lib/neo4j/data` - 데이터 저장소
   - `/var/lib/neo4j/logs` - 로그 파일
   - `/var/lib/neo4j/plugins` - 플러그인
   - `/var/lib/neo4j/import` - 데이터 임포트
   - `/var/lib/neo4j/config` - 설정 파일

3. **Neo4j 설정 파일**
   - `/var/lib/neo4j/config/neo4j.conf` - Neo4j 설정 파일
   - `/var/lib/neo4j/config/init.cypher` - 초기 스키마 설정
   - `/var/lib/neo4j/plugins/` - APOC 및 Graph Data Science 플러그인

## 🔄 CloudFormation에서 사용 방법

Neo4j EC2 인스턴스는 `neo4j-infra.yaml` 템플릿을 통해 배포됩니다:

```yaml
Neo4jInstance:
  Type: AWS::EC2::Instance
  Properties:
    ImageId: !Ref Neo4jAmiId  # Packer로 빌드된 AMI ID
    UserData:
      # Docker 컨테이너 실행 (neo4j:5.15.0)
      # Parameter Store에서 비밀번호 가져오기
      # 볼륨 마운트 및 설정 파일 적용
```

## 🔍 AMI 관리

### AMI 목록 조회

```bash
# 특정 이름의 AMI 검색
aws ec2 describe-images \
  --region ap-northeast-2 \
  --owners self \
  --filters "Name=name,Values=skn18-neo4j-ami-*" \
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

## 🐛 문제 해결

### 빌드 실패 시

1. **권한 오류**: IAM 권한 확인
2. **네트워크 오류**: 보안 그룹 및 서브넷 확인
3. **빌드 시간 초과**: `instance_type`을 더 큰 타입으로 변경

### 디버깅

```bash
# Packer 디버그 모드
PACKER_LOG=1 packer build packer-neo4j.pkr.hcl

# 특정 빌드 단계만 실행 (테스트용)
packer build -only=amazon-ebs.skn18-neo4j packer-neo4j.pkr.hcl
```

### Neo4j 컨테이너 문제

EC2 인스턴스에 SSH 접속 후:

```bash
# 컨테이너 상태 확인
docker ps -a

# 로그 확인
docker logs neo4j-final

# 컨테이너 재시작
docker restart neo4j-final
```

## 📝 참고 자료

- [Packer 공식 문서](https://www.packer.io/docs)
- [Packer AWS Builder 문서](https://www.packer.io/docs/builders/amazon)
- [Neo4j Docker 문서](https://neo4j.com/docs/operations-manual/current/docker/)
- [Neo4j Configuration](https://neo4j.com/docs/operations-manual/current/configuration/)

