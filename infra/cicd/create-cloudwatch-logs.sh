#!/bin/bash
# CloudWatch Log Groups 생성 스크립트
# 배포 전에 실행하여 필요한 로그 그룹을 미리 생성

set -e

REGION="${AWS_REGION:-ap-northeast-2}"

# 생성할 로그 그룹 목록
LOG_GROUPS=(
    "/ec2/skn18/web-service"
    "/ec2/skn18/worker-service"
    "/ec2/skn18/celery-worker-service"
    "/ec2/skn18/celery-beat-service"
)

echo "Creating CloudWatch log groups in region: $REGION"

for log_group in "${LOG_GROUPS[@]}"; do
    echo "Checking/Creating log group: $log_group"
    
    # 로그 그룹 존재 여부 확인
    if aws logs describe-log-groups \
        --log-group-name-prefix "$log_group" \
        --region "$REGION" \
        --query "logGroups[?logGroupName=='$log_group'].logGroupName" \
        --output text | grep -q "$log_group"; then
        echo "  ✓ Log group already exists: $log_group"
    else
        # 로그 그룹 생성
        echo "  Creating log group: $log_group"
        aws logs create-log-group \
            --log-group-name "$log_group" \
            --region "$REGION" || {
            echo "  ⚠ Failed to create log group: $log_group"
            echo "  Continuing with next log group..."
        }
        echo "  ✓ Created log group: $log_group"
    fi
done

echo "CloudWatch log groups setup complete!"
