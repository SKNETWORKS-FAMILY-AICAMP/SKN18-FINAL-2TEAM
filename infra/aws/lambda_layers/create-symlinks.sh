#!/bin/bash
# Lambda Layers 디렉토리에 requirements.txt 심볼릭 링크 생성
# SAM이 requirements.txt를 찾을 수 있도록 requirements-layer-*.txt로 링크

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Lambda Layers 심볼릭 링크 생성 ==="
echo ""

# Common Layer
echo "1. Common Layer..."
cd common
if [ -f "requirements.txt" ] && [ ! -L "requirements.txt" ]; then
  echo "  기존 requirements.txt 삭제 중..."
  rm -f requirements.txt
fi
if [ ! -L "requirements.txt" ]; then
  ln -sf requirements-layer-common.txt requirements.txt
  echo "  ✓ requirements.txt -> requirements-layer-common.txt"
else
  echo "  ✓ 심볼릭 링크가 이미 존재합니다."
fi
ls -la requirements.txt
cd ..

# Protocols Layer
echo ""
echo "2. Protocols Layer..."
cd protocols
if [ -f "requirements.txt" ] && [ ! -L "requirements.txt" ]; then
  echo "  기존 requirements.txt 삭제 중..."
  rm -f requirements.txt
fi
if [ ! -L "requirements.txt" ]; then
  ln -sf requirements-layer-protocols.txt requirements.txt
  echo "  ✓ requirements.txt -> requirements-layer-protocols.txt"
else
  echo "  ✓ 심볼릭 링크가 이미 존재합니다."
fi
ls -la requirements.txt
cd ..

# NIH Layer
echo ""
echo "3. NIH Layer..."
cd nih
if [ -f "requirements.txt" ] && [ ! -L "requirements.txt" ]; then
  echo "  기존 requirements.txt 삭제 중..."
  rm -f requirements.txt
fi
if [ ! -L "requirements.txt" ]; then
  ln -sf requirements-layer-nih.txt requirements.txt
  echo "  ✓ requirements.txt -> requirements-layer-nih.txt"
else
  echo "  ✓ 심볼릭 링크가 이미 존재합니다."
fi
ls -la requirements.txt
cd ..

echo ""
echo "=== 완료 ==="

