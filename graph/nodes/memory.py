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
VALID_CASE_TYPES = ["SIMULATION_Q", "INFERENCE_Q", "BIO_Q", "PROTOCOL_Q", "USER_INFO"]


# ---------------------------------------------
# 🔹 질문과 응답 요약 함수 (LLM 기반)
# ---------------------------------------------
def summarize_llm_response(question: str, full_response: str, max_length: int = 500) -> str:
    """
    LLM을 사용하여 질문과 응답을 함께 요약
    
    Args:
        question: 사용자 질문
        full_response: 전체 LLM 응답
        max_length: 최대 요약 길이 (기본값 500자)
    
    Returns:
        "~질문에 대한 응답으로 ~~~다." 형식의 요약
    """
    if not full_response or not question:
        return ""
    
    # 응답 길이에 따라 문장 수 결정
    response_length = len(full_response)
    if response_length < 500:
        sentence_count = 3
        target_length = 300
    else:
        sentence_count = 10
        target_length = max_length
    
    # LLM으로 요약
    try:
        prompt = f"""다음 질문과 답변을 "{question[:50]}... 질문에 대한 응답으로" 형식으로 시작하여 요약하세요.

질문:
{question}

답변:
{full_response}

요약 규칙:
1. 반드시 "~질문에 대한 응답으로"로 시작하고 "~다."로 끝내기
2. 질문의 핵심과 답변의 주요 내용을 모두 포함
3. {"3문장" if response_length < 500 else "10문장 미만"}으로 작성
4. {target_length}자 이내로 작성
5. 자연스럽고 완전한 문장으로 구성
6. 리스트 형식이면 주요 항목만 언급

요약만 출력하세요:"""

        summary = memory_summarize_tool_llm(prompt).strip()
        
        # 길이 초과 시 문장 단위로 자르기
        if len(summary) > target_length:
            # 마지막 완전한 문장까지만 포함
            sentences = summary[:target_length].split('.')
            if len(sentences) > 1:
                summary = '.'.join(sentences[:-1]) + '.'
            else:
                summary = summary[:target_length-3] + "..."
        
        print(f"[Summarize] Q&A 요약 완료: 질문 {len(question)}자 + 응답 {len(full_response)}자 → 요약 {len(summary)}자 ({sentence_count}문장)")
        return summary
        
    except Exception as e:
        print(f"[Summarize] LLM 요약 실패: {e}, fallback 사용")
        # fallback: 질문 요약 + 답변 첫 문장
        question_summary = question[:50] + "..." if len(question) > 50 else question
        sentences = full_response.split('.')
        if sentences and sentences[0]:
            fallback = f"{question_summary} 질문에 대한 응답으로 {sentences[0]}."
            if len(fallback) > target_length:
                fallback = fallback[:target_length-3] + "..."
            return fallback
        return f"{question_summary} 질문에 대한 응답입니다."


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
            "last_summary": "질문과 답변 요약", 
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
                "last_summary": "",
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
                "last_summary": "",
                "last_case_type": "",
                "last_topic": "",
                "has_previous": False
            }
        
        # 케이스 타입과 요약 가져오기
        last_case_type = latest_conv.case_type or ""
        last_summary = latest_conv.summary or ""
        
        return {
            "last_question": latest_conv.original_question or "",
            "last_summary": last_summary,
            "last_case_type": last_case_type,
            "last_topic": latest_conv.topic or "",
            "has_previous": True
        }
        
    except Exception as e:
        print(f"[memory_read_basic_tool Error] {e}")
        return {
            "last_question": "",
            "last_summary": "",
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
            summary_preview = (conv.summary or "")[:30] + "..." if conv.summary else "N/A"
            print(f"[MemoryRead] chat_sid={conv.chat_sid}, case_type={conv.case_type}, created_at={conv.created_at}, summary={summary_preview}")
        
        # 가장 최근 대화 정보
        last_case = None
        last_summary = None
        if conversations:
            latest = conversations[0]
            last_summary = latest.summary
            last_case = latest.case_type
        
        state["memory_slot"] = {
            "last_case": last_case,
            "last_summary": last_summary,
        }
        
        # 어떤 케이스 타입의 히스토리를 가져올지 결정
        current_case = state.get("case_type")
        is_follow_up = state.get("is_follow_up", False)
        reference_case = state.get("reference_case_type")
        
        # USER_INFO인 경우 항상 USER_INFO 타입 메모리 조회
        if current_case == "USER_INFO":
            target_case_type = "USER_INFO"
            history_source = "USER_INFO"
            print(f"[MemoryRead] USER_INFO 질문: USER_INFO 타입 히스토리 로드")
        # 꼬리질문이어도 원본 질문의 case_type을 기준으로 조회
        # 예: "내가 최근에 물어봤던 논문 내용이 뭐더라?" → BIO_Q로 분류 → BIO_Q 타입 메모리 조회
        elif is_follow_up:
            target_case_type = current_case
            history_source = "FOLLOW_UP"
            print(f"[MemoryRead] 꼬리질문 감지: 원본 질문 타입({current_case}) 기준으로 히스토리 로드")
            if reference_case and reference_case != current_case:
                print(f"[MemoryRead] 참고: 이전 대화 타입은 {reference_case}였지만, 원본 질문 타입({current_case}) 기준으로 조회")
        else:
            target_case_type = current_case
            history_source = "CURRENT_TYPE"
            print(f"[MemoryRead] 일반 질문: {current_case} 타입 히스토리 로드")
        
        # 해당 케이스 타입의 히스토리만 최대 5개 조회
        relevant_conversations = [
            conv for conv in conversations 
            if conv.case_type == target_case_type and conv.summary
        ][:CASE_HISTORY_LIMIT]  # 최대 5개
        
        # relevant_history 구성
        state["relevant_history"] = [
            {
                "chat_sid": conv.chat_sid,
                "question": conv.original_question,
                "summary": conv.summary,
                "keywords": []  # latest_keywords 컬럼 삭제로 빈 리스트 사용
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
def generate_topic_title(question: str, full_response: str) -> str:
    """
    질문과 응답을 기반으로 채팅방 제목용 1줄 요약 생성

    Args:
        question: 사용자 질문
        full_response: 전체 LLM 응답

    Returns:
        채팅방 제목으로 사용할 1줄 요약 (최대 50자)
    """
    if not question:
        return "새 대화"

    try:
        prompt = f"""다음 질문을 기반으로 채팅방 제목으로 사용할 1줄 요약을 생성하세요.

질문: {question}

요약 규칙:
1. 질문의 핵심 주제만 간결하게 추출
2. 최대 50자 이내 (공백 포함)
3. 명사구 형태로 작성 (예: "단백질 변이 분석", "KaiC 정제 프로토콜", "AlphaFold 사용법")
4. 마침표 없이 작성
5. 너무 일반적이지 않게, 구체적인 주제 포함

제목만 출력하세요:"""

        title = memory_summarize_tool_llm(prompt).strip()

        # 길이 제한
        if len(title) > 50:
            title = title[:47] + "..."

        # 마침표 제거
        title = title.rstrip('.')

        print(f"[TopicTitle] 채팅방 제목 생성: {title}")
        return title

    except Exception as e:
        print(f"[TopicTitle] 제목 생성 실패: {e}, fallback 사용")
        # fallback: 질문 앞 30자 사용
        fallback = question[:30] + "..." if len(question) > 30 else question
        return fallback


def memory_write_node(state):
    """
    각 질문마다 새로운 ConversationMemory row 생성.
    해당 케이스 컬럼에만 summary 저장.
    topic 필드에 채팅방 제목용 1줄 요약 저장.
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
            question = state.get("question", "")

            # topic (채팅방 제목) 생성
            topic_title = generate_topic_title(question, full_answer)
            state["chat_title"] = topic_title  # Django로 전달용

            # USER_INFO인 경우 요약은 사용자의 인적사항 1문장만
            if current_case_type == "USER_INFO":
                # LLM을 사용하여 사용자 인적사항을 1문장으로 요약
                try:
                    prompt = f"""다음 사용자의 인적사항을 1문장으로 요약하세요.

사용자 발화: {question}

요약 규칙:
1. 반드시 1문장으로 작성 (마침표 포함)
2. "사용자는 ~입니다." 또는 "사용자는 ~이다." 형식 사용
3. 핵심 신분/직업 정보만 포함 (학생, 연구원, 교수 등)
4. 50자 이내로 간결하게 작성

요약만 출력하세요:"""
                    summary = memory_summarize_tool_llm(prompt).strip()
                    
                    # 길이 제한
                    if len(summary) > 100:
                        summary = summary[:97] + "..."
                    
                    print(f"[MemoryWrite] USER_INFO 요약: {summary}")
                except Exception as e:
                    print(f"[MemoryWrite] USER_INFO 요약 실패: {e}, fallback 사용")
                    # fallback: 질문을 그대로 사용하되 50자로 제한
                    summary = question[:50] + "..." if len(question) > 50 else question
            else:
                # 기존 로직: 일반 요약
                summary = summarize_llm_response(question, full_answer, max_length=500)
            
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
                elif current_case_type == "USER_INFO":
                    referenced_count = 0  # USER_INFO는 이전 대화 참고 없음
                
                # 새 ConversationMemory row 생성
                new_memory = ConversationMemory(
                    chat_room_id=chat_room_id,
                    user_id=user_id,
                    original_question=state.get("question", ""),
                    topic=topic_title,  # 채팅방 제목용 1줄 요약
                    entities=state.get("extracted_entities", []) or [],
                    referenced_memory_count=referenced_count,
                    case_type=current_case_type,
                    full_response=full_answer,
                    summary=summary
                )
                
                db.add(new_memory)
                db.commit()

                print(f"[MemoryWrite] 새 row 생성: chat_sid={new_memory.chat_sid}, case_type={current_case_type}")
                print(f"[MemoryWrite] 저장 완료:")
                print(f"  - case_type: {current_case_type}")
                print(f"  - topic: {topic_title}")
                print(f"  - referenced_memory_count: {referenced_count}개")
                print(f"  - full_response: {len(full_answer)}자")
                print(f"  - summary: {summary[:50]}...")
            else:
                print(f"[MemoryWrite] Warning: 알 수 없는 case_type입니다: {current_case_type}")

        # 노드 종료 로그
        print(f"\n[MEMORY_WRITE NODE] 종료")
        print(f"  저장 완료: case_type={current_case_type}")
        print(f"{'='*60}\n")
        
        return state

    finally:
        db.close()
