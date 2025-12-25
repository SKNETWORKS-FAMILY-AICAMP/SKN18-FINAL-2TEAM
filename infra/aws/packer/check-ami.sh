#!/bin/bash
# Amazon Linux 2023 AMI 확인 스크립트

REGION="${1:-ap-northeast-2}"

echo "=== Checking available Amazon Linux 2023 AMIs in region: $REGION ==="
echo ""

# 방법 1: AWS CLI로 직접 확인
echo "1. Using AWS CLI to list AL2023 AMIs:"
aws ec2 describe-images \
  --region "$REGION" \
  --owners amazon \
  --filters \
    "Name=name,Values=al2023-ami-*" \
    "Name=architecture,Values=x86_64" \
    "Name=root-device-type,Values=ebs" \
    "Name=virtualization-type,Values=hvm" \
  --query 'Images | sort_by(@, &CreationDate) | [-1].[ImageId,Name,CreationDate]' \
  --output table

echo ""
echo "=== Latest AL2023 AMI ID ==="
LATEST_AMI=$(aws ec2 describe-images \
  --region "$REGION" \
  --owners amazon \
  --filters \
    "Name=name,Values=al2023-ami-*" \
    "Name=architecture,Values=x86_64" \
    "Name=root-device-type,Values=ebs" \
    "Name=virtualization-type,Values=hvm" \
  --query 'Images | sort_by(@, &CreationDate) | [-1].ImageId' \
  --output text)

if [ -n "$LATEST_AMI" ] && [ "$LATEST_AMI" != "None" ]; then
  echo "Latest AMI ID: $LATEST_AMI"
  echo ""
  echo "To use this AMI directly in packer.pkr.hcl, replace source_ami_filter with:"
  echo "  source_ami = \"$LATEST_AMI\""
else
  echo "No AMI found. Please check your AWS credentials and region."
fi

