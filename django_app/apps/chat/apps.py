from django.apps import AppConfig
import os
import sys
import logging
from pathlib import Path

logger = logging.getLogger('apps.chat')


class ChatConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.chat"
    
    def ready(self):
        """
        Django 앱이 완전히 로드된 후 호출됩니다.
        여기서 외부 서비스 연결(Neo4j, RabbitMQ 등)을 미리 초기화하여 첫 요청의 지연을 방지합니다.
        """
        # 프로덕션 환경에서만 실행 (마이그레이션/테스트 중에는 실행하지 않음)
        if os.environ.get('RUN_MAIN') == 'true' or 'gunicorn' in os.environ.get('_', ''):
            # 프로젝트 루트를 sys.path에 추가 (graph, messaging 모듈 import용)
            # apps.py -> chat -> apps -> django_app -> PROJECT_ROOT (parents[3])
            PROJECT_ROOT = Path(__file__).resolve().parents[3]
            if str(PROJECT_ROOT) not in sys.path:
                sys.path.insert(0, str(PROJECT_ROOT))
            
            # Neo4j 드라이버 미리 초기화
            try:
                from graph.nodes.rag_retriever_bridge import _get_neo4j_driver
                driver = _get_neo4j_driver()
                logger.info("✅ Neo4j driver initialized at app startup")
            except Exception as e:
                # 초기화 실패해도 앱 시작은 계속됨 (첫 요청 시 재시도)
                logger.warning(f"⚠️ Neo4j driver initialization failed (will retry on first request): {e}", exc_info=True)
            
            # RabbitMQ 연결 미리 초기화
            try:
                from messaging.connection import RabbitMQConnection
                connection_manager = RabbitMQConnection()
                # 연결 테스트 (연결이 없으면 생성됨)
                if not connection_manager.is_connected():
                    connection_manager.get_connection()
                logger.info("✅ RabbitMQ connection initialized at app startup")
            except Exception as e:
                # 초기화 실패해도 앱 시작은 계속됨 (첫 요청 시 재시도)
                logger.warning(f"⚠️ RabbitMQ connection initialization failed (will retry on first request): {e}", exc_info=True)
