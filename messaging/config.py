"""
RabbitMQ 설정 및 큐/익스체인지 정의
확장 가능한 토픽 익스체인지 기반 구조

RabbitMQ 접속 정보는 다음의 우선순위로 사용된다:
1. 환경 변수 (RABBITMQ_HOST, RABBITMQ_USER, RABBITMQ_PASSWORD 등)
2. AWS Parameter Store (/skn18/rabbitmq-user, /skn18/rabbitmq-password)
3. 기본값 (localhost, guest 등)

AWS 환경에서는 Parameter Store에서 사용자명과 비밀번호를 가져옵니다.
"""
import os
from typing import Dict, Any, Optional
from urllib.parse import quote_plus

# AWS Lambda 환경에서만 boto3 사용 (로컬에서는 Optional)
try:
    import boto3  # type: ignore
    from botocore.exceptions import ClientError  # type: ignore
    HAS_BOTO3 = True
except ImportError:  # pragma: no cover
    boto3 = None  # type: ignore
    HAS_BOTO3 = False


def _get_parameter_from_store(
    parameter_path: str,
    region: Optional[str] = None,
) -> Optional[str]:
    """
    AWS Parameter Store에서 파라미터 값을 가져온다.
    
    Args:
        parameter_path: Parameter Store 경로 (예: /skn18/rabbitmq-user)
        region: AWS 리전 (None이면 환경 변수 또는 기본값 사용)
    
    Returns:
        파라미터 값 문자열, 실패 시 None
    """
    if not HAS_BOTO3:
        return None
    
    try:
        if region is None:
            region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "ap-northeast-2"))
        
        ssm_client = boto3.client("ssm", region_name=region)
        # SecureString인 경우 WithDecryption=True 필요
        with_decryption = "password" in parameter_path.lower()
        response = ssm_client.get_parameter(
            Name=parameter_path,
            WithDecryption=with_decryption
        )
        return response["Parameter"]["Value"]
    except (ClientError, Exception):
        return None


# RabbitMQ 연결 설정
# 우선순위: 환경 변수 > Parameter Store > 기본값

# HOST: 환경 변수 또는 기본값 (Parameter Store에는 없음)
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")

# PORT: 환경 변수 또는 기본값
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))

# USER: 환경 변수 > Parameter Store > 기본값
RABBITMQ_USER = os.getenv("RABBITMQ_USER")
if RABBITMQ_USER is None:
    RABBITMQ_USER = _get_parameter_from_store("/skn18/rabbitmq-user") or "guest"

# PASSWORD: 환경 변수 > Parameter Store > 기본값
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD")
if RABBITMQ_PASSWORD is None:
    RABBITMQ_PASSWORD = _get_parameter_from_store("/skn18/rabbitmq-password") or "guest"

# VHOST: 환경 변수 또는 기본값
RABBITMQ_VHOST = os.getenv("RABBITMQ_VHOST", "/")

# 연결 URL (비밀번호는 URL 인코딩 필요)
_encoded_password = quote_plus(RABBITMQ_PASSWORD)
RABBITMQ_URL = f"amqp://{RABBITMQ_USER}:{_encoded_password}@{RABBITMQ_HOST}:{RABBITMQ_PORT}/{RABBITMQ_VHOST}"

# Exchange 정의 (토픽 익스체인지 기반)
EXCHANGES: Dict[str, Dict[str, Any]] = {
    "tasks": {
        "name": "tasks.topic",
        "type": "topic",
        "durable": True,
    },
    "status": {
        "name": "status.topic",
        "type": "topic",
        "durable": True,
    },
    "dlx": {
        "name": "tasks.dlx",
        "type": "direct",
        "durable": True,
    },
    
}

# 라우팅 키 패턴: domain.entity.action
ROUTING_KEYS = {
    # 시뮬레이션 실행
    "sim.run.alphafold3": "sim.run.alphafold3",
    "sim.run.protein_mpnn": "sim.run.protein_mpnn",
    "sim.run.rfdiffusion": "sim.run.rfdiffusion",
    
    # 시뮬레이션 상태 피드백
    "sim.status": "sim.status",
    
    # 확장 가능한 라우팅 키 (향후 추가)
    # "rag.etl.pubmed": "rag.etl.pubmed",
    # "rag.etl.nih": "rag.etl.nih",
    # "kg.sync.entities": "kg.sync.entities",
    # "notify.email": "notify.email",
}

# 큐 설정 (확장 가능한 구조)
QUEUE_CONFIG: Dict[str, Dict[str, Any]] = {
    "sim.run.alphafold3": {
        "queue_name": "sim.run.alphafold3",
        "exchange": "tasks.topic",
        "routing_key": "sim.run.alphafold3",
        "durable": True,
        "dlx": "tasks.dlx",
        "dlq": "sim.run.alphafold3.dlq",
        "max_retries": 3,
        "priority": 5,  # 높은 우선순위
    },
    "sim.run.protein_mpnn": {
        "queue_name": "sim.run.protein_mpnn",
        "exchange": "tasks.topic",
        "routing_key": "sim.run.protein_mpnn",
        "durable": True,
        "dlx": "tasks.dlx",
        "dlq": "sim.run.protein_mpnn.dlq",
        "max_retries": 3,
        "priority": 5,
    },
    "sim.run.rfdiffusion": {
        "queue_name": "sim.run.rfdiffusion",
        "exchange": "tasks.topic",
        "routing_key": "sim.run.rfdiffusion",
        "durable": True,
        "dlx": "tasks.dlx",
        "dlq": "sim.run.rfdiffusion.dlq",
        "max_retries": 3,
        "priority": 5,
    },
    "sim.status": {
        "queue_name": "sim.status",
        "exchange": "status.topic",
        "routing_key": "sim.status",
        "durable": True,
        "priority": 1,  # 낮은 우선순위
    },
}

