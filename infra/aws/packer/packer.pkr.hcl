# Packer configuration for SKN18 pgvector EC2 AMI
# This builds a custom AMI with Docker and PostgreSQL init.sql pre-installed

# Packer 플러그인 선언 (필수)
packer {
  required_plugins {
    amazon = {
      version = ">= 1.0.0"
      source  = "github.com/hashicorp/amazon"
    }
  }
}

variable "aws_region" {
  type        = string
  description = "AWS region where AMI will be built"
  default     = "ap-northeast-2"
}

variable "instance_type" {
  type        = string
  description = "EC2 instance type for building AMI (t2.micro or t3.micro for Free Tier)"
  default     = "t2.micro"  # Free Tier 호환, 빌드 시간이 더 걸릴 수 있음
  # 대안: t3.micro (Free Tier 호환, 더 빠름), t3.small (Free Tier 아님, 더 빠름)
}

variable "ami_name_prefix" {
  type        = string
  description = "Prefix for AMI name"
  default     = "skn18-pgvector-ami"
}

variable "vpc_id" {
  type        = string
  description = "VPC ID where Packer will build the AMI (optional, will use default VPC if not specified)"
  default     = ""
}

variable "subnet_id" {
  type        = string
  description = "Subnet ID where Packer will launch the instance (optional, will use default subnet if not specified)"
  default     = ""
}

# Source AMI: Amazon Linux 2023 (latest)
source "amazon-ebs" "skn18-pgvector" {
  ami_name      = "${var.ami_name_prefix}-${formatdate("YYYYMMDD-hhmmss", timestamp())}"
  instance_type = var.instance_type
  region        = var.aws_region
  
  # VPC와 서브넷 지정 (기본 VPC가 없는 경우 필수)
  vpc_id    = var.vpc_id != "" ? var.vpc_id : null
  subnet_id = var.subnet_id != "" ? var.subnet_id : null
  
  # VPC가 지정된 경우 Public IP 할당 (Public 서브넷인 경우)
  associate_public_ip_address = var.vpc_id != "" ? true : null

  # Source AMI: Amazon Linux 2023 (최신 버전)
  # 방법 1: 필터 사용 (동적으로 최신 AMI 찾기)
  # 방법 2: 직접 AMI ID 지정 (더 확실함, 아래 주석 해제 후 사용)
  
  # 방법 1: 필터 패턴 사용
  source_ami_filter {
    filters = {
      name                = "al2023-ami-*x86_64"
      root-device-type    = "ebs"
      virtualization-type = "hvm"
    }
    most_recent = true
    owners      = ["amazon"]
  }
  
  # 방법 2: 직접 AMI ID 지정 (필터가 작동하지 않을 경우 아래 주석 해제하고 위의 source_ami_filter는 주석 처리)
  # 확인된 AMI ID: ami-0a04a4c757a2f0593 (al2023-ami-ecs-hvm-2023.0.20251217-kernel-6.1-x86_64)
  # source_ami = "ami-0a04a4c757a2f0593"

  # SSH 접속 설정
  ssh_username = "ec2-user"
  ssh_timeout  = "10m"

  # 태그
  tags = {
    Name        = "${var.ami_name_prefix}"
    Project     = "SKN18"
    Component   = "pgvector-ec2"
    ManagedBy   = "Packer"
    BuildDate   = formatdate("YYYY-MM-DD hh:mm:ss ZZZ", timestamp())
  }

  # IAM 인스턴스 프로파일 (선택사항 - 더 많은 권한이 필요하면 추가)
  # iam_instance_profile = "packer-builder-profile"
}

# Build 과정
build {
  name = "skn18-pgvector-ami"
  sources = [
    "source.amazon-ebs.skn18-pgvector"
  ]

  # Provisioner 1: 기본 업데이트 및 Docker 설치
  provisioner "shell" {
    inline = [
      "set -xe",
      "echo '=== Starting AMI build process ==='",
      "",
      "# 기본 업데이트",
      "sudo dnf update -y",
      "",
      "# Docker 설치",
      "sudo dnf install -y docker",
      "sudo systemctl enable docker",
      "",
      "# ec2-user를 docker 그룹에 추가",
      "sudo usermod -aG docker ec2-user",
      "",
      "# PostgreSQL 데이터 디렉토리 준비",
      "sudo mkdir -p /var/lib/postgresql",
      "sudo chown ec2-user:ec2-user /var/lib/postgresql",
      "",
      "echo '=== Docker installation completed ==='"
    ]
  }

  # Provisioner 2: init.sql 파일 복사
  provisioner "file" {
    source      = "init.sql"
    destination = "/tmp/init.sql"
  }

  # Provisioner 3: init.sql을 적절한 위치로 이동
  provisioner "shell" {
    inline = [
      "sudo mv /tmp/init.sql /home/ec2-user/init.sql",
      "sudo chown ec2-user:ec2-user /home/ec2-user/init.sql",
      "sudo chmod 644 /home/ec2-user/init.sql",
      "echo '=== init.sql file copied ==='"
    ]
  }

  # Provisioner 4: Docker 시작 스크립트 준비 (런타임에 실행)
  provisioner "shell" {
    inline = [
      "cat << 'SCRIPT_EOF' | sudo tee /usr/local/bin/start-pgvector-docker.sh > /dev/null",
      "#!/bin/bash",
      "set -xe",
      "",
      "# Docker 서비스 시작",
      "sudo systemctl start docker",
      "",
      "# 기존 컨테이너 정리",
      "sudo docker stop pg-db-final || true",
      "sudo docker rm -f pg-db-final || true",
      "",
      "# PostgreSQL 데이터 디렉토리 정리 (18+ 호환)",
      "if [ -d /var/lib/postgresql/data ]; then",
      "  echo '기존 PostgreSQL 데이터 디렉토리 발견, 백업 후 제거...'",
      "  sudo mv /var/lib/postgresql/data /var/lib/postgresql/data.backup.$(date +%Y%m%d_%H%M%S) || true",
      "fi",
      "",
      "# PostgreSQL 18+ 형식에 맞게 디렉토리 준비",
      "sudo mkdir -p /var/lib/postgresql",
      "sudo chown ec2-user:ec2-user /var/lib/postgresql",
      "",
      "echo '=== Docker container startup script created ==='",
      "SCRIPT_EOF",
      "sudo chmod +x /usr/local/bin/start-pgvector-docker.sh",
      "echo '=== Build completed successfully ==='"
    ]
  }

  # Provisioner 5: 최종 정리
  provisioner "shell" {
    inline = [
      "# Docker 서비스 중지 (AMI에는 설치만 되어있고 실행 중이지 않음)",
      "sudo systemctl stop docker || true",
      "",
      "# 임시 파일 정리",
      "sudo rm -rf /tmp/* /var/tmp/* || true",
      "",
      "echo '=== AMI build finished ==='"
    ]
  }

  # Post-processor: AMI 태그 추가
  post-processor "manifest" {
    output     = "manifest.json"
    strip_path = true
  }
}

