#!/bin/bash
# CloudFormation 배포만 실행하는 스크립트 (빌드/패키징은 이미 완료된 경우)

STACK_NAME="${1:-skn18-final-infra}"
REGION="${2:-ap-northeast-2}"

echo "=========================================="
echo "  CloudFormation Deploy Only"
echo "=========================================="
echo ""
echo "Stack Name: $STACK_NAME"
echo "Region: $REGION"
echo ""

# packaged.yaml 확인
if [ ! -f "packaged.yaml" ]; then
    echo "❌ packaged.yaml not found."
    echo "   Run ./deploy.sh first to build and package."
    exit 1
fi

echo "✓ packaged.yaml found"
echo ""

# 스택 상태 확인
CURRENT_STATUS=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query 'Stacks[0].StackStatus' \
    --output text 2>/dev/null || echo "NOT_FOUND")

if [ "$CURRENT_STATUS" != "NOT_FOUND" ]; then
    echo "Current Stack Status: $CURRENT_STATUS"
    echo ""
fi

read -p "Deploy CloudFormation stack? (y/N): " confirm

if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    echo "Cancelled."
    exit 0
fi

echo ""
echo "Deploying stack..."
echo ""

# 배포 실행
aws cloudformation deploy \
    --template-file packaged.yaml \
    --stack-name "$STACK_NAME" \
    --capabilities CAPABILITY_AUTO_EXPAND CAPABILITY_IAM \
    --region "$REGION" \
    --no-fail-on-empty-changeset

DEPLOY_EXIT_CODE=$?

if [ $DEPLOY_EXIT_CODE -eq 0 ]; then
    echo ""
    echo "✓ Deployment completed successfully!"
    echo ""
    echo "Stack outputs:"
    aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query 'Stacks[0].Outputs' \
        --output table 2>/dev/null || true
else
    echo ""
    echo "✗ Deployment failed with exit code: $DEPLOY_EXIT_CODE"
    echo ""
    echo "Check stack events:"
    aws cloudformation describe-stack-events \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --max-items 10 \
        --query 'StackEvents[].{Time:Timestamp,Resource:LogicalResourceId,Status:ResourceStatus,Reason:ResourceStatusReason}' \
        --output table 2>/dev/null || true
    exit $DEPLOY_EXIT_CODE
fi

