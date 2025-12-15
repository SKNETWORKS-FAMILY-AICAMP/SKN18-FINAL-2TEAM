#!/bin/bash
# Lambda 빌드 디렉토리 준비 스크립트

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
BUILD_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Project root: $PROJECT_ROOT"
echo "Build dir: $BUILD_DIR"

# lambda_build 디렉토리 하위 내용 비우기 (스크립트 파일은 유지)
echo "Cleaning lambda_build directory..."
cd "$BUILD_DIR"
# 현재 디렉토리에서 protocols와 nih 디렉토리만 삭제
for dir in protocols nih; do
    if [ -d "$dir" ]; then
        echo "  Removing $dir/..."
        rm -rf "$dir"
    fi
done
echo "✓ lambda_build directory cleaned"

# PROJECT_ROOT 경로를 Lambda 환경에 맞게 수정하는 함수
fix_project_root() {
    local file_path="$1"
    if [ ! -f "$file_path" ]; then
        echo "Warning: File not found: $file_path"
        return
    fi
    
    # Python 스크립트로 파일 수정
    python3 << EOF
import re

file_path = "$file_path"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 이미 Lambda 환경 감지 코드가 있는지 확인
if 'AWS_LAMBDA_FUNCTION_NAME' in content and 'Path(\'/var/task\')' in content:
    print(f"✓ PROJECT_ROOT already configured for Lambda in {file_path}")
    exit(0)

# 기존 PROJECT_ROOT 설정 찾기 (단일 라인 패턴)
old_pattern = r'^PROJECT_ROOT = Path\(__file__\)\.resolve\(\)\.parents\[3\]'
new_code = '''# 패키지 형태로 실행하지 않아도 rag.* 모듈을 찾을 수 있도록 루트 경로 추가
import os
# Lambda 환경 감지
if os.environ.get('AWS_LAMBDA_FUNCTION_NAME'):
    # Lambda 환경: /var/task가 루트
    PROJECT_ROOT = Path('/var/task')
else:
    # 로컬 환경: 기존 방식
    PROJECT_ROOT = Path(__file__).resolve().parents[3]'''

if re.search(old_pattern, content, re.MULTILINE):
    # 기존 코드를 새 코드로 교체
    content = re.sub(
        old_pattern,
        new_code,
        content,
        flags=re.MULTILINE
    )
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✓ Updated PROJECT_ROOT path in {file_path}")
else:
    print(f"⚠ PROJECT_ROOT pattern not found in {file_path}, skipping...")
EOF
}

# NIH Lambda의 project_root 경로를 Lambda 환경에 맞게 수정하는 함수
fix_nih_project_root() {
    local file_path="$1"
    if [ ! -f "$file_path" ]; then
        echo "Warning: File not found: $file_path"
        return
    fi
    
    python3 << EOF
import re

file_path = "$file_path"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 기존 project_root 설정 찾기
old_pattern = r'^project_root = Path\(__file__\)\.parent\.parent\.parent\.parent\.parent'
new_code = '''# Lambda 환경 감지
import os
if os.environ.get('AWS_LAMBDA_FUNCTION_NAME'):
    # Lambda 환경: /var/task가 루트
    project_root = Path('/var/task')
else:
    # 로컬 환경: 기존 방식
    project_root = Path(__file__).parent.parent.parent.parent.parent'''

if re.search(old_pattern, content, re.MULTILINE):
    # 기존 코드를 새 코드로 교체
    content = re.sub(
        old_pattern,
        new_code,
        content,
        flags=re.MULTILINE
    )
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✓ Updated project_root path in {file_path}")
else:
    print(f"⚠ project_root pattern not found in {file_path}, skipping...")
EOF
}

# Protocols Lambda 빌드 디렉토리 준비
prepare_protocols() {
    echo "Preparing Protocols Lambda build directory..."
    PROTOCOLS_DIR="$BUILD_DIR/protocols"
    rm -rf "$PROTOCOLS_DIR"
    mkdir -p "$PROTOCOLS_DIR"
    
    # 필요한 디렉토리 구조 생성
    mkdir -p "$PROTOCOLS_DIR/rag/etl"
    
    # step01_ingest: Protocols 관련 파일만 복사 (Ingest Lambda용)
    echo "  Copying step01_ingest (Protocols files only)..."
    mkdir -p "$PROTOCOLS_DIR/rag/etl/step01_ingest/modules"
    cp "$PROJECT_ROOT/rag/etl/step01_ingest/__init__.py" "$PROTOCOLS_DIR/rag/etl/step01_ingest/" 2>/dev/null || true
    cp "$PROJECT_ROOT/rag/etl/step01_ingest/03_ingest_protocols.py" "$PROTOCOLS_DIR/rag/etl/step01_ingest/"
    # modules 폴더의 Protocols 관련 파일만 복사
    cp "$PROJECT_ROOT/rag/etl/step01_ingest/modules/__init__.py" "$PROTOCOLS_DIR/rag/etl/step01_ingest/modules/" 2>/dev/null || true
    cp "$PROJECT_ROOT/rag/etl/step01_ingest/modules/protocol.py" "$PROTOCOLS_DIR/rag/etl/step01_ingest/modules/"
    cp "$PROJECT_ROOT/rag/etl/step01_ingest/modules/schedule_store.py" "$PROTOCOLS_DIR/rag/etl/step01_ingest/modules/"
    
    # step02_normalize: Protocols 관련 파일만 복사 (Cleanse+Chunk Lambda용)
    echo "  Copying step02_normalize (Protocols files only)..."
    mkdir -p "$PROTOCOLS_DIR/rag/etl/step02_normalize"
    # __init__.py 파일 복사 또는 생성
    if [ -f "$PROJECT_ROOT/rag/etl/step02_normalize/__init__.py" ]; then
        cp "$PROJECT_ROOT/rag/etl/step02_normalize/__init__.py" "$PROTOCOLS_DIR/rag/etl/step02_normalize/"
    else
        touch "$PROTOCOLS_DIR/rag/etl/step02_normalize/__init__.py"
        echo "  Created missing __init__.py for step02_normalize"
    fi
    cp "$PROJECT_ROOT/rag/etl/step02_normalize/03_normalize_protocols.py" "$PROTOCOLS_DIR/rag/etl/step02_normalize/"
    
    # step04_chunk: Protocols 관련 파일만 복사 (Cleanse+Chunk Lambda용)
    echo "  Copying step04_chunk (Protocols files only)..."
    mkdir -p "$PROTOCOLS_DIR/rag/etl/step04_chunk"
    # __init__.py 파일 복사 또는 생성
    if [ -f "$PROJECT_ROOT/rag/etl/step04_chunk/__init__.py" ]; then
        cp "$PROJECT_ROOT/rag/etl/step04_chunk/__init__.py" "$PROTOCOLS_DIR/rag/etl/step04_chunk/"
    else
        touch "$PROTOCOLS_DIR/rag/etl/step04_chunk/__init__.py"
        echo "  Created missing __init__.py for step04_chunk"
    fi
    cp "$PROJECT_ROOT/rag/etl/step04_chunk/03_chunker_protocols.py" "$PROTOCOLS_DIR/rag/etl/step04_chunk/"
    # protocols_cleanse_chunk.py에서 chunker_protocols로 import하므로 별칭 파일 생성
    cp "$PROJECT_ROOT/rag/etl/step04_chunk/03_chunker_protocols.py" "$PROTOCOLS_DIR/rag/etl/step04_chunk/chunker_protocols.py"
    echo "  Created chunker_protocols.py alias for import compatibility"
    
    # step05_embed: Protocols 관련 파일만 복사 (Cleanse+Chunk+Embed Lambda용)
    echo "  Copying step05_embed (Protocols files only)..."
    mkdir -p "$PROTOCOLS_DIR/rag/etl/step05_embed"
    # __init__.py 파일 복사 또는 생성
    if [ -f "$PROJECT_ROOT/rag/etl/step05_embed/__init__.py" ]; then
        cp "$PROJECT_ROOT/rag/etl/step05_embed/__init__.py" "$PROTOCOLS_DIR/rag/etl/step05_embed/"
    else
        touch "$PROTOCOLS_DIR/rag/etl/step05_embed/__init__.py"
        echo "  Created missing __init__.py for step05_embed"
    fi
    cp "$PROJECT_ROOT/rag/etl/step05_embed/03_embed_protocols.py" "$PROTOCOLS_DIR/rag/etl/step05_embed/"
    
    # common: 전체 복사 (db_connection.py가 schedule_store에서 사용됨)
    echo "  Copying common modules..."
    cp -r "$PROJECT_ROOT/rag/etl/common" "$PROTOCOLS_DIR/rag/etl/"
    # .gitkeep 파일 제거
    find "$PROTOCOLS_DIR/rag/etl/common" -name ".gitkeep" -type f -delete 2>/dev/null || true
    
    # infra/aws/lambda_functions/trigger_etl: Ingest Lambda 6개와 Cleanse+Chunk Lambda용
    echo "  Copying infra/aws/lambda_functions/trigger_etl..."
    mkdir -p "$PROTOCOLS_DIR/infra/aws/lambda_functions"
    cp -r "$PROJECT_ROOT/infra/aws/lambda_functions/trigger_etl" "$PROTOCOLS_DIR/infra/aws/lambda_functions/"
    # .gitkeep 파일 제거
    find "$PROTOCOLS_DIR/infra/aws/lambda_functions/trigger_etl" -name ".gitkeep" -type f -delete 2>/dev/null || true
    
    # Protocols Lambda에 불필요한 파일 제거
    echo "  Removing unnecessary files for Protocols Lambda..."
    # trigger_etl에서 nih, pubmed 제거
    rm -rf "$PROTOCOLS_DIR/infra/aws/lambda_functions/trigger_etl/nih" || true
    rm -rf "$PROTOCOLS_DIR/infra/aws/lambda_functions/trigger_etl/pubmed" || true
    # protocols_cleanse_chunk_embed.py 제거 (protocols_cleanse_chunk.py만 사용)
    rm -f "$PROTOCOLS_DIR/infra/aws/lambda_functions/trigger_etl/protocols/protocols_cleanse_chunk_embed.py" || true
    # trigger_etl/requirements.txt 제거 (requirements-lambda-protocols.txt만 사용)
    rm -f "$PROTOCOLS_DIR/infra/aws/lambda_functions/trigger_etl/requirements.txt" || true
    
    # requirements 파일 복사
    cp "$PROJECT_ROOT/requirements-lambda-protocols.txt" "$PROTOCOLS_DIR/"
    
    # SAM이 requirements.txt를 찾을 수 있도록 심볼릭 링크 생성
    cd "$PROTOCOLS_DIR"
    ln -sf requirements-lambda-protocols.txt requirements.txt
    cd "$BUILD_DIR"
    
    # PROJECT_ROOT 경로를 Lambda 환경에 맞게 수정
    echo "Fixing PROJECT_ROOT path for Lambda environment..."
    fix_project_root "$PROTOCOLS_DIR/rag/etl/step01_ingest/03_ingest_protocols.py"
    
    # infra handler들의 project_root 경로도 수정
    for handler_file in "$PROTOCOLS_DIR/infra/aws/lambda_functions/trigger_etl/protocols"/*.py; do
        if [ -f "$handler_file" ]; then
            fix_nih_project_root "$handler_file"
        fi
    done
    
    echo "✓ Protocols Lambda build directory prepared"
}

# NIH Lambda 빌드 디렉토리 준비
prepare_nih() {
    echo "Preparing NIH Lambda build directory..."
    NIH_DIR="$BUILD_DIR/nih"
    rm -rf "$NIH_DIR"
    mkdir -p "$NIH_DIR"
    
    # 필요한 디렉토리 구조 생성
    mkdir -p "$NIH_DIR/rag/etl"
    
    # step01_ingest: NIH 관련 파일만 복사
    echo "  Copying step01_ingest (NIH files only)..."
    mkdir -p "$NIH_DIR/rag/etl/step01_ingest"
    cp "$PROJECT_ROOT/rag/etl/step01_ingest/__init__.py" "$NIH_DIR/rag/etl/step01_ingest/" 2>/dev/null || true
    cp "$PROJECT_ROOT/rag/etl/step01_ingest/02_ingest_nih.py" "$NIH_DIR/rag/etl/step01_ingest/"
    # 숫자로 시작하는 파일명을 import 가능한 별칭으로 생성
    cp "$PROJECT_ROOT/rag/etl/step01_ingest/02_ingest_nih.py" "$NIH_DIR/rag/etl/step01_ingest/ingest_nih.py"
    echo "  Created ingest_nih.py alias for import compatibility"
    # modules 폴더는 전체 복사 (필요한 경우를 위해)
    cp -r "$PROJECT_ROOT/rag/etl/step01_ingest/modules" "$NIH_DIR/rag/etl/step01_ingest/" 2>/dev/null || true
    # .gitkeep 파일 제거
    find "$NIH_DIR/rag/etl/step01_ingest/modules" -name ".gitkeep" -type f -delete 2>/dev/null || true
    
    # step02_normalize: NIH 관련 파일만 복사
    echo "  Copying step02_normalize (NIH files only)..."
    mkdir -p "$NIH_DIR/rag/etl/step02_normalize/modules"
    cp "$PROJECT_ROOT/rag/etl/step02_normalize/__init__.py" "$NIH_DIR/rag/etl/step02_normalize/" 2>/dev/null || true
    cp "$PROJECT_ROOT/rag/etl/step02_normalize/02_normalize_nih.py" "$NIH_DIR/rag/etl/step02_normalize/"
    # 숫자로 시작하는 파일명을 import 가능한 별칭으로 생성
    cp "$PROJECT_ROOT/rag/etl/step02_normalize/02_normalize_nih.py" "$NIH_DIR/rag/etl/step02_normalize/normalize_nih.py"
    echo "  Created normalize_nih.py alias for import compatibility"
    # modules/nih/만 복사
    cp -r "$PROJECT_ROOT/rag/etl/step02_normalize/modules/nih" "$NIH_DIR/rag/etl/step02_normalize/modules/"
    # .gitkeep 파일 제거
    find "$NIH_DIR/rag/etl/step02_normalize/modules/nih" -name ".gitkeep" -type f -delete 2>/dev/null || true
    cp "$PROJECT_ROOT/rag/etl/step02_normalize/modules/__init__.py" "$NIH_DIR/rag/etl/step02_normalize/modules/" 2>/dev/null || true
    
    # step04_chunk: NIH 관련 파일만 복사
    echo "  Copying step04_chunk (NIH files only)..."
    mkdir -p "$NIH_DIR/rag/etl/step04_chunk/modules"
    cp "$PROJECT_ROOT/rag/etl/step04_chunk/__init__.py" "$NIH_DIR/rag/etl/step04_chunk/" 2>/dev/null || true
    cp "$PROJECT_ROOT/rag/etl/step04_chunk/02_chunker_nih.py" "$NIH_DIR/rag/etl/step04_chunk/"
    # 숫자로 시작하는 파일명을 import 가능한 별칭으로 생성
    cp "$PROJECT_ROOT/rag/etl/step04_chunk/02_chunker_nih.py" "$NIH_DIR/rag/etl/step04_chunk/chunker_nih.py"
    echo "  Created chunker_nih.py alias for import compatibility"
    # modules/nih/만 복사
    cp -r "$PROJECT_ROOT/rag/etl/step04_chunk/modules/nih" "$NIH_DIR/rag/etl/step04_chunk/modules/"
    # .gitkeep 파일 제거
    find "$NIH_DIR/rag/etl/step04_chunk/modules/nih" -name ".gitkeep" -type f -delete 2>/dev/null || true
    cp "$PROJECT_ROOT/rag/etl/step04_chunk/modules/__init__.py" "$NIH_DIR/rag/etl/step04_chunk/modules/" 2>/dev/null || true
    
    # common: 전체 복사
    echo "  Copying common modules..."
    cp -r "$PROJECT_ROOT/rag/etl/common" "$NIH_DIR/rag/etl/"
    # .gitkeep 파일 제거
    find "$NIH_DIR/rag/etl/common" -name ".gitkeep" -type f -delete 2>/dev/null || true
    
    mkdir -p "$NIH_DIR/infra/aws/lambda_functions"
    cp -r "$PROJECT_ROOT/infra/aws/lambda_functions/trigger_etl" "$NIH_DIR/infra/aws/lambda_functions/"
    # .gitkeep 파일 제거
    find "$NIH_DIR/infra/aws/lambda_functions/trigger_etl" -name ".gitkeep" -type f -delete 2>/dev/null || true
    
    # NIH Lambda에 불필요한 파일 제거
    echo "Removing unnecessary files for NIH Lambda..."
    rm -rf "$NIH_DIR/infra/aws/lambda_functions/trigger_etl/protocols" || true
    rm -rf "$NIH_DIR/infra/aws/lambda_functions/trigger_etl/pubmed" || true
    # trigger_etl/requirements.txt 제거 (requirements-lambda-nih.txt만 사용)
    rm -f "$NIH_DIR/infra/aws/lambda_functions/trigger_etl/requirements.txt" || true
    
    # requirements 파일 복사
    cp "$PROJECT_ROOT/requirements-lambda-nih.txt" "$NIH_DIR/"
    
    # SAM이 requirements.txt를 찾을 수 있도록 심볼릭 링크 생성
    cd "$NIH_DIR"
    ln -sf requirements-lambda-nih.txt requirements.txt
    cd "$BUILD_DIR"
    
    # Lambda 핸들러의 import 문 수정 (새로운 핸들러 파일들 포함)
    echo "Fixing import statements in Lambda handlers..."
    
    # nih_ingest.py
    if [ -f "$NIH_DIR/infra/aws/lambda_functions/trigger_etl/nih/nih_ingest.py" ]; then
        sed -i.bak 's/from rag\.etl\.step01_ingest\.02_ingest_nih/from rag.etl.step01_ingest.ingest_nih/g' "$NIH_DIR/infra/aws/lambda_functions/trigger_etl/nih/nih_ingest.py"
        # step02_normalize.02_normalize_nih import도 수정 추가
        sed -i.bak 's/from rag\.etl\.step02_normalize\.02_normalize_nih/from rag.etl.step02_normalize.normalize_nih/g' "$NIH_DIR/infra/aws/lambda_functions/trigger_etl/nih/nih_ingest.py"
        rm -f "$NIH_DIR/infra/aws/lambda_functions/trigger_etl/nih/nih_ingest.py.bak"
        fix_nih_project_root "$NIH_DIR/infra/aws/lambda_functions/trigger_etl/nih/nih_ingest.py"
    fi
    
    # nih_cleanse_chunk.py
    if [ -f "$NIH_DIR/infra/aws/lambda_functions/trigger_etl/nih/nih_cleanse_chunk.py" ]; then
        sed -i.bak 's/from rag\.etl\.step02_normalize\.02_normalize_nih/from rag.etl.step02_normalize.normalize_nih/g' "$NIH_DIR/infra/aws/lambda_functions/trigger_etl/nih/nih_cleanse_chunk.py"
        sed -i.bak 's/from rag\.etl\.step04_chunk\.02_chunker_nih/from rag.etl.step04_chunk.chunker_nih/g' "$NIH_DIR/infra/aws/lambda_functions/trigger_etl/nih/nih_cleanse_chunk.py"
        rm -f "$NIH_DIR/infra/aws/lambda_functions/trigger_etl/nih/nih_cleanse_chunk.py.bak"
        fix_nih_project_root "$NIH_DIR/infra/aws/lambda_functions/trigger_etl/nih/nih_cleanse_chunk.py"
    fi
    
    echo "✓ NIH Lambda build directory prepared"
}

# 실행
prepare_protocols
prepare_nih

echo "✓ All Lambda build directories prepared"