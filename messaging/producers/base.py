"""
Base Producer 클래스 (확장 가능)
"""
import json
import logging
import pika
from typing import Dict, Any
from messaging.connection import RabbitMQConnection
from messaging.config import EXCHANGES, QUEUE_CONFIG

logger = logging.getLogger(__name__)


class BaseProducer:
    """Producer 기본 클래스"""
    
    def __init__(self, routing_key: str):
        """
        Args:
            routing_key: 라우팅 키 (예: "sim.run.alphafold3")
        """
        if routing_key not in QUEUE_CONFIG:
            raise ValueError(f"Unknown routing key: {routing_key}")
        
        self.queue_config = QUEUE_CONFIG[routing_key]
        self.routing_key = routing_key
        self.connection_manager = RabbitMQConnection()
    
    def publish(self, message: Dict[str, Any], priority: int = None):
        """
        메시지 발행
        
        Args:
            message: 메시지 딕셔너리
            priority: 우선순위 (기본값: 큐 설정값)
        """
        channel = None
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
            
            # 메시지 속성
            properties = pika.BasicProperties(
                delivery_mode=2,  # 메시지 영속성
                priority=priority or self.queue_config.get("priority", 0)
            )
            
            # 메시지 발행
            channel.basic_publish(
                exchange=exchange_name,
                routing_key=self.routing_key,
                body=json.dumps(message),
                properties=properties
            )
            
            logger.info(f"Message published to {queue_name}: task_id={message.get('task_id', 'N/A')}")
            
        except Exception as e:
            logger.error(f"Failed to publish message: {e}", exc_info=True)
            raise
        finally:
            # Channel을 닫아 메모리 누수 방지
            if channel and not channel.is_closed:
                try:
                    channel.close()
                except Exception:
                    pass  # 이미 닫혀있을 수 있음


class TopicProducer:
    """토픽 익스체인지용 Producer"""
    
    def __init__(self, exchange: str = "tasks.topic"):
        """
        Args:
            exchange: Exchange 이름
        """
        self.exchange = exchange
        self.connection_manager = RabbitMQConnection()
    
    def publish(self, routing_key: str, message: Dict[str, Any], priority: int = 0):
        """
        토픽 익스체인지로 메시지 발행
        
        Args:
            routing_key: 라우팅 키 (예: "sim.run.alphafold3")
            message: 메시지 딕셔너리
            priority: 우선순위
        """
        channel = None
        try:
            connection = self.connection_manager.get_connection()
            channel = connection.channel()
            
            # Exchange 선언
            exchange_type = EXCHANGES[self.exchange.split(".")[0]]["type"]
            channel.exchange_declare(
                exchange=self.exchange,
                exchange_type=exchange_type,
                durable=True
            )
            
            # 메시지 속성
            properties = pika.BasicProperties(
                delivery_mode=2,
                priority=priority
            )
            
            # 메시지 발행
            channel.basic_publish(
                exchange=self.exchange,
                routing_key=routing_key,
                body=json.dumps(message),
                properties=properties
            )
            
            logger.info(f"Message published to {self.exchange} with routing_key={routing_key}: task_id={message.get('task_id', 'N/A')}")
            
        except Exception as e:
            logger.error(f"Failed to publish message: {e}", exc_info=True)
            raise
        finally:
            # Channel을 닫아 메모리 누수 방지
            if channel and not channel.is_closed:
                try:
                    channel.close()
                except Exception:
                    pass  # 이미 닫혀있을 수 있음

