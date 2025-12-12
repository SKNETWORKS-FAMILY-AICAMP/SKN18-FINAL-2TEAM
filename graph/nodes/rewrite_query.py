"""
query_rewrite_agent.py (구 rewrite_query.py)
--------------------
LLM이 3가지 tool을 판단하여 사용하는 에이전트 노드
- change_date_tool: 날짜 정규화
- keyword_extractor_tool: 키워드/엔티티 추출 (필수 호출)
- query_simplifier_tool: 질문 단순화
"""

from typing import Dict, Any, List
import json
from datetime import datetime, timedelta
from graph.nodes.call_llm import gpt4o_mini

try:
    import dateparser
except ImportError:
    print("[Warning] dateparser 설치 필요: pip install dateparser")
    dateparser = None


# ============================================
# 🔹 Tool 1: 날짜 정규화 (LLM 기반)
# ============================================
def change_date_tool(query: str) -> str:
    """
    상대적 시간 표현을 절대 날짜로 변환 (LLM 사용)
    
    예시:
        "올해 논문" → "2025년 논문"
        "최근 3년" → "2022-2025"
        "작년 6월" → "2024년 6월"
        "3일 전" → "2025년 12월 9일"
        "어제 오후 3시" → "2025년 12월 11일 15시"
    
    Args:
        query: 원본 질문
        
    Returns:
        날짜가 정규화된 질문
    """
    now = datetime.now()
    current_time_info = {
        "year": now.year,
        "month": now.month,
        "day": now.day,
        "hour": now.hour,
        "minute": now.minute,
        "weekday": now.strftime("%A"),
        "date": now.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    prompt = f"""현재 시간 정보를 기준으로 질문 속의 상대적 시간 표현을 절대 시간으로 변환하세요.

현재 시간: {current_time_info['date']}
- 년: {current_time_info['year']}
- 월: {current_time_info['month']}
- 일: {current_time_info['day']}
- 시각: {current_time_info['hour']}시 {current_time_info['minute']}분
- 요일: {current_time_info['weekday']}

원본 질문: {query}

변환 규칙:
1. 상대적 시간 표현(올해, 작년, 최근 N년, N일 전, 어제, 오늘, 지난주, 지난달 등)을 절대 날짜로 변환
2. 연월일시간 모두 처리 가능 (예: "3일 전 오후 2시" → "2025년 12월 9일 14시")
3. 범위 표현도 처리 (예: "최근 3년" → "2022-2025")
4. 날짜 표현이 없으면 원본 그대로 반환
5. 자연스러운 한국어/영어 유지

변환된 질문만 출력하세요 (설명 없이):"""

    try:
        normalized_query = gpt4o_mini(prompt).strip()
        
        # LLM이 실패하거나 이상한 결과를 반환한 경우 원본 반환
        if not normalized_query or len(normalized_query) > len(query) * 3:
            print(f"[change_date_tool] LLM 결과 이상, 원본 반환")
            return query
        
        print(f"[change_date_tool] '{query}' → '{normalized_query}'")
        return normalized_query
        
    except Exception as e:
        print(f"[change_date_tool] 오류: {e}, 원본 반환")
        return query


# ============================================
# 🔹 Tool 2: 키워드/엔티티 추출 (필수 호출)
# ============================================
def keyword_extractor_tool(question: str) -> Dict[str, List[str]]:
    """
    질문에서 검색에 필요한 핵심 엔티티와 키워드 추출
    
    예시:
        "KaiC 단백질 정제 yield 개선 방법?" 
        → {
            "keywords": ["KaiC", "protein purification", "low yield"],
            "entities": ["KaiC"]
        }
    
    Args:
        question: 사용자 질문
        
    Returns:
        {"keywords": [...], "entities": [...]}
    """
    prompt = f"""다음 질문에서 검색에 필요한 키워드와 엔티티를 추출하세요.

질문: {question}

규칙:
1. entities: 정확한 실체 이름 (단백질명, 유전자명, 기법명 등 고유명사)
2. keywords: 검색 강화를 위한 의미적 키워드 (개념, 동작, 속성 등)

출력 형식 (반드시 JSON):
{{
  "entities": ["KaiC", "phosphorylation"],
  "keywords": ["protein purification", "yield improvement", "optimization"]
}}

JSON만 출력하세요:"""

    try:
        response = gpt4o_mini(prompt).strip()
        
        # JSON 파싱
        result = json.loads(response)
        keywords = result.get("keywords", [])
        entities = result.get("entities", [])
        
        print(f"[keyword_extractor_tool] keywords: {keywords}, entities: {entities}")
        return {"keywords": keywords, "entities": entities}
        
    except Exception as e:
        print(f"[keyword_extractor_tool] 오류: {e}, 빈 결과 반환")
        return {"keywords": [], "entities": []}


# ============================================
# 🔹 Tool 3: 질문 단순화
# ============================================
def query_simplifier_tool(question: str) -> str:
    """
    질문을 검색 엔진이 좋아하는 짧고 명확한 검색 쿼리로 변환
    
    예시:
        "혹시 KaiC 단백질 관련 최신 연구 좀 찾아줄 수 있을까요?"
        → "KaiC protein latest research papers"
    
    Args:
        question: 원본 질문
        
    Returns:
        단순화된 검색 쿼리
    """
    prompt = f"""다음 질문을 검색 엔진에 최적화된 짧고 명확한 검색 쿼리로 변환하세요.

원본 질문: {question}

규칙:
1. 핵심 키워드만 남기고 불필요한 조사/어미 제거
2. 영어 전문 용어 우선 사용
3. 5-10단어 이내로 간결하게
4. 검색 의도를 명확히 표현

검색 쿼리만 출력하세요:"""

    try:
        simplified = gpt4o_mini(prompt).strip()
        print(f"[query_simplifier_tool] '{question[:30]}...' → '{simplified}'")
        return simplified
        
    except Exception as e:
        print(f"[query_simplifier_tool] 오류: {e}, 원본 반환")
        return question


# ============================================
# 🔹 Query Rewrite Agent Node
# ============================================
def query_rewrite_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Query Rewrite Agent 노드
    LLM이 3가지 tool을 판단하여 사용하는 에이전트
    
    Input:
        - state["question"]: 사용자 질문
        - state["memory_slot"]: 메모리 슬롯 (선택적)
    
    Output:
        - state["rewritten_query"]: 재작성된 검색 쿼리
        - state["extracted_keywords"]: 추출된 키워드들
        - state["extracted_entities"]: 추출된 엔티티들
    
    Tool 사용:
        - keyword_extractor_tool: 필수 호출
        - change_date_tool: LLM이 필요시 호출
        - query_simplifier_tool: LLM이 필요시 호출
    """
    
    # 노드 진입 로그
    print(f"\n{'='*60}")
    print(f"[QUERY_REWRITE_AGENT NODE] 시작")
    print(f"  question: {str(state.get('question', ''))[:30]}...")
    print(f"{'='*60}\n")
    
    question = state.get("question", "")
    memory_slot = state.get("memory_slot", {})
    
    # 질문이 없으면 빈 결과 반환
    if not question:
        state["rewritten_query"] = ""
        state["extracted_keywords"] = []
        state["extracted_entities"] = []
        return state
    
    # 1. 키워드/엔티티 추출 (필수 호출)
    print("[Agent] Step 1: 키워드/엔티티 추출 (필수)")
    extracted = keyword_extractor_tool(question)
    keywords = extracted["keywords"]
    entities = extracted["entities"]
    
    # state에 키워드/엔티티 저장
    state["extracted_keywords"] = keywords
    state["extracted_entities"] = entities
    
    # 2. LLM에게 tool 사용 여부 판단 요청
    previous_topic = memory_slot.get("topic", "") if memory_slot else ""
    
    # Tool 사용 판단 프롬프트
    tool_decision_prompt = f"""질문을 분석하여 어떤 tool을 사용할지 결정하세요.

질문: {question}
추출된 키워드: {keywords}
추출된 엔티티: {entities}"""

    if previous_topic:
        tool_decision_prompt += f"\n이전 주제: {previous_topic}"

    tool_decision_prompt += """

사용 가능한 tool:
1. change_date_tool: 상대적 시간 표현("올해", "작년", "최근 3년" 등)이 있으면 사용
2. query_simplifier_tool: 질문이 길거나 복잡하면 사용

질문을 분석하여 필요한 tool을 JSON 형식으로 출력하세요:
{
  "use_change_date": true/false,
  "use_simplifier": true/false,
  "reason": "간단한 이유"
}

JSON만 출력하세요:"""

    try:
        # LLM이 tool 사용 결정
        decision_response = gpt4o_mini(tool_decision_prompt).strip()
        decision = json.loads(decision_response)
        
        print(f"[Agent] Tool 사용 결정: {decision}")
        
        # 3. 날짜 정규화 (필요시)
        processed_query = question
        if decision.get("use_change_date", False):
            print("[Agent] Step 2: 날짜 정규화 실행")
            processed_query = change_date_tool(processed_query)
        
        # 4. 질문 단순화 (필요시)
        if decision.get("use_simplifier", False):
            print("[Agent] Step 3: 질문 단순화 실행")
            processed_query = query_simplifier_tool(processed_query)
        
        # 최종 재작성 쿼리
        state["rewritten_query"] = processed_query
        
        print(f"[Agent] 최종 쿼리: '{processed_query[:50]}...'")
        
    except Exception as e:
        print(f"[Agent] 오류 발생: {e}")
        # 오류 시 간단한 폴백: 질문 + 키워드 조합
        rewritten_parts = [question]
        if keywords:
            rewritten_parts.extend(keywords[:3])
        if entities:
            rewritten_parts.extend(entities[:3])
        
        state["rewritten_query"] = " ".join(rewritten_parts)
    
    # 노드 종료 로그
    print(f"\n[QUERY_REWRITE_AGENT NODE] 종료")
    print(f"  rewritten_query: {str(state.get('rewritten_query', ''))[:30]}...")
    print(f"  keywords: {state.get('extracted_keywords', [])}")
    print(f"  entities: {state.get('extracted_entities', [])}")
    print(f"{'='*60}\n")
    
    return state

