# Packer configuration for SKN18 Neo4j EC2 AMI
# This builds a custom AMI with Docker and Neo4j configuration pre-installed

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
  default     = "skn18-neo4j-ami"
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
source "amazon-ebs" "skn18-neo4j" {
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
    Component   = "neo4j-ec2"
    ManagedBy   = "Packer"
    BuildDate   = formatdate("YYYY-MM-DD hh:mm:ss ZZZ", timestamp())
  }
}

# Build 과정
build {
  name = "skn18-neo4j-ami"
  sources = [
    "source.amazon-ebs.skn18-neo4j"
  ]

  # Provisioner 1: 기본 업데이트 및 Docker 설치
  provisioner "shell" {
    inline = [
      "set -xe",
      "echo '=== Starting Neo4j AMI build process ==='",
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
      "# Neo4j 데이터 디렉토리 준비",
      "sudo mkdir -p /var/lib/neo4j/data",
      "sudo mkdir -p /var/lib/neo4j/logs",
      "sudo mkdir -p /var/lib/neo4j/plugins",
      "sudo mkdir -p /var/lib/neo4j/import",
      "sudo mkdir -p /var/lib/neo4j/config",
      "sudo chown -R ec2-user:ec2-user /var/lib/neo4j",
      "",
      "echo '=== Docker installation completed ==='"
    ]
  }

  # Provisioner 2: neo4j.conf 파일 복사
  provisioner "file" {
    source      = "../../neo4j/neo4j.conf"
    destination = "/tmp/neo4j.conf"
  }

  # Provisioner 3: init.cypher 파일 복사
  provisioner "file" {
    source      = "../../neo4j/init.cypher"
    destination = "/tmp/init.cypher"
  }

  # Provisioner 4: plugins 파일 개별 복사 (디렉토리 업로드는 Packer에서 문제가 있을 수 있음)
  provisioner "file" {
    source      = "../../neo4j/plugins/apoc.jar"
    destination = "/tmp/apoc.jar"
  }

  provisioner "file" {
    source      = "../../neo4j/plugins/graph-data-science.jar"
    destination = "/tmp/graph-data-science.jar"
  }

  # Provisioner 5: 파일들을 적절한 위치로 이동
  provisioner "shell" {
    inline = [
      "sudo mv /tmp/neo4j.conf /var/lib/neo4j/config/neo4j.conf",
      "sudo mv /tmp/init.cypher /var/lib/neo4j/config/init.cypher",
      "sudo mv /tmp/apoc.jar /var/lib/neo4j/plugins/apoc.jar",
      "sudo mv /tmp/graph-data-science.jar /var/lib/neo4j/plugins/graph-data-science.jar",
      "sudo chown -R ec2-user:ec2-user /var/lib/neo4j",
      "sudo chmod 644 /var/lib/neo4j/config/neo4j.conf",
      "sudo chmod 644 /var/lib/neo4j/config/init.cypher",
      "sudo chmod 644 /var/lib/neo4j/plugins/*.jar",
      "echo '=== Neo4j configuration files copied ==='"
    ]
  }

  # Provisioner 6: Docker 시작 스크립트 준비 (런타임에 실행)
  provisioner "shell" {
    inline = [
      "cat << 'SCRIPT_EOF' | sudo tee /usr/local/bin/start-neo4j-docker.sh > /dev/null",
      "#!/bin/bash",
      "set -xe",
      "",
      "# Docker 서비스 시작",
      "sudo systemctl start docker",
      "",
      "# 기존 컨테이너 정리",
      "sudo docker stop neo4j-final || true",
      "sudo docker rm -f neo4j-final || true",
      "",
      "# Neo4j 데이터 디렉토리 정리",
      "if [ -d /var/lib/neo4j/data/databases ]; then",
      "  echo '기존 Neo4j 데이터 디렉토리 발견, 백업 후 제거...'",
      "  sudo mv /var/lib/neo4j/data /var/lib/neo4j/data.backup.$(date +%Y%m%d_%H%M%S) || true",
      "  sudo mkdir -p /var/lib/neo4j/data",
      "fi",
      "",
      "# Neo4j 디렉토리 권한 확인",
      "sudo mkdir -p /var/lib/neo4j/{data,logs,plugins,import,config}",
      "sudo chown -R ec2-user:ec2-user /var/lib/neo4j",
      "",
      "echo '=== Neo4j Docker container startup script created ==='",
      "SCRIPT_EOF",
      "sudo chmod +x /usr/local/bin/start-neo4j-docker.sh",
      "echo '=== Build completed successfully ==='"
    ]
  }

  # Provisioner 7: 최종 정리
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
    output     = "manifest-neo4j.json"
    strip_path = true
  }
}

