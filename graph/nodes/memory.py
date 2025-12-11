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


CONTEXT_WINDOW_MAX = 10
MEMORY_CONTEXT_LIMIT = 3  # State 전달 시 최근 N개만
CASE_HISTORY_LIMIT = 5    # 각 케이스별 최대 저장 개수

# 케이스 타입 매핑 (classifier에서 반환하는 case_type → DB 컬럼명)
# NO_RELATION은 저장하지 않음
CASE_TYPE_TO_COLUMN = {
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
        
        # chat_room_id로 가장 최근 대화 조회
        latest_conv = (
            db.query(ConversationMemory)
            .filter_by(chat_room_id=chat_room_id, user_id=user_id)
            .order_by(ConversationMemory.created_at.desc())
            .first()
        )
        
        if not latest_conv:
            return {
                "last_question": "",
                "last_answer_summary": "",
                "last_case_type": "",
                "last_topic": "",
                "has_previous": False
            }
        
        # 케이스 타입 확인 (어느 컬럼에 값이 있는지)
        last_case_type = ""
        last_answer_summary = ""
        for case_type, column_name in CASE_TYPE_TO_COLUMN.items():
            value = getattr(latest_conv, column_name, None)
            if value:
                last_case_type = case_type
                last_answer_summary = value
                break
        
        return {
            "last_question": latest_conv.original_question or "",
            "last_answer_summary": last_answer_summary,
            "last_case_type": last_case_type,
            "last_topic": latest_conv.topic or "",
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
    
    # 노드 진입 로그
    print(f"\n{'='*60}")
    print(f"[MEMORY_READ NODE] 시작")
    print(f"  question: {str(state.get('question', ''))[:30]}...")
    print(f"  conversation_id: {state.get('conversation_id', '')}")
    print(f"  case_type: {state.get('case_type', '')}")
    print(f"{'='*60}\n")

    chat_room_id = state.get("conversation_id")
    user_id = state.get("user_id", "default")

    db = Connect_PostgreSQL()
    try:
        # chat_room_id로 모든 대화 조회 (최신순)
        conversations = (
            db.query(ConversationMemory)
            .filter_by(chat_room_id=chat_room_id, user_id=user_id)
            .order_by(ConversationMemory.created_at.desc())
            .all()
        )
        
        # 조회된 대화들의 chat_id 로그
        print(f"\n[MemoryRead] 조회된 대화 개수: {len(conversations)}")
        for conv in conversations:
            case_cols = [f"{col}={getattr(conv, col, '')[:30]}..." for _, col in CASE_TYPE_TO_COLUMN.items() if getattr(conv, col, None)]
            print(f"[MemoryRead] chat_id={conv.chat_id}, created_at={conv.created_at}, {', '.join(case_cols)}")
        
        # 가장 최근 대화 정보
        last_case = None
        topic = None
        if conversations:
            latest = conversations[0]
            topic = latest.topic
            # 어느 컬럼에 값이 있는지 확인
            for case_type, column_name in CASE_TYPE_TO_COLUMN.items():
                if getattr(latest, column_name, None):
                    last_case = case_type
                    break
        
        state["memory_slot"] = {
            "last_case": last_case,
            "topic": topic,
        }
        
        # 각 케이스 타입별 히스토리 (최근 N개만)
        case_histories = {
            "SIMULATION_Q": [],
            "INFERENCE_Q": [],
            "BIO_Q": [],
            "PROTOCOL_Q": [],
        }
        
        for conv in conversations:
            for case_type, column_name in CASE_TYPE_TO_COLUMN.items():
                answer_summary = getattr(conv, column_name, None)
                if answer_summary and len(case_histories[case_type]) < MEMORY_CONTEXT_LIMIT:
                    case_histories[case_type].append({
                        "question": conv.original_question,
                        "answer_summary": answer_summary,
                        "keywords": conv.latest_keywords or []
                    })
        
        state["simulation_q_history"] = case_histories["SIMULATION_Q"]
        state["inference_q_history"] = case_histories["INFERENCE_Q"]
        state["bio_q_history"] = case_histories["BIO_Q"]
        state["protocal_q_history"] = case_histories["PROTOCOL_Q"]
        state["system_log"] = append_log(state, f"[memory_read] Loaded {len(conversations)} conversations for {chat_room_id}")

        # 노드 종료 로그
        print(f"\n[MEMORY_READ NODE] 종료")
        print(f"  memory_slot: {state.get('memory_slot', {})}")
        print(f"  히스토리 개수: SIM={len(case_histories['SIMULATION_Q'])}, INF={len(case_histories['INFERENCE_Q'])}, BIO={len(case_histories['BIO_Q'])}, PROT={len(case_histories['PROTOCOL_Q'])}")
        print(f"{'='*60}\n")

        return state

    finally:
        db.close()


# ---------------------------------------------
# 🔹 2) Memory Write Node (마지막 단계)
# ---------------------------------------------
def memory_write_node(state):
    """
    각 질문마다 새로운 ConversationMemory row 생성.
    해당 케이스 컬럼에만 answer_summary 저장.
    """
    # 노드 진입 로그
    print(f"\n{'='*60}")
    print(f"[MEMORY_WRITE NODE] 시작")
    print(f"  question: {str(state.get('question', ''))[:30]}...")
    print(f"  case_type: {state.get('case_type', '')}")
    print(f"  final_answer: {str(state.get('final_answer', ''))[:30]}...")
    print(f"{'='*60}\n")
    
    chat_room_id = state.get("conversation_id")
    user_id = state.get("user_id", "default")
    current_case_type = state.get("case_type", "NO_RELATION")

    db = Connect_PostgreSQL()
    try:
        # NO_RELATION이 아닌 경우에만 저장
        if (state.get("question") and state.get("final_answer") 
            and current_case_type != "NO_RELATION"):

            full_answer = state.get("final_answer", "")
            answer_summary = summarize_llm_response(full_answer, max_length=200)
            
            # 케이스 컬럼 결정
            case_column = CASE_TYPE_TO_COLUMN.get(current_case_type)
            
            if case_column:
                # 새 ConversationMemory row 생성
                new_memory = ConversationMemory(
                    chat_room_id=chat_room_id,
                    user_id=user_id,
                    original_question=state.get("question", ""),
                    topic=" ".join(state.get("extracted_keywords", [])[:3]),
                    entities=state.get("extracted_entities", []) or [],
                    latest_keywords=state.get("extracted_keywords", []) or [],
                    context_window=1,
                )
                
                # 해당 케이스 컬럼에만 answer_summary 저장
                setattr(new_memory, case_column, answer_summary)
                
                db.add(new_memory)
                db.commit()
                
                print(f"[MemoryWrite] 새 row 생성: chat_id={new_memory.chat_id}, case_type={current_case_type}")
                print(f"[MemoryWrite] {case_column} 컬럼에 저장: {answer_summary[:50]}...")
            else:
                print(f"[MemoryWrite] Warning: {current_case_type}에 대한 컬럼 매핑이 없습니다.")

        state["system_log"] = append_log(state, f"[memory_write] new row for {current_case_type}")
        
        # 노드 종료 로그
        print(f"\n[MEMORY_WRITE NODE] 종료")
        print(f"  저장 완료: case_type={current_case_type}")
        print(f"{'='*60}\n")
        
        return state
        
    finally:
        db.close()
