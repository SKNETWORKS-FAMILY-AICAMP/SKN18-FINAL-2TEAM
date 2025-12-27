#!/bin/bash
# Packer 빌드에 사용할 VPC ID와 Subnet ID를 찾아서 출력하는 스크립트
# CloudFormation 스택에서 가져오거나, 직접 조회할 수 있습니다.

REGION="${1:-ap-northeast-2}"
STACK_NAME="${2:-skn18-final-infra-cf-CoreInfraStack-xxxxx}"  # CloudFormation 스택 이름 (선택사항)

echo "=== Finding VPC and Subnet for Packer Build ==="
echo "Region: $REGION"
echo ""

# 방법 1: CloudFormation 스택에서 가져오기 (가장 권장)
if [ -n "$STACK_NAME" ] && [ "$STACK_NAME" != "skn18-final-infra-cf-CoreInfraStack-xxxxx" ]; then
  echo "📋 Method 1: Getting from CloudFormation Stack"
  echo "Stack Name: $STACK_NAME"
  echo ""
  
  VPC_ID=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`VpcId`].OutputValue' \
    --output text 2>/dev/null)
  
  SUBNET_ID=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`SubnetId`].OutputValue' \
    --output text 2>/dev/null)
  
  if [ -n "$VPC_ID" ] && [ "$VPC_ID" != "None" ]; then
    echo "✅ Found VPC and Subnet from CloudFormation Stack:"
    echo ""
    echo "VPC ID: $VPC_ID"
    echo "Subnet ID: $SUBNET_ID"
    echo ""
    echo "📝 Packer build command:"
    echo "packer build \\"
    echo "  -var 'vpc_id=$VPC_ID' \\"
    echo "  -var 'subnet_id=$SUBNET_ID' \\"
    echo "  packer-rabbitmq.pkr.hcl"
    exit 0
  else
    echo "⚠️  Could not find VPC/Subnet from CloudFormation stack"
    echo ""
  fi
fi

# 방법 2: Export된 값에서 가져오기
echo "📋 Method 2: Getting from CloudFormation Exports"
echo ""

# CoreInfraStack의 Export 이름 패턴 찾기
EXPORT_VPC=$(aws cloudformation list-exports \
  --region "$REGION" \
  --query "Exports[?contains(Name, 'CoreInfraStack') && contains(Name, 'VpcId')].Name" \
  --output text 2>/dev/null | head -n 1)

if [ -n "$EXPORT_VPC" ]; then
  VPC_ID=$(aws cloudformation list-exports \
    --region "$REGION" \
    --query "Exports[?Name=='$EXPORT_VPC'].Value" \
    --output text 2>/dev/null)
  
  EXPORT_SUBNET=$(aws cloudformation list-exports \
    --region "$REGION" \
    --query "Exports[?contains(Name, 'CoreInfraStack') && contains(Name, 'SubnetId') && !contains(Name, 'SubnetId2')].Name" \
    --output text 2>/dev/null | head -n 1)
  
  if [ -n "$EXPORT_SUBNET" ]; then
    SUBNET_ID=$(aws cloudformation list-exports \
      --region "$REGION" \
      --query "Exports[?Name=='$EXPORT_SUBNET'].Value" \
      --output text 2>/dev/null)
  fi
  
  if [ -n "$VPC_ID" ] && [ "$VPC_ID" != "None" ] && [ -n "$SUBNET_ID" ] && [ "$SUBNET_ID" != "None" ]; then
    echo "✅ Found VPC and Subnet from CloudFormation Exports:"
    echo ""
    echo "VPC ID: $VPC_ID"
    echo "Subnet ID: $SUBNET_ID"
    echo ""
    echo "📝 Packer build command:"
    echo "packer build \\"
    echo "  -var 'vpc_id=$VPC_ID' \\"
    echo "  -var 'subnet_id=$SUBNET_ID' \\"
    echo "  packer-rabbitmq.pkr.hcl"
    exit 0
  fi
fi

# 방법 3: 직접 조회 (기본 VPC 또는 특정 이름의 VPC)
echo "📋 Method 3: Finding VPCs and Subnets directly"
echo ""

echo "Available VPCs:"
aws ec2 describe-vpcs \
  --region "$REGION" \
  --query 'Vpcs[*].[VpcId,CidrBlock,IsDefault,Tags[?Key==`Name`].Value|[0]]' \
  --output table

echo ""
echo "Available Public Subnets:"
aws ec2 describe-subnets \
  --region "$REGION" \
  --filters "Name=map-public-ip-on-launch,Values=true" \
  --query 'Subnets[*].[SubnetId,VpcId,CidrBlock,AvailabilityZone,Tags[?Key==`Name`].Value|[0]]' \
  --output table

echo ""
echo "💡 Usage:"
echo "  # CloudFormation 스택 이름을 알고 있는 경우:"
echo "  $0 $REGION skn18-final-infra-cf-CoreInfraStack-xxxxx"
echo ""
echo "  # 또는 직접 VPC ID와 Subnet ID를 지정:"
echo "  packer build \\"
echo "    -var 'vpc_id=vpc-xxxxx' \\"
echo "    -var 'subnet_id=subnet-xxxxx' \\"
echo "    packer-rabbitmq.pkr.hcl"
echo ""
echo "  # VPC/Subnet 없이 빌드 (기본 VPC 사용):"
echo "  packer build packer-rabbitmq.pkr.hcl"

