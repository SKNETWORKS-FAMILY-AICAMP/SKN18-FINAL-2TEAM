#!/bin/bash
# CloudFormation 배포 상태 확인 스크립트

STACK_NAME="${1:-skn18-final-infra}"
REGION="${2:-ap-northeast-2}"

echo "Checking deployment status for stack: $STACK_NAME"
echo "Region: $REGION"
echo ""

# 스택 상태 확인
STATUS=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query 'Stacks[0].StackStatus' \
    --output text 2>/dev/null || echo "NOT_FOUND")

if [ "$STATUS" = "NOT_FOUND" ]; then
    echo "❌ Stack '$STACK_NAME' not found"
    exit 1
fi

echo "📊 Stack Status: $STATUS"
echo ""

# 진행 중인 경우 최근 이벤트 표시
if [[ "$STATUS" == *"IN_PROGRESS"* ]]; then
    echo "🔄 Stack is being created/updated. Recent events:"
    echo ""
    aws cloudformation describe-stack-events \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --max-items 15 \
        --query 'StackEvents[].{Time:Timestamp,Resource:LogicalResourceId,Status:ResourceStatus}' \
        --output table 2>/dev/null || true
elif [[ "$STATUS" == *"FAILED"* ]] || [[ "$STATUS" == *"ROLLBACK"* ]]; then
    echo "❌ Stack is in failed state. Recent failures:"
    echo ""
    aws cloudformation describe-stack-events \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --max-items 20 \
        --query 'StackEvents[?ResourceStatus==`CREATE_FAILED` || ResourceStatus==`UPDATE_FAILED` || ResourceStatus==`DELETE_FAILED`].{Time:Timestamp,Resource:LogicalResourceId,Status:ResourceStatus,Reason:ResourceStatusReason}' \
        --output table 2>/dev/null || true
    echo ""
    echo "For full stack events, run:"
    echo "  aws cloudformation describe-stack-events --stack-name $STACK_NAME --region $REGION"
elif [[ "$STATUS" == *"COMPLETE"* ]] && [[ "$STATUS" != *"ROLLBACK"* ]]; then
    echo "✅ Stack deployment completed successfully!"
    echo ""
    echo "Stack Outputs:"
    aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query 'Stacks[0].Outputs' \
        --output table 2>/dev/null || true
fi

