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
from memory_db_schema import ConversationMemory
from datetime import datetime
from graph.nodes.call_llm import gpt4o_mini


CONTEXT_WINDOW_MAX = 10
MEMORY_CONTEXT_LIMIT = 3  # State 전달 시 최근 N개만
CASE_HISTORY_LIMIT = 5    # 각 케이스별 최대 저장 개수

# 케이스 타입 매핑 (classifier에서 반환하는 case_type → DB 컬럼명)
# NO_RELATION은 저장하지 않음
# 각 컬럼은 JSONB 타입으로 {"full_response": "원본", "summarize_response": "요약"} 형태로 저장
CASE_TYPE_TO_COLUMN = {
    "SIMULATION_Q": "simulation_q",
    "INFERENCE_Q": "inference_q",
    "BIO_Q": "bio_q",
    "PROTOCOL_Q": "protocal_q",
}


# ---------------------------------------------
# 🔹 응답 요약 함수 (LLM 기반)
# ---------------------------------------------
def summarize_llm_response(full_response: str, max_length: int = 200) -> str:
    """
    LLM을 사용하여 응답을 의미있게 요약
    
    Args:
        full_response: 전체 LLM 응답
        max_length: 최대 요약 길이
    
    Returns:
        요약된 응답
    """
    if not full_response:
        return ""
    
    # 이미 짧으면 그대로 반환
    if len(full_response) <= max_length:
        return full_response
    
    # LLM으로 요약
    try:
        prompt = f"""다음 답변을 핵심 내용만 {max_length}자 이내로 간결하게 요약하세요.

원본 답변:
{full_response}

요약 규칙:
1. 핵심 정보만 포함
2. 리스트 형식이면 주요 항목만 언급 (전체 나열 금지)
3. {max_length}자 이내로 작성
4. 자연스럽고 완전한 문장으로 마무리
5. 불완전한 문장이나 숫자로 끝나지 않기

요약만 출력하세요:"""

        summary = gpt4o_mini(prompt).strip()
        
        # 길이 초과 시 문장 단위로 자르기
        if len(summary) > max_length:
            # 마지막 완전한 문장까지만 포함
            sentences = summary[:max_length].split('.')
            if len(sentences) > 1:
                summary = '.'.join(sentences[:-1]) + '.'
            else:
                summary = summary[:max_length-3] + "..."
        
        print(f"[Summarize] LLM 요약 완료: {len(full_response)}자 → {len(summary)}자")
        return summary
        
    except Exception as e:
        print(f"[Summarize] LLM 요약 실패: {e}, fallback 사용")
        # fallback: 첫 문장만 추출
        sentences = full_response.split('.')
        if sentences and sentences[0]:
            fallback = sentences[0] + '.'
            if len(fallback) > max_length:
                fallback = fallback[:max_length-3] + "..."
            return fallback
        return full_response[:max_length-3] + "..."


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
            answer_data = getattr(latest_conv, column_name, None)
            if answer_data:
                last_case_type = case_type
                # JSONB에서 요약본 추출
                last_answer_summary = answer_data.get("summarize_response", "") if isinstance(answer_data, dict) else ""
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
                answer_data = getattr(conv, column_name, None)
                if answer_data and len(case_histories[case_type]) < MEMORY_CONTEXT_LIMIT:
                    # JSONB에서 요약본만 추출
                    answer_summary = answer_data.get("summarize_response", "") if isinstance(answer_data, dict) else ""
                    
                    if answer_summary:  # 요약본이 있는 경우만 추가
                        case_histories[case_type].append({
                            "chat_id": conv.chat_id,  # chat_id 추가
                            "question": conv.original_question,
                            "answer_summary": answer_summary,  # 요약본만 state로 전달
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
                
                # JSONB 형태로 원본 + 요약 함께 저장
                answer_json = {
                    "full_response": full_answer,
                    "summarize_response": answer_summary
                }
                setattr(new_memory, case_column, answer_json)
                
                db.add(new_memory)
                db.commit()

                print(f"[MemoryWrite] 새 row 생성: chat_id={new_memory.chat_id}, case_type={current_case_type}")
                print(f"[MemoryWrite] JSON 저장 ({case_column}):")
                print(f"  - full_response: {len(full_answer)}자")
                print(f"  - summarize_response: {answer_summary[:50]}...")
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
