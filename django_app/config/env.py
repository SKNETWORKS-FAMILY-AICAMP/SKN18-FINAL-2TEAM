import environ, os
from pathlib import Path

""" 
다른 모듈에서 환경값이 필요하면 from config.env import env를 한 뒤 
env("VAR_NAME", default="...") 형태로 사용
"""
BASE_DIR = Path(__file__).resolve().parents[2]  # SKN18-4th-4team/
env = environ.Env()
# 우선순위: .env → .env.local → (옵션) ENV_FILE로 지정된 경로
for f in [BASE_DIR / ".env", BASE_DIR / ".env.local"]:
    if f.exists():
        environ.Env.read_env(f)

env_file = os.getenv("ENV_FILE")
if env_file and Path(env_file).exists():
    environ.Env.read_env(env_file)
