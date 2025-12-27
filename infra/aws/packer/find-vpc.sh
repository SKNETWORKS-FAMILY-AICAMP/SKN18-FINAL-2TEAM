#!/bin/bash
# VPC와 서브넷 찾기 스크립트

REGION="${1:-ap-northeast-2}"

echo "=== Finding available VPCs and Subnets in region: $REGION ==="
echo ""

# VPC 목록 조회
echo "1. Available VPCs:"
aws ec2 describe-vpcs \
  --region "$REGION" \
  --query 'Vpcs[*].[VpcId,CidrBlock,IsDefault,Tags[?Key==`Name`].Value|[0]]' \
  --output table

echo ""
echo "2. Available Public Subnets (with internet gateway route):"
# Public 서브넷 찾기 (Internet Gateway가 연결된 VPC의 서브넷)
aws ec2 describe-subnets \
  --region "$REGION" \
  --filters "Name=map-public-ip-on-launch,Values=true" \
  --query 'Subnets[*].[SubnetId,VpcId,CidrBlock,AvailabilityZone,Tags[?Key==`Name`].Value|[0]]' \
  --output table

echo ""
echo "=== Usage ==="
echo "Packer 빌드 시 VPC와 서브넷을 지정하려면:"
echo "  packer build -var 'vpc_id=vpc-xxxxx' -var 'subnet_id=subnet-xxxxx' packer.pkr.hcl"
echo ""
echo "또는 기본 VPC를 생성하려면:"
echo "  aws ec2 create-default-vpc --region $REGION"

