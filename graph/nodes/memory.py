"""
memory.py
-------------------------------------
LangGraph Memory Node (Read / Write)
케이스 타입별 컬럼 구조로 메모리 관리
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../infra/db'))

from memory_db_stetting import Connect_PostgreSQL
from memory_db_schema import ConversationMemory, summarize_llm_response
from datetime import datetime
from sqlalchemy.orm.attributes import flag_modified


CONTEXT_WINDOW_MAX = 10
MEMORY_CONTEXT_LIMIT = 3  # State 전달 시 최근 N개만
CASE_HISTORY_LIMIT = 5    # 각 케이스별 최대 저장 개수

# 케이스 타입 매핑 (classifier에서 반환하는 case_type → DB 컬럼명)
# no_relation은 저장하지 않음
CASE_TYPE_COLUMNS = {
    "SIMULATION_Q": "simulation_q",
    "INFERENCE_Q": "inference_q",
    "BIO_Q": "bio_q",
    "PROTOCOL_Q": "protocal_q",
}


# ---------------------------------------------
# 🔹 system_log append helper (노드 반환 시 병합)
# ---------------------------------------------
def append_log(state, message: str):
    logs = state.get("system_log", [])
    logs.append(message)
    return logs


# ---------------------------------------------
# 🔹 0) Memory Read Basic Tool (for classifier)
# ---------------------------------------------
def memory_read_basic_tool(chat_room_id: str, user_id: str = "default") -> dict:
    """
    이전 대화 참조가 필요할 때 호출되는 도구
    chat_room_id 기준으로 가장 최근 대화 1개만 조회
    
    Args:
        chat_room_id (str): 채팅방 ID
        user_id (str): 사용자 ID (기본값: "default")
        
    Returns:
        dict: 직전 대화 정보
        {
            "last_question": "이전 질문",
            "last_answer_summary": "이전 답변 요약", 
            "last_case_type": "BIO_Q",
            "last_topic": "단백질 폴딩",
            "has_previous": True/False
        }
    """
    db = Connect_PostgreSQL()
    try:
        # 메모리 조회
        memory = (
            db.query(ConversationMemory)
            .filter_by(chat_room_id=chat_room_id, user_id=user_id)
            .first()
        )
        
        if memory is None:
            return {
                "last_question": "",
                "last_answer_summary": "",
                "last_case_type": "",
                "last_topic": "",
                "has_previous": False
            }
        
        # 모든 케이스 타입 컬럼에서 가장 최근 대화 찾기
        all_conversations = []
        
        for case_type, column_name in CASE_TYPE_COLUMNS.items():
            case_history = getattr(memory, column_name, []) or []
            if case_history:
                # 가장 최근 대화 (배열의 마지막 요소)
                latest_conv = case_history[-1]
                latest_conv["case_type"] = case_type  # 이미 대문자
                all_conversations.append(latest_conv)
        
        if not all_conversations:
            return {
                "last_question": "",
                "last_answer_summary": "",
                "last_case_type": "",
                "last_topic": "",
                "has_previous": False
            }
        
        # timestamp 기준으로 가장 최근 대화 선택
        latest_conversation = max(all_conversations, 
                                key=lambda x: x.get("timestamp", ""))
        
        return {
            "last_question": latest_conversation.get("question", ""),
            "last_answer_summary": latest_conversation.get("answer_summary", ""),
            "last_case_type": latest_conversation.get("case_type", ""),
            "last_topic": " ".join(latest_conversation.get("keywords", [])[:3]),
            "has_previous": True
        }
        
    except Exception as e:
        print(f"[memory_read_basic_tool Error] {e}")
        return {
            "last_question": "",
            "last_answer_summary": "",
            "last_case_type": "",
            "last_topic": "",
            "has_previous": False
        }
    finally:
        db.close()


# ---------------------------------------------
# 🔹 1) Memory Read Node
# ---------------------------------------------
def memory_read_node(state):
    """
    chat_room_id, user_id로 DB 메모리를 불러와 state에 넣는다.
    - memory_slot: 슬롯 메모리 (last_question, original_question, topic, entities 등)
    - xxx_history: 각 케이스 타입별 대화 히스토리 (선택적)
    """

    chat_room_id = state.get("conversation_id")
    user_id = state.get("user_id", "default")

    db = Connect_PostgreSQL()
    try:
        # 1. 메모리 조회 (없으면 신규 생성)
        memory = (
            db.query(ConversationMemory)
            .filter_by(chat_room_id=chat_room_id, user_id=user_id)
            .first()
        )

        if memory is None:
            memory = ConversationMemory(
                chat_room_id=chat_room_id,
                user_id=user_id,
            )
            db.add(memory)
            db.commit()
            db.refresh(memory)  # 자동증가된 chat_id 값을 가져오기 위해 refresh

        # 2. state에 메모리 정보 직접 추가 (히스토리에서 마지막 케이스 추출)
        last_case = None
        last_conversation = None
        
        # 모든 케이스 타입에서 가장 최근 대화 찾기
        all_conversations = []
        for case_type, column_name in CASE_TYPE_COLUMNS.items():
            case_history = getattr(memory, column_name, []) or []
            if case_history:
                latest_conv = case_history[-1]
                latest_conv["case_type"] = case_type
                all_conversations.append(latest_conv)
        
        if all_conversations:
            # timestamp 기준으로 가장 최근 대화 선택
            last_conversation = max(all_conversations, 
                                  key=lambda x: x.get("timestamp", ""))
            last_case = last_conversation.get("case_type")
        
        state["memory_slot"] = {
            "last_case": last_case,
            "topic": memory.topic,
        }
        
        # 3. 각 케이스 타입별 히스토리 (최근 N개만)
        # no_relation은 히스토리를 저장하지 않음
        state["simulation_q_history"] = (memory.simulation_q or [])[-MEMORY_CONTEXT_LIMIT:]
        state["inference_q_history"] = (memory.inference_q or [])[-MEMORY_CONTEXT_LIMIT:]
        state["bio_q_history"] = (memory.bio_q or [])[-MEMORY_CONTEXT_LIMIT:]
        state["protocal_q_history"] = (memory.protocal_q or [])[-MEMORY_CONTEXT_LIMIT:]
        state["system_log"] = append_log(state, f"[memory_read] Loaded memory for {chat_room_id}")

        return state

    finally:
        db.close()


# ---------------------------------------------
# 🔹 2) Memory Write Node (마지막 단계)
# ---------------------------------------------
def memory_write_node(state):
    """
    그래프 종료 직전 메모리를 DB에 저장하는 노드.
    케이스 타입별 컬럼에 대화를 JSONB 배열로 저장.
    """
    chat_room_id = state.get("conversation_id")
    user_id = state.get("user_id", "default")
    current_case_type = state.get("case_type", "NO_RELATION")

    db = Connect_PostgreSQL()
    try:
        # 1. 메모리 조회 또는 생성
        memory = (
            db.query(ConversationMemory)
            .filter_by(chat_room_id=chat_room_id, user_id=user_id)
            .first()
        )

        if memory is None:
            memory = ConversationMemory(
                chat_room_id=chat_room_id,
                user_id=user_id,
            )
            db.add(memory)
            db.flush()  # chat_id 값을 즉시 생성하기 위해 flush

        # 2. Slot Memory 업데이트 (메타데이터)
        memory.latest_keywords = state.get("extracted_keywords", [])
        memory.entities = state.get("extracted_entities", [])

        # Original Question 업데이트: 첫 대화거나 is_follow_up=False인 경우 갱신
        current_question = state.get("question")
        is_follow_up = state.get("is_follow_up", False)

        if not memory.original_question or not is_follow_up:
            memory.original_question = current_question

        # Topic 업데이트 (키워드 기반 간단 요약)
        if state.get("extracted_keywords"):
            memory.topic = " ".join(state["extracted_keywords"][:3])

        # 3. 케이스 타입별 컬럼에 대화 추가 (NO_RELATION은 제외)
        if (state.get("question") and state.get("final_answer") and 
            current_case_type != "NO_RELATION"):
            
            full_answer = state.get("final_answer", "")
            answer_summary = summarize_llm_response(full_answer, max_length=200)

            # 새 대화 객체 (모든 필드 포함)
            new_conversation = {
                "question": state.get("question", ""),
                "answer_summary": answer_summary,
                "answer_full": full_answer,
                "timestamp": datetime.utcnow().isoformat(),
                "keywords": state.get("extracted_keywords", []) or [],
                "entities": state.get("extracted_entities", []) or [],
                "sources": state.get("answer_sources", []) or []
            }

            # 디버깅: 저장되는 데이터 확인
            print(f"[MemoryWrite] 저장할 대화 데이터: {list(new_conversation.keys())}")
            print(f"[MemoryWrite] question: {new_conversation['question'][:50]}...")
            print(f"[MemoryWrite] answer_full 길이: {len(new_conversation['answer_full'])}")
            print(f"[MemoryWrite] keywords 개수: {len(new_conversation['keywords'])}")
            print(f"[MemoryWrite] entities 개수: {len(new_conversation['entities'])}")

            # 해당 케이스 타입 컬럼에 추가 (NO_RELATION은 매핑에서 제외됨)
            case_column = CASE_TYPE_COLUMNS.get(current_case_type)
            if case_column:  # 유효한 케이스 타입인 경우만 저장
                case_history = getattr(memory, case_column, []) or []

                # 배열에 추가
                case_history.append(new_conversation)

                # 최대 개수 제한 (오래된 것부터 삭제)
                if len(case_history) > CASE_HISTORY_LIMIT:
                    case_history = case_history[-CASE_HISTORY_LIMIT:]

                # 업데이트
                setattr(memory, case_column, case_history)

                # SQLAlchemy가 JSONB 변경을 감지하도록 플래그 설정
                flag_modified(memory, case_column)
                
                print(f"[MemoryWrite] {case_column} 컬럼에 저장 완료 (총 {len(case_history)}개 대화)")
            else:
                print(f"[MemoryWrite] Warning: {current_case_type}에 대한 컬럼 매핑이 없습니다.")

            # context_window 증가
            memory.context_window = (memory.context_window or 0) + 1

        db.commit()

        # state에 시스템 로그 추가
        state["system_log"] = append_log(state, f"[memory_write] Saved to {current_case_type} column")
        
        return state

    finally:
        db.close()
