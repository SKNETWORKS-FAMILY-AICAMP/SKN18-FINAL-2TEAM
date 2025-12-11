'''
메모리 데이터베이스 스키마
- chat_room_id: 채팅창 ID (conversation_id와 동일)
- 케이스 타입별 컬럼으로 대화 관리
- 각 타입별 최근 대화를 효율적으로 조회
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
    케이스 타입별 컬럼에 answer_summary만 저장.
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
    context_window = Column(Integer, default=0)  # 전체 대화 수

    # ---------------------------
    # 케이스 타입별 답변 요약 (각 컬럼에 answer_summary만 저장)
    # ---------------------------
    simulation_q = Column(Text, nullable=True)   # SIMULATION_Q 답변 요약
    inference_q = Column(Text, nullable=True)    # INFERENCE_Q 답변 요약
    bio_q = Column(Text, nullable=True)          # BIO_Q 답변 요약
    protocal_q = Column(Text, nullable=True)     # PROTOCOL_Q 답변 요약

    # 확장 필드
    extra = Column(JSONB, default=dict)

    def to_dict(self):
        """ORM 객체를 딕셔너리로 변환"""
        return {
            "chat_id": self.chat_id,
            "chat_room_id": self.chat_room_id,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "original_question": self.original_question,
            "topic": self.topic,
            "latest_keywords": self.latest_keywords or [],
            "entities": self.entities or [],
            "context_window": self.context_window,
            "simulation_q": self.simulation_q,
            "inference_q": self.inference_q,
            "bio_q": self.bio_q,
            "protocal_q": self.protocal_q,
            "extra": self.extra or {}
        }

    def __repr__(self):
        return f"<ConversationMemory(chat_id={self.chat_id}, chat_room_id={self.chat_room_id}, user_id={self.user_id})>"




# ---------------------------
# 응답 요약 함수
# ---------------------------
def summarize_llm_response(full_response: str, max_length: int = 200) -> str:
    """
    LLM 응답을 요약해서 저장용으로 변환
    
    Args:
        full_response: 전체 LLM 응답
        max_length: 최대 요약 길이
    
    Returns:
        요약된 응답
    """
    if not full_response:
        return ""
    
    # 1. 기본 길이 제한
    if len(full_response) <= max_length:
        return full_response
    
    # 2. 문장 단위로 자르기
    sentences = full_response.split('.')
    summary = ""
    
    for sentence in sentences:
        if len(summary + sentence + ".") <= max_length:
            summary += sentence + "."
        else:
            break
    
    # 3. 빈 요약이면 강제로 자르기
    if not summary.strip():
        summary = full_response[:max_length-3] + "..."
    
    return summary.strip()
