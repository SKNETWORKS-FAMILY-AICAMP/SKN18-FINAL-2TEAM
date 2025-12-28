#!/bin/bash
# 생성된 RabbitMQ AMI ID를 Parameter Store에 등록하는 스크립트

AMI_ID="${1:-}"  # 필수 파라미터
REGION="${2:-ap-northeast-2}"
PARAM_NAME="/skn18/rabbitmq-ami-id"

if [ -z "$AMI_ID" ]; then
  echo "Usage: $0 <AMI_ID> [REGION]"
  echo "Example: $0 ami-0123456789abcdef0 ap-northeast-2"
  exit 1
fi

echo "=== Registering RabbitMQ AMI ID to Parameter Store ==="
echo "AMI ID: $AMI_ID"
echo "Region: $REGION"
echo "Parameter: $PARAM_NAME"
echo ""

# Parameter Store에 AMI ID 저장
aws ssm put-parameter \
  --region "$REGION" \
  --name "$PARAM_NAME" \
  --type "String" \
  --value "$AMI_ID" \
  --description "SKN18 RabbitMQ EC2 AMI ID (built with Packer)" \
  --overwrite

if [ $? -eq 0 ]; then
  echo ""
  echo "✅ Successfully registered RabbitMQ AMI ID to Parameter Store!"
  echo ""
  echo "이제 CloudFormation 배포 시 이 AMI가 자동으로 사용됩니다."
  echo ""
  echo "확인:"
  echo "  aws ssm get-parameter --region $REGION --name $PARAM_NAME --query 'Parameter.Value' --output text"
else
  echo ""
  echo "❌ Failed to register AMI ID"
  exit 1
fi

