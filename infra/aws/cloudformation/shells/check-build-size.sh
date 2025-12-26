#!/bin/bash
# SAM 빌드 크기 확인 스크립트

echo "=== SAM Build Size Check ==="
echo ""

if [ ! -d ".aws-sam/build" ]; then
  echo "❌ .aws-sam/build 디렉토리가 없습니다. 먼저 sam build를 실행하세요."
  exit 1
fi

echo "각 스택별 크기:"
du -sh .aws-sam/build/* 2>/dev/null | sort -h

echo ""
echo "각 Lambda 함수별 크기 (Protocols):"
if [ -d ".aws-sam/build/ProtocolsLambdaStack" ]; then
  du -sh .aws-sam/build/ProtocolsLambdaStack/* 2>/dev/null | sort -h | head -10
fi

echo ""
echo "각 Lambda 함수별 크기 (NIH):"
if [ -d ".aws-sam/build/NihLambdaStack" ]; then
  du -sh .aws-sam/build/NihLambdaStack/* 2>/dev/null | sort -h | head -10
fi

echo ""
echo "큰 디렉토리 상위 10개 (Protocols EtlLambdaProtein 예시):"
if [ -d ".aws-sam/build/ProtocolsLambdaStack/ProtocolsEtlLambdaProtein" ]; then
  du -sh .aws-sam/build/ProtocolsLambdaStack/ProtocolsEtlLambdaProtein/* 2>/dev/null | sort -h -r | head -10
fi

