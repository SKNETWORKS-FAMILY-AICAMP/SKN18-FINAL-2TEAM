'''
orm으로 만드는 메모리 데이터베이스 초기화 스키마마
'''

from sqlalchemy import (
    Column, String, JSON, DateTime, Text
)
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()


class ConversationMemory(Base):
    """
    Memory Node(DB Slot) 저장용 테이블.
    classifier의 CASE 이름과 일치하는 컬럼으로 저장된다.
    """

    __tablename__ = "conversation_memory"

    # ---------------------------
    # 기본 정보
    # ---------------------------
    conversation_id = Column(String, primary_key=True)   # 채팅방 기준
    user_id = Column(String, nullable=False)             # 유저 기준
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ---------------------------
    # CASE 별 JSON Memory
    # ---------------------------
    no_relation = Column(JSON, default=list)
    simulation_q = Column(JSON, default=list)
    inference_q = Column(JSON, default=list)
    bio_q = Column(JSON, default=list)
    protocal_q = Column(JSON, default=list)

    # ---------------------------
    # Slot Memory 필드
    # ---------------------------
    last_case = Column(String)
    last_question = Column(Text)
    latest_keywords = Column(JSON, default=list)
    topic = Column(String)
    entities = Column(JSON, default=list)

    # 정제된 대화문맥(필요한 정보만 저장)
    context_window = Column(JSON, default=list)
    
    # 확장 필드
    extra = Column(JSON, default=dict)

    def __repr__(self):
        return f"<ConversationMemory(id={self.conversation_id})>"