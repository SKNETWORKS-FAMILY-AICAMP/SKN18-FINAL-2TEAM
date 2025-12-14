'''
메모리 데이터베이스 스키마
- chat_room_id: 채팅창 ID (conversation_id와 동일)
- case_type: 데이터 타입 구분 (SIMULATION_Q, INFERENCE_Q, BIO_Q, PROTOCOL_Q)
- full_response: 원본 답변 저장
- summarize_response: 요약 답변 저장
- 단순화된 3컬럼 구조로 효율적인 조회 및 관리
'''

from sqlalchemy import (
    Column, String, DateTime, Text, Integer, Sequence, ForeignKey
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()


class ConversationMemory(Base):
    """
    각 질문-답변을 개별 row로 저장하는 테이블.
    chat_room_id는 채팅방을 구분하고, 각 질문마다 새 row 생성.
    case_type으로 데이터 타입 구분, full_response와 summarize_response에 답변 저장.
    """

    __tablename__ = "conversation_memory"

    # ---------------------------
    # 기본 정보
    # ---------------------------
    chat_id = Column(Integer, Sequence('chat_id_seq'), primary_key=True, autoincrement=True)  # 자동증가 PK
    chat_room_id = Column(String, nullable=False, index=True)  # 채팅방 ID (같은 방에 여러 row 가능)
    user_id = Column(String, nullable=False)            # 유저 ID
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ---------------------------
    # 메타 정보
    # ---------------------------
    original_question = Column(Text)         # 질문 원문
    topic = Column(String)                   # 1줄 주제 요약
    entities = Column(JSONB, default=list)   # 추출된 엔티티들
    latest_keywords = Column(JSONB, default=list)  # 최근 키워드들
    referenced_memory_count = Column(Integer, default=0)  # 답변 생성 시 참고한 이전 대화 개수

    # ---------------------------
    # 답변 정보 (단순화된 구조)
    # ---------------------------
    case_type = Column(String, nullable=False, index=True)  # 데이터 타입: SIMULATION_Q, INFERENCE_Q, BIO_Q, PROTOCOL_Q
    full_response = Column(Text, nullable=True)             # 원본 답변 전체
    summarize_response = Column(Text, nullable=True)        # 요약된 답변

    def __repr__(self):
        return f"<ConversationMemory(chat_id={self.chat_id}, chat_room_id={self.chat_room_id}, user_id={self.user_id})>"
