#!/bin/bash
# NIH Cleansing + Chunking Lambda MemorySize 설정 스크립트

MEMORY_SIZE="${1:-10240}"  # 기본값: 10240MB (10GB, Lambda 최대값)
REGION="${2:-ap-northeast-2}"
PARAM_NAME="/skn18/nih-cleanse-chunk-memory-size"

echo "=== Setting NIH Cleansing + Chunking Lambda Memory Size ==="
echo "Memory Size: ${MEMORY_SIZE}MB"
echo "Region: $REGION"
echo "Parameter: $PARAM_NAME"
echo ""

# Lambda MemorySize 유효 범위 체크 (128MB ~ 10240MB, 64MB 단위)
MIN_MEMORY=128
MAX_MEMORY=10240

if [ "$MEMORY_SIZE" -lt "$MIN_MEMORY" ] || [ "$MEMORY_SIZE" -gt "$MAX_MEMORY" ]; then
  echo "❌ Error: Memory size must be between ${MIN_MEMORY}MB and ${MAX_MEMORY}MB"
  exit 1
fi

if [ $((MEMORY_SIZE % 64)) -ne 0 ]; then
  echo "❌ Error: Memory size must be a multiple of 64MB"
  exit 1
fi

# Parameter Store에 메모리 크기 저장
aws ssm put-parameter \
  --region "$REGION" \
  --name "$PARAM_NAME" \
  --type "String" \
  --value "$MEMORY_SIZE" \
  --description "NIH Cleansing + Chunking Lambda Memory Size (MB). NIH는 메모리 사용량이 많아 큰 값 권장 (5120MB ~ 10240MB)" \
  --overwrite

if [ $? -eq 0 ]; then
  echo ""
  echo "✅ Successfully set NIH Cleansing + Chunking Lambda memory size to ${MEMORY_SIZE}MB!"
  echo ""
  echo "다음 CloudFormation 배포 시 적용됩니다."
  echo ""
  echo "확인:"
  echo "  aws ssm get-parameter --region $REGION --name $PARAM_NAME --query 'Parameter.Value' --output text"
else
  echo ""
  echo "❌ Failed to set memory size"
  exit 1
fi

