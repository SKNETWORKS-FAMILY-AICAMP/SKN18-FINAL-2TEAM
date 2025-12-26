"""
Base Consumer 클래스 (확장 가능)
"""
import json
import logging
import pika
from typing import Callable, Dict, Any
from messaging.connection import RabbitMQConnection
from messaging.config import EXCHANGES, QUEUE_CONFIG

logger = logging.getLogger(__name__)


class BaseConsumer:
    """Consumer 기본 클래스"""
    
    def __init__(self, routing_key: str, callback: Callable[[Dict[str, Any]], None]):
        """
        Args:
            routing_key: 라우팅 키 (예: "sim.run.alphafold3")
            callback: 메시지 처리 콜백 함수
        """
        if routing_key not in QUEUE_CONFIG:
            raise ValueError(f"Unknown routing key: {routing_key}")
        
        self.queue_config = QUEUE_CONFIG[routing_key]
        self.routing_key = routing_key
        self.callback = callback
        self.connection_manager = RabbitMQConnection()
    
    def start_consuming(self):
        """메시지 소비 시작"""
        try:
            connection = self.connection_manager.get_connection()
            channel = connection.channel()
            
            exchange_name = self.queue_config["exchange"]
            exchange_type = EXCHANGES[exchange_name.split(".")[0]]["type"]
            
            # Exchange 선언
            channel.exchange_declare(
                exchange=exchange_name,
                exchange_type=exchange_type,
                durable=True
            )
            
            # Queue 선언
            queue_name = self.queue_config["queue_name"]
            queue_args = {
                "durable": self.queue_config["durable"],
            }
            
            # DLX 설정
            if "dlx" in self.queue_config:
                queue_args["x-dead-letter-exchange"] = self.queue_config["dlx"]
                queue_args["x-dead-letter-routing-key"] = self.queue_config.get("dlq", f"{queue_name}.dlq")
            
            channel.queue_declare(
                queue=queue_name,
                durable=self.queue_config["durable"],
                arguments=queue_args
            )
            
            # Queue와 Exchange 바인딩
            channel.queue_bind(
                exchange=exchange_name,
                queue=queue_name,
                routing_key=self.routing_key
            )
            
            # Consumer 설정
            channel.basic_qos(prefetch_count=1)  # 한 번에 하나씩 처리
            
            channel.basic_consume(
                queue=queue_name,
                on_message_callback=self._handle_message
            )
            
            logger.info(f"Starting consumer for {queue_name}")
            channel.start_consuming()
            
        except KeyboardInterrupt:
            logger.info("Consumer stopped by user")
            if 'channel' in locals():
                channel.stop_consuming()
        except Exception as e:
            logger.error(f"Consumer error: {e}", exc_info=True)
            raise
    
    def _handle_message(self, ch, method, properties, body):
        """메시지 처리"""
        try:
            message = json.loads(body)
            logger.info(f"Received message: task_id={message.get('task_id', 'N/A')}")
            
            # 콜백 실행
            self.callback(message)
            
            # ACK 전송
            ch.basic_ack(delivery_tag=method.delivery_tag)
            
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            # NACK 전송 (재큐잉)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

