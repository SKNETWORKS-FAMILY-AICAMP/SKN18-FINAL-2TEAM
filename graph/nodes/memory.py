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
from graph.llm_config import memory_summarize_tool_llm


CONTEXT_WINDOW_MAX = 10
MEMORY_CONTEXT_LIMIT = 3  # State 전달 시 최근 N개만
CASE_HISTORY_LIMIT = 5    # 각 케이스별 최대 저장 개수

# 지원하는 케이스 타입 목록
VALID_CASE_TYPES = ["SIMULATION_Q", "INFERENCE_Q", "BIO_Q", "PROTOCOL_Q"]


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

        summary = memory_summarize_tool_llm(prompt).strip()
        
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
        
        # 케이스 타입과 요약 답변 가져오기
        last_case_type = latest_conv.case_type or ""
        last_answer_summary = latest_conv.summarize_response or ""
        
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
            summary_preview = (conv.summarize_response or "")[:30] + "..." if conv.summarize_response else "N/A"
            print(f"[MemoryRead] chat_id={conv.chat_id}, case_type={conv.case_type}, created_at={conv.created_at}, summary={summary_preview}")
        
        # 가장 최근 대화 정보
        last_case = None
        last_summary = None
        if conversations:
            latest = conversations[0]
            last_summary = latest.summarize_response
            last_case = latest.case_type
        
        state["memory_slot"] = {
            "last_case": last_case,
            "last_summary": last_summary,
        }
        
        # 어떤 케이스 타입의 히스토리를 가져올지 결정
        current_case = state.get("case_type")
        is_follow_up = state.get("is_follow_up", False)
        reference_case = state.get("reference_case_type")
        
        # 꼬리질문이어도 원본 질문의 case_type을 기준으로 조회
        # 예: "내가 최근에 물어봤던 논문 내용이 뭐더라?" → BIO_Q로 분류 → BIO_Q 타입 메모리 조회
        target_case_type = current_case
        if is_follow_up:
            history_source = "FOLLOW_UP"
            print(f"[MemoryRead] 꼬리질문 감지: 원본 질문 타입({current_case}) 기준으로 히스토리 로드")
            if reference_case and reference_case != current_case:
                print(f"[MemoryRead] 참고: 이전 대화 타입은 {reference_case}였지만, 원본 질문 타입({current_case}) 기준으로 조회")
        else:
            history_source = "CURRENT_TYPE"
            print(f"[MemoryRead] 일반 질문: {current_case} 타입 히스토리 로드")
        
        # 해당 케이스 타입의 히스토리만 최대 5개 조회
        relevant_conversations = [
            conv for conv in conversations 
            if conv.case_type == target_case_type and conv.summarize_response
        ][:CASE_HISTORY_LIMIT]  # 최대 5개
        
        # relevant_history 구성
        state["relevant_history"] = [
            {
                "chat_id": conv.chat_id,
                "question": conv.original_question,
                "answer_summary": conv.summarize_response,
                "keywords": conv.latest_keywords or []
            }
            for conv in relevant_conversations
        ]
        state["history_source"] = history_source

        # 노드 종료 로그
        print(f"\n[MEMORY_READ NODE] 종료")
        print(f"  memory_slot: {state.get('memory_slot', {})}")
        print(f"  relevant_history: {len(state.get('relevant_history', []))}개 (타입: {target_case_type}, 소스: {history_source})")
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
            
            # 유효한 케이스 타입인지 확인
            if current_case_type in VALID_CASE_TYPES:
                # 답변 생성 시 참고한 이전 대화 개수 계산
                referenced_count = 0
                if current_case_type == "SIMULATION_Q":
                    referenced_count = len(state.get("simulation_q_history", []))
                elif current_case_type == "INFERENCE_Q":
                    referenced_count = len(state.get("inference_q_history", []))
                elif current_case_type == "BIO_Q":
                    referenced_count = len(state.get("bio_q_history", []))
                elif current_case_type == "PROTOCOL_Q":
                    referenced_count = len(state.get("protocal_q_history", []))
                
                # 새 ConversationMemory row 생성
                new_memory = ConversationMemory(
                    chat_room_id=chat_room_id,
                    user_id=user_id,
                    original_question=state.get("question", ""),
                    topic=" ".join(state.get("extracted_keywords", [])[:3]),
                    entities=state.get("extracted_entities", []) or [],
                    latest_keywords=state.get("extracted_keywords", []) or [],
                    referenced_memory_count=referenced_count,
                    case_type=current_case_type,
                    full_response=full_answer,
                    summarize_response=answer_summary
                )
                
                db.add(new_memory)
                db.commit()

                print(f"[MemoryWrite] 새 row 생성: chat_id={new_memory.chat_id}, case_type={current_case_type}")
                print(f"[MemoryWrite] 저장 완료:")
                print(f"  - case_type: {current_case_type}")
                print(f"  - referenced_memory_count: {referenced_count}개")
                print(f"  - full_response: {len(full_answer)}자")
                print(f"  - summarize_response: {answer_summary[:50]}...")
            else:
                print(f"[MemoryWrite] Warning: 알 수 없는 case_type입니다: {current_case_type}")

        # 노드 종료 로그
        print(f"\n[MEMORY_WRITE NODE] 종료")
        print(f"  저장 완료: case_type={current_case_type}")
        print(f"{'='*60}\n")
        
        return state

    finally:
        db.close()
