from django.apps import AppConfig
import os


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
            # Neo4j 드라이버 미리 초기화
            try:
                from graph.nodes.rag_retriever_bridge import _get_neo4j_driver
                driver = _get_neo4j_driver()
                print("✅ [ChatConfig] Neo4j driver initialized at app startup")
            except Exception as e:
                # 초기화 실패해도 앱 시작은 계속됨 (첫 요청 시 재시도)
                print(f"⚠️ [ChatConfig] Neo4j driver initialization failed (will retry on first request): {e}")
            
            # RabbitMQ 연결 미리 초기화
            try:
                from messaging.connection import RabbitMQConnection
                connection_manager = RabbitMQConnection()
                # 연결 테스트 (연결이 없으면 생성됨)
                if not connection_manager.is_connected():
                    connection_manager.get_connection()
                print("✅ [ChatConfig] RabbitMQ connection initialized at app startup")
            except Exception as e:
                # 초기화 실패해도 앱 시작은 계속됨 (첫 요청 시 재시도)
                print(f"⚠️ [ChatConfig] RabbitMQ connection initialization failed (will retry on first request): {e}")
