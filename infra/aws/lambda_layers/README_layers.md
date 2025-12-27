# Lambda Layers 및 배포 프로세스 가이드

이 문서는 SKN18 프로젝트의 Lambda Layer 구조와 SAM을 이용한 빌드/배포 프로세스를 설명합니다.

## 1. Lambda Layer 구조

프로젝트는 효율적인 의존성 관리를 위해 3개의 Layer를 사용합니다.

### A. Common Layer (`skn18-common-layer`)
- **용도**: 모든 Lambda 함수에서 공통으로 사용하는 기본 라이브러리
- **포함 패키지**: `requests`, `python-dateutil`, `python-dotenv`
- **정의 위치**: `infra/aws/lambda_layers/common/requirements-layer-common.txt`

### B. Protocols Layer (`skn18-protocols-layer`)
- **용도**: Protocols.io 데이터 처리 전용 라이브러리
- **포함 패키지**: `beautifulsoup4`, `lxml`, `psycopg2-binary`
- **정의 위치**: `infra/aws/lambda_layers/protocols/requirements-layer-protocols.txt`

### C. NIH Layer (`skn18-nih-layer`)
- **용도**: NIH 데이터 처리 및 텍스트 처리 전용 라이브러리
- **포함 패키지**: `tiktoken`, `nltk` (+ NLTK 데이터 `punkt`, `punkt_tab`)
- **정의 위치**: `infra/aws/lambda_layers/nih/requirements-layer-nih.txt`

---

## 2. SAM 빌드 및 배포 프로세스

`sam build` -> `sam deploy` 실행 시 다음과 같은 순서로 처리됩니다.

### 1단계: `sam build` (로컬 아티팩트 생성)

**Layer가 먼저 빌드되고, 그 다음 Function이 빌드됩니다.**

1. **Layer 빌드** (`core-infra.yaml`)
   - `requirements-layer-*.txt`를 참조하여 라이브러리를 설치합니다.
   - 결과물: `.aws-sam/build/LayerName/python/lib/python3.12/site-packages/`

2. **Function 빌드** (`lambdas-*.yaml`)
   - **CodeUri 복사**: 프로젝트 전체 코드를 `.aws-sam/build/FunctionName/`으로 복사합니다.
   - **BuildCommand 실행**:
     - 불필요한 파일 삭제 (다른 Lambda 코드, 테스트 파일 등)
     - Layer에 포함된 중복 라이브러리 제거 (`rm -rf requests ...`)
     - 파일 이름 변경 (예: `03_chunker_protocols.py` -> `chunker_protocols.py`)
     - *참고: `requirements-lambda-*.txt`는 Layer 사용으로 인해 더 이상 사용되지 않습니다.*

### 2단계: `sam deploy` (AWS 배포)

1. **업로드**: 빌드된 Layer와 Function 아티팩트(ZIP)를 S3에 업로드합니다.
2. **스택 업데이트**: CloudFormation 템플릿을 업데이트합니다.
3. **리소스 생성/갱신**:
   - Lambda Layer 버전을 생성합니다.
   - Lambda Function을 생성하고, 생성된 Layer ARN을 연결합니다.

---

## 3. 런타임 동작 (AWS Lambda 실행 시)

Lambda가 AWS 환경에서 실행될 때의 구조입니다.

1. **Layer 마운트 (`/opt`)**
   - Layer의 내용이 `/opt` 디렉토리에 압축 해제됩니다.
   - 파이썬 라이브러리 경로: `/opt/python/lib/python3.12/site-packages/`
   - Python은 이 경로를 자동으로 인식하여 `import`가 가능합니다.

2. **Function 코드 로드 (`/var/task`)**
   - BuildCommand로 정리된 함수 코드가 `/var/task`에 위치합니다.

3. **실행**
   - 핸들러가 실행되면서 `/var/task`의 코드와 `/opt`의 라이브러리를 함께 사용합니다.

---

## 4. 의존성 추가/변경 방법

### 새로운 라이브러리가 필요한 경우
1. 해당 라이브러리가 **공통**인지, **특정 기능**용인지 판단합니다.
2. 적절한 `infra/aws/lambda_layers/*/requirements-layer-*.txt` 파일에 추가합니다.
3. `sam build`를 실행하면 Layer가 다시 빌드되어 포함됩니다.

### BuildCommand 수정이 필요한 경우
- `lambdas-protocols.yaml` 또는 `lambdas-nih.yaml`의 `Metadata > BuildProperties > BuildCommand`를 수정합니다.
- 주로 불필요한 파일을 더 삭제하거나, 특정 파일을 복사해야 할 때 수정합니다.

