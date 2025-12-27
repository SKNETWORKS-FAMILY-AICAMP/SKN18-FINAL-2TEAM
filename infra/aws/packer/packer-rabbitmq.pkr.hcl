# Packer configuration for SKN18 RabbitMQ EC2 AMI
# This builds a custom AMI with Docker and RabbitMQ configuration pre-installed

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
  default     = "t2.micro"
}

variable "ami_name_prefix" {
  type        = string
  description = "Prefix for AMI name"
  default     = "skn18-rabbitmq-ami"
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
source "amazon-ebs" "skn18-rabbitmq" {
  ami_name      = "${var.ami_name_prefix}-${formatdate("YYYYMMDD-hhmmss", timestamp())}"
  instance_type = var.instance_type
  region        = var.aws_region
  
  # VPC와 서브넷 지정 (기본 VPC가 없는 경우 필수)
  vpc_id    = var.vpc_id != "" ? var.vpc_id : null
  subnet_id = var.subnet_id != "" ? var.subnet_id : null
  
  # VPC가 지정된 경우 Public IP 할당 (Public 서브넷인 경우)
  associate_public_ip_address = var.vpc_id != "" ? true : null

  # Source AMI: Amazon Linux 2023 (최신 버전)
  source_ami_filter {
    filters = {
      name                = "al2023-ami-*x86_64"
      root-device-type    = "ebs"
      virtualization-type = "hvm"
    }
    most_recent = true
    owners      = ["amazon"]
  }

  # SSH 접속 설정
  ssh_username = "ec2-user"
  ssh_timeout  = "10m"

  # 태그
  tags = {
    Name        = "${var.ami_name_prefix}"
    Project     = "SKN18"
    Component   = "rabbitmq-ec2"
    ManagedBy   = "Packer"
    BuildDate   = formatdate("YYYY-MM-DD hh:mm:ss ZZZ", timestamp())
  }
}

# Build 과정
build {
  name = "skn18-rabbitmq-ami"
  sources = [
    "source.amazon-ebs.skn18-rabbitmq"
  ]

  # Provisioner 1: 기본 업데이트 및 Docker 설치
  provisioner "shell" {
    inline = [
      "set -xe",
      "echo '=== Starting RabbitMQ AMI build process ==='",
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
      "# RabbitMQ 데이터 디렉토리 준비",
      "sudo mkdir -p /var/lib/rabbitmq",
      "sudo mkdir -p /var/log/rabbitmq",
      "sudo chown -R ec2-user:ec2-user /var/lib/rabbitmq",
      "sudo chown -R ec2-user:ec2-user /var/log/rabbitmq",
      "",
      "echo '=== Docker installation completed ==='"
    ]
  }

  # Provisioner 2: Docker 시작 스크립트 준비 (런타임에 실행)
  provisioner "shell" {
    inline = [
      "cat << 'SCRIPT_EOF' | sudo tee /usr/local/bin/start-rabbitmq-docker.sh > /dev/null",
      "#!/bin/bash",
      "set -xe",
      "",
      "# Docker 서비스 시작",
      "sudo systemctl start docker",
      "",
      "# 기존 컨테이너 정리",
      "sudo docker stop rabbitmq-final || true",
      "sudo docker rm -f rabbitmq-final || true",
      "",
      "# RabbitMQ 디렉토리 권한 확인",
      "sudo mkdir -p /var/lib/rabbitmq /var/log/rabbitmq",
      "sudo chown -R ec2-user:ec2-user /var/lib/rabbitmq",
      "sudo chown -R ec2-user:ec2-user /var/log/rabbitmq",
      "",
      "echo '=== RabbitMQ Docker container startup script created ==='",
      "SCRIPT_EOF",
      "sudo chmod +x /usr/local/bin/start-rabbitmq-docker.sh",
      "echo '=== Build completed successfully ==='"
    ]
  }

  # Provisioner 3: 최종 정리
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
    output     = "manifest-rabbitmq.json"
    strip_path = true
  }
}

