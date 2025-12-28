import environ, os
from pathlib import Path

""" 
다른 모듈에서 환경값이 필요하면 from config.env import env를 한 뒤 
env("VAR_NAME", default="...") 형태로 사용
"""
BASE_DIR = Path(__file__).resolve().parents[2]  # SKN18-4th-4team/
env = environ.Env()

# 프로덕션 환경에서는 .env 파일을 읽지 않음 (Parameter Store 사용)
# AWS 환경 감지: EC2 인스턴스 메타데이터 또는 환경 변수로 확인
IS_PRODUCTION = os.getenv("AWS_EXECUTION_ENV") is not None or \
                os.getenv("AWS_REGION") is not None or \
                os.path.exists("/sys/class/dmi/id/product-uuid")  # EC2 인스턴스 감지

if not IS_PRODUCTION:
    # 개발 환경에서만 .env 파일 로드
    # 우선순위: .env → .env.local → (옵션) ENV_FILE로 지정된 경로
    for f in [BASE_DIR / ".env", BASE_DIR / ".env.local"]:
        if f.exists():
            environ.Env.read_env(f)
    
    env_file = os.getenv("ENV_FILE")
    if env_file and Path(env_file).exists():
        environ.Env.read_env(env_file)
else:
    # 프로덕션 환경에서는 환경 변수만 사용 (Parameter Store에서 entrypoint.sh가 설정)
    print("Production environment detected - skipping .env file loading")
