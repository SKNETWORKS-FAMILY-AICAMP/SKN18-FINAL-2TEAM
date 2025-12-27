#!/bin/bash
# CloudFormation 배포 스크립트
# 이 스크립트는 prepare_build.sh → sam build → sam package → aws cloudformation deploy 순서로 실행합니다.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/../lambda_build"
CF_DIR="$SCRIPT_DIR"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# 색상 출력
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo_info() {
    echo -e "${GREEN}=== $1 ===${NC}"
}

echo_warn() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

echo_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Lambda Layer requirements.txt 확인
check_lambda_layers() {
    echo_info "Checking Lambda Layer requirements.txt files"
    
    LAYERS_DIR="$SCRIPT_DIR/../lambda_layers"
    MISSING_FILES=()
    
    for layer in common protocols nih; do
        LAYER_DIR="$LAYERS_DIR/$layer"
        if [ ! -f "$LAYER_DIR/requirements.txt" ]; then
            MISSING_FILES+=("$layer")
        elif [ ! -L "$LAYER_DIR/requirements.txt" ] && [ ! -f "$LAYER_DIR/requirements-layer-$layer.txt" ]; then
            echo_warn "$layer/requirements.txt exists but requirements-layer-$layer.txt not found"
        fi
    done
    
    if [ ${#MISSING_FILES[@]} -gt 0 ]; then
        echo_error "Missing requirements.txt in layers: ${MISSING_FILES[*]}"
        echo "Creating symlinks..."
        if [ -f "$LAYERS_DIR/create-symlinks.sh" ]; then
            cd "$LAYERS_DIR"
            bash create-symlinks.sh
        else
            echo_error "create-symlinks.sh not found. Please create requirements.txt manually."
            exit 1
        fi
    else
        echo "✓ All Lambda Layer requirements.txt files exist"
    fi
}

# Step 1: Lambda 빌드 디렉토리 준비
prepare_build() {
    echo_info "Step 1: Preparing Lambda build directories"
    cd "$BUILD_DIR"
    
    if [ ! -f "prepare_build.sh" ]; then
        echo_error "prepare_build.sh not found in $BUILD_DIR"
        exit 1
    fi
    
    if [ ! -x "prepare_build.sh" ]; then
        chmod +x prepare_build.sh
    fi
    
    ./prepare_build.sh
    
    # 빌드 디렉토리 확인
    if [ ! -d "protocols" ] || [ ! -d "nih" ]; then
        echo_error "prepare_build.sh failed: protocols or nih directory not found"
        exit 1
    fi
    
    echo "✓ Lambda build directories prepared"
}

# Step 2: SAM 빌드
sam_build() {
    echo_info "Step 2: SAM Build"
    cd "$CF_DIR"
    
    # .aws-sam 디렉토리 정리
    if [ -d ".aws-sam" ]; then
        echo "Cleaning .aws-sam directory..."
        rm -rf .aws-sam
    fi
    
    # SAM 빌드 실행
    echo "Running: sam build -t skn18-final-infra-cf.yaml"
    sam build -t skn18-final-infra-cf.yaml
    
    if [ ! -f ".aws-sam/build/template.yaml" ]; then
        echo_error "SAM build failed: template.yaml not found"
        exit 1
    fi
    
    echo "✓ SAM build completed"
    
    # 빌드 크기 확인
    echo ""
    echo "Build artifact sizes:"
    du -sh .aws-sam/build/*/ 2>/dev/null | head -5 || true
}

# Step 3: SAM 패키징 (중요: Nested Stack 템플릿과 CodeUri를 S3 URL로 변환)
sam_package() {
    echo_info "Step 3: SAM Package (converting CodeUri to S3 URLs)"
    cd "$CF_DIR"
    
    if [ ! -f ".aws-sam/build/template.yaml" ]; then
        echo_error ".aws-sam/build/template.yaml not found. Run sam build first."
        exit 1
    fi
    
    echo "Running: sam package --template-file .aws-sam/build/template.yaml --output-template-file packaged.yaml --resolve-s3"
    
    # sam package 실행 (Traceback이 발생해도 패키징이 성공할 수 있으므로 exit code만 확인)
    set +e  # 일시적으로 set -e 비활성화
    sam package \
        --template-file .aws-sam/build/template.yaml \
        --output-template-file packaged.yaml \
        --resolve-s3 \
        --region ap-northeast-2 2>&1 | tee /tmp/sam_package.log
    PACKAGE_EXIT_CODE=${PIPESTATUS[0]}
    set -e  # 다시 활성화
    
    # packaged.yaml 파일이 생성되었는지 확인 (실제 성공 여부)
    if [ ! -f "packaged.yaml" ]; then
        echo_error "SAM package failed: packaged.yaml not found"
        if [ -f /tmp/sam_package.log ]; then
            echo "SAM package output:"
            tail -20 /tmp/sam_package.log
        fi
        exit 1
    fi
    
    # Traceback이 발생했지만 packaged.yaml이 생성된 경우 경고만 출력
    if [ $PACKAGE_EXIT_CODE -ne 0 ]; then
        echo_warn "SAM package completed with warnings (exit code: $PACKAGE_EXIT_CODE)"
        echo_warn "This is often caused by SAM CLI telemetry code issues, but packaging succeeded."
        if [ -f /tmp/sam_package.log ]; then
            if grep -q "Traceback\|BlockingIOError" /tmp/sam_package.log; then
                echo "  → Traceback detected in SAM CLI (known issue, can be ignored)"
            fi
        fi
    else
        echo "✓ SAM package completed successfully"
    fi
    
    echo "  → packaged.yaml created with S3 URLs for all templates and CodeUri"
}

# 배포 상태 확인 함수
check_deployment_status() {
    local stack_name="${1:-skn18-final-infra}"
    local region="${2:-ap-northeast-2}"
    
    echo ""
    echo_info "Checking deployment status..."
    
    local status=$(aws cloudformation describe-stacks \
        --stack-name "$stack_name" \
        --region "$region" \
        --query 'Stacks[0].StackStatus' \
        --output text 2>/dev/null || echo "NOT_FOUND")
    
    if [ "$status" = "NOT_FOUND" ]; then
        echo_warn "Stack '$stack_name' not found"
        return 1
    fi
    
    echo "Stack Status: $status"
    
    if [[ "$status" == *"IN_PROGRESS"* ]]; then
        echo ""
        echo "Recent events:"
        aws cloudformation describe-stack-events \
            --stack-name "$stack_name" \
            --region "$region" \
            --max-items 10 \
            --query 'StackEvents[].{Time:Timestamp,Resource:LogicalResourceId,Status:ResourceStatus}' \
            --output table 2>/dev/null || true
    elif [[ "$status" == *"FAILED"* ]] || [[ "$status" == *"ROLLBACK"* ]]; then
        echo ""
        echo_error "Stack is in failed state. Recent failures:"
        aws cloudformation describe-stack-events \
            --stack-name "$stack_name" \
            --region "$region" \
            --max-items 20 \
            --query 'StackEvents[?ResourceStatus==`CREATE_FAILED` || ResourceStatus==`UPDATE_FAILED` || ResourceStatus==`DELETE_FAILED`].{Time:Timestamp,Resource:LogicalResourceId,Status:ResourceStatus,Reason:ResourceStatusReason}' \
            --output table 2>/dev/null || true
    fi
    
    return 0
}

# Step 4: CloudFormation 배포
cf_deploy() {
    local auto_yes="${1:-false}"
    echo_info "Step 4: CloudFormation Deploy"
    cd "$CF_DIR"
    
    if [ ! -f "packaged.yaml" ]; then
        echo_error "packaged.yaml not found. Run sam package first."
        exit 1
    fi
    
    # 로그 디렉토리 생성
    LOGS_DIR="$CF_DIR/logs"
    if [ ! -d "$LOGS_DIR" ]; then
        mkdir -p "$LOGS_DIR"
        echo "Created logs directory: $LOGS_DIR"
    fi
    
    # 타임스탬프가 포함된 로그 파일명 생성
    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    LOG_FILE="$LOGS_DIR/deploy_${TIMESTAMP}.log"
    
    echo "Running: aws cloudformation deploy --template-file packaged.yaml --stack-name skn18-final-infra --capabilities CAPABILITY_AUTO_EXPAND CAPABILITY_IAM --region ap-northeast-2"
    echo "Log file: $LOG_FILE"
    echo ""
    echo "Note: This script uses 'aws cloudformation deploy' (not 'sam deploy')"
    echo "      You can monitor the log file in real-time with: tail -f $LOG_FILE"
    echo ""
    # 스택 상태 확인
    CURRENT_STATUS=$(aws cloudformation describe-stacks \
        --stack-name skn18-final-infra \
        --region ap-northeast-2 \
        --query 'Stacks[0].StackStatus' \
        --output text 2>/dev/null || echo "NOT_FOUND")
    
    if [ "$CURRENT_STATUS" = "DELETE_FAILED" ]; then
        echo_warn "Stack is in DELETE_FAILED state."
        echo "  This usually means the stack is mostly deleted, with only S3 bucket remaining."
        echo "  CloudFormation may not allow creating a new stack with the same name."
        echo ""
        echo "Options:"
        echo "  1. Try to deploy anyway (may fail if stack name conflict)"
        echo "  2. Cancel and manually clean up the DELETE_FAILED stack from AWS console"
        echo ""
        if [ "$auto_yes" = true ]; then
            echo "Auto-confirm: Continuing with deployment (--yes flag)"
            response="y"
        else
            read -p "Continue with deployment? (y/N): " response
        fi
        if [[ ! "$response" =~ ^[Yy]$ ]]; then
            echo "Deployment cancelled."
            echo ""
            echo "To manually clean up:"
            echo "  1. Go to AWS CloudFormation console"
            echo "  2. Find 'skn18-final-infra' stack in DELETE_FAILED state"
            echo "  3. Delete the stack (S3 bucket will be retained if not empty)"
            echo "  4. Or continue with deployment - it may work if the stack is mostly deleted"
            exit 0
        fi
    else
        if [ "$auto_yes" = true ]; then
            echo "Auto-confirm: Continuing with deployment (--yes flag)"
        else
            echo_warn "This will deploy/update the CloudFormation stack. Continue? (y/N)"
            read -r response
            if [[ ! "$response" =~ ^[Yy]$ ]]; then
                echo "Deployment cancelled."
                exit 0
            fi
        fi
    fi
    
    # 배포를 백그라운드로 시작하고 로그를 파일에 저장
    echo ""
    echo_info "Starting deployment..."
    echo "  → Logging to: $LOG_FILE"
    echo "  → Monitor with: tail -f $LOG_FILE"
    echo ""
    
    # 배포 실행 (실시간 출력과 파일 저장 동시에)
    # Note: aws cloudformation deploy는 기본적으로 진행 상황을 자세히 보여주지 않으므로
    #       로그 파일을 tail -f로 모니터링하는 것을 권장합니다
    aws cloudformation deploy \
        --template-file packaged.yaml \
        --stack-name skn18-final-infra \
        --capabilities CAPABILITY_AUTO_EXPAND CAPABILITY_IAM \
        --region ap-northeast-2 \
        --no-fail-on-empty-changeset \
        2>&1 | tee "$LOG_FILE"
    
    DEPLOY_EXIT_CODE=${PIPESTATUS[0]}
    
    # 배포 완료 후 상태 확인
    if [ $DEPLOY_EXIT_CODE -ne 0 ]; then
        check_deployment_status "skn18-final-infra" "ap-northeast-2"
    fi
    
    # 최신 로그 파일 심볼릭 링크 생성 (편의를 위해)
    LATEST_LOG="$LOGS_DIR/deploy.log"
    ln -sf "$(basename "$LOG_FILE")" "$LATEST_LOG" 2>/dev/null || true
    
    if [ $DEPLOY_EXIT_CODE -eq 0 ]; then
        echo ""
        echo_info "Deployment completed successfully!"
        echo "Log saved to: $LOG_FILE"
        echo ""
        echo "Stack outputs:"
        aws cloudformation describe-stacks \
            --stack-name skn18-final-infra \
            --region ap-northeast-2 \
            --query 'Stacks[0].Outputs' \
            --output table 2>/dev/null || true
    else
        echo_error "Deployment failed. Check $LOG_FILE for details."
        echo ""
        echo "Fetching recent stack events..."
        aws cloudformation describe-stack-events \
            --stack-name skn18-final-infra \
            --region ap-northeast-2 \
            --max-items 20 \
            --query 'StackEvents[?ResourceStatus==`CREATE_FAILED` || ResourceStatus==`UPDATE_FAILED` || ResourceStatus==`DELETE_FAILED`].{Time:Timestamp,Resource:LogicalResourceId,Status:ResourceStatus,Reason:ResourceStatusReason}' \
            --output table 2>/dev/null || true
        
        echo ""
        echo "Checking Nested Stack details..."
        # 실패한 Nested Stack 찾기 (최근 이벤트에서)
        echo "Finding failed Nested Stacks from recent events..."
        FAILED_NESTED_STACKS=$(aws cloudformation describe-stack-events \
            --stack-name skn18-final-infra \
            --region ap-northeast-2 \
            --max-items 50 \
            --query 'StackEvents[?ResourceType==`AWS::CloudFormation::Stack` && ResourceStatus==`CREATE_FAILED`].PhysicalResourceId' \
            --output text 2>/dev/null | head -1 || echo "")
        
        if [ -n "$FAILED_NESTED_STACKS" ] && [ "$FAILED_NESTED_STACKS" != "None" ]; then
            echo ""
            echo "Found failed Nested Stack(s):"
            for stack_id in $FAILED_NESTED_STACKS; do
                echo ""
                echo "=========================================="
                echo "Nested Stack: $stack_id"
                echo "=========================================="
                echo ""
                
                # 스택 이름 추출 (ARN에서)
                STACK_NAME=$(echo "$stack_id" | awk -F'/' '{print $NF}')
                
                echo "Stack Name: $STACK_NAME"
                echo ""
                
                # 실패한 리소스 확인
                echo "Failed resources in this Nested Stack:"
                aws cloudformation describe-stack-events \
                    --stack-name "$stack_id" \
                    --region ap-northeast-2 \
                    --max-items 30 \
                    --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`].{Time:Timestamp,Resource:LogicalResourceId,Reason:ResourceStatusReason}' \
                    --output table 2>/dev/null || true
                
                echo ""
                echo "Recent events (last 15):"
                aws cloudformation describe-stack-events \
                    --stack-name "$stack_id" \
                    --region ap-northeast-2 \
                    --max-items 15 \
                    --query 'StackEvents[].{Time:Timestamp,Resource:LogicalResourceId,Status:ResourceStatus}' \
                    --output table 2>/dev/null || true
                
                echo ""
            done
        else
            echo "No failed Nested Stacks found in recent events."
            echo "Note: Nested Stacks may have been deleted. Check CloudFormation console for details."
        fi
        
        echo ""
        echo "For full stack events, run:"
        echo "  aws cloudformation describe-stack-events --stack-name skn18-final-infra --region ap-northeast-2"
        exit $DEPLOY_EXIT_CODE
    fi
}

# 메인 실행
main() {
    # 옵션 파싱
    AUTO_YES=false
    while [[ $# -gt 0 ]]; do
        case $1 in
            -y|--yes)
                AUTO_YES=true
                shift
                ;;
            *)
                echo_warn "Unknown option: $1"
                echo "Usage: $0 [-y|--yes]"
                echo "  -y, --yes    Skip confirmation prompt"
                exit 1
                ;;
        esac
    done
    
    echo ""
    echo "=========================================="
    echo "  CloudFormation Deployment Script"
    echo "=========================================="
    echo ""
    echo "Project Root: $PROJECT_ROOT"
    echo "Build Dir: $BUILD_DIR"
    echo "CF Dir: $CF_DIR"
    if [ "$AUTO_YES" = true ]; then
        echo "Auto-confirm: Enabled (--yes flag)"
    fi
    echo ""
    
    # Lambda Layer 확인
    check_lambda_layers
    
    # Step 1: prepare_build.sh
    prepare_build
    
    # Step 2: sam build
    sam_build
    
    # Step 3: sam package (중요!)
    sam_package
    
    # Step 4: aws cloudformation deploy
    cf_deploy "$AUTO_YES"
    
    echo ""
    echo_info "All steps completed successfully!"
}

# 스크립트 실행
main "$@"

