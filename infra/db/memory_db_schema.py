'''
메모리 데이터베이스 스키마
- chat_room_id: 채팅창 ID (conversation_id와 동일)
- case_type: 데이터 타입 구분 (SIMULATION_Q, INFERENCE_Q, BIO_Q, PROTOCOL_Q)
- full_response: 원본 답변 저장
- summary: 질문과 답변 요약 저장
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
    case_type으로 데이터 타입 구분, full_response와 summary에 답변 저장.
    """

    __tablename__ = "t_memory"

    # 이미지 순서대로 컬럼 정의
    chat_sid = Column(Integer, Sequence('chat_sid_seq'), primary_key=True, autoincrement=True)  # 채팅응답아이디 (PK)
    chat_room_id = Column(String, nullable=False, index=True)  # 채팅방 아이디
    user_id = Column(String, nullable=False)  # 유저 아이디
    case_type = Column(String, nullable=False, index=True)  # 질문유형
    original_question = Column(Text)  # 질문 원문
    full_response = Column(Text, nullable=True)  # 원본 답변 전체
    summary = Column(Text, nullable=True)  # 질문과 답변 요약
    topic = Column(String)  # 1줄주제요약
    referenced_memory_count = Column(Integer, default=0)  # 참고한 이전 대화 개수
    
    # 추가 메타 정보 (이미지에는 없지만 기존 기능 유지)
    entities = Column(JSONB, default=list)  # retrieval에서 추출된 엔티티들
    created_at = Column(DateTime, default=datetime.utcnow)  # 생성시간
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)  # 수정시간
    def __repr__(self):
        return f"<ConversationMemory(chat_sid={self.chat_sid}, chat_room_id={self.chat_room_id}, user_id={self.user_id})>"