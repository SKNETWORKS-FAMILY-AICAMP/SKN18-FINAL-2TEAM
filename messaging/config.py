"""
RabbitMQ 설정 및 큐/익스체인지 정의
확장 가능한 토픽 익스체인지 기반 구조
"""
import os
from typing import Dict, Any

# RabbitMQ 연결 설정
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "guest")
RABBITMQ_VHOST = os.getenv("RABBITMQ_VHOST", "/")

# 연결 URL
RABBITMQ_URL = f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASSWORD}@{RABBITMQ_HOST}:{RABBITMQ_PORT}/{RABBITMQ_VHOST}"

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

