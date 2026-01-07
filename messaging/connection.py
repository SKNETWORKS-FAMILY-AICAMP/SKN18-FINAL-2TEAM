"""
RabbitMQ 연결 관리 (싱글톤 패턴)
"""
import pika
import logging
from typing import Optional
from messaging.config import RABBITMQ_URL

logger = logging.getLogger(__name__)


class RabbitMQConnection:
    """RabbitMQ 연결 싱글톤"""
    _instance: Optional['RabbitMQConnection'] = None
    _connection: Optional[pika.BlockingConnection] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_connection(self) -> pika.BlockingConnection:
        """연결 가져오기 (없으면 생성)"""
        if self._connection is None or self._connection.is_closed:
            try:
                parameters = pika.URLParameters(RABBITMQ_URL)
                parameters.heartbeat = 0
                parameters.blocked_connection_timeout = None  # 선택이지만 같이 꺼두면 안전
                self._connection = pika.BlockingConnection(parameters)
                logger.info(f"RabbitMQ connected to {RABBITMQ_URL.split('@')[1] if '@' in RABBITMQ_URL else RABBITMQ_URL}")
            except Exception as e:
                logger.error(f"Failed to connect to RabbitMQ: {e}")
                raise
        return self._connection
    
    def close(self):
        """연결 종료"""
        if self._connection and not self._connection.is_closed:
            self._connection.close()
            self._connection = None
            logger.info("RabbitMQ connection closed")
    
    def is_connected(self) -> bool:
        """연결 상태 확인"""
        return self._connection is not None and not self._connection.is_closed

