import environ, os
from pathlib import Path

""" 
다른 모듈에서 환경값이 필요하면 from config.env import env를 한 뒤 
env("VAR_NAME", default="...") 형태로 사용
"""
BASE_DIR = Path(__file__).resolve().parents[2]  # SKN18-4th-4team/
env = environ.Env()

# 프로덕션 환경 감지: EC2 인스턴스에서 실행 중인지 확인
# 로컬 개발 환경에서는 항상 .env 파일을 로드
# 프로덕션 환경(EC2)에서만 .env 파일을 건너뜀

# EC2 인스턴스 감지: 메타데이터 서비스 접근 가능 여부로 확인
def is_ec2_instance():
    """EC2 인스턴스인지 확인"""
    try:
        import urllib.request
        urllib.request.urlopen("http://169.254.169.254/latest/meta-data/instance-id", timeout=1)
        return True
    except:
        return False

# 1단계: EC2 인스턴스가 아닌 경우, .env 파일을 먼저 로드 (로컬 개발 환경)
# EC2가 아니면 무조건 개발 환경으로 간주하고 .env 파일 로드
IS_EC2 = is_ec2_instance()
IS_AWS_EXECUTION = os.getenv("AWS_EXECUTION_ENV") is not None

# EC2가 아니고 AWS Lambda도 아니면 .env 파일 로드
if not IS_EC2 and not IS_AWS_EXECUTION:
    # 개발 환경에서만 .env 파일 로드
    # 우선순위: .env → .env.local → (옵션) ENV_FILE로 지정된 경로
    env_loaded = False
    for f in [BASE_DIR / ".env", BASE_DIR / ".env.local"]:
        if f.exists():
            environ.Env.read_env(f)
            env_loaded = True
            print(f"✓ Loaded .env file from: {f}")
    
    env_file = os.getenv("ENV_FILE")
    if env_file and Path(env_file).exists():
        environ.Env.read_env(env_file)
        env_loaded = True
        print(f"✓ Loaded .env file from: {env_file}")
    
    if not env_loaded:
        print("⚠ No .env file found. Make sure .env file exists in project root.")

# 2단계: .env 파일 로드 후 프로덕션 환경 여부 최종 결정
# 개발 환경 강제 설정: DJANGO_ENV=development 환경 변수가 있으면 개발 환경으로 간주
IS_DEVELOPMENT = os.getenv("DJANGO_ENV") == "development"

# 프로덕션 환경 조건:
# 1. EC2 인스턴스에서 실행 중이거나
# 2. AWS_EXECUTION_ENV 환경 변수가 설정되어 있거나
# 3. AWS_REGION이 설정되어 있고 DJANGO_ENV가 development가 아닌 경우
IS_PRODUCTION = (
    IS_EC2 or
    IS_AWS_EXECUTION or
    (os.getenv("AWS_REGION") is not None and not IS_DEVELOPMENT)
)

if IS_PRODUCTION and not IS_DEVELOPMENT:
    # 프로덕션 환경에서는 환경 변수만 사용 (Parameter Store에서 entrypoint.sh가 설정)
    print("Production environment detected - using environment variables from Parameter Store")
