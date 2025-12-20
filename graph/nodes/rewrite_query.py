"""
query_rewrite_agent.py (구 rewrite_query.py)
--------------------
LLM이 2가지 tool을 판단하여 사용하는 에이전트 노드
- change_date_tool: 날짜 정규화
- query_simplifier_tool: 질문 단순화

참고: 키워드/엔티티 추출은 retriever 노드에서 RAG 결과를 통해 수행됨
"""

from typing import Dict, Any, List
import json
import re
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from graph.llm_config import (
    rewrite_query_expander_tool_llm,
    rewrite_query_simplifier_tool_llm,
    rewrite_query_node_llm
)


# ============================================
# 🔹 Tool 1: 날짜 정규화 (정규식 + dateutil 기반)
# ============================================
def change_date_tool(query: str) -> str:
    """
    상대적 시간 표현을 절대 날짜로 변환 (정규식 + dateutil 사용)
    
    예시:
        "올해 논문" → "2025년 논문"
        "최근 3년" → "2022-2025"
        "작년 6월" → "2024년 6월"
        "3일 전" → "2025년 12월 10일"
        "어제" → "2025년 12월 12일"
    
    Args:
        query: 원본 질문
        
    Returns:
        날짜가 정규화된 질문
    """
    try:
        now = datetime.now()
        normalized = query
        
        # 정규식 패턴과 변환 함수 정의
        patterns = [
            # 최근 N년 (범위 형태로 변환)
            (r'최근\s*(\d+)\s*년', 
             lambda m: f"{now.year - int(m.group(1)) + 1}-{now.year}년"),
            
            # 최근 N개월
            (r'최근\s*(\d+)\s*개월', 
             lambda m: (now - relativedelta(months=int(m.group(1)))).strftime('%Y년 %m월') + f"-{now.strftime('%Y년 %m월')}"),
            
            # N년 전
            (r'(\d+)\s*년\s*전', 
             lambda m: f"{now.year - int(m.group(1))}년"),
            
            # N개월 전
            (r'(\d+)\s*개월\s*전', 
             lambda m: (now - relativedelta(months=int(m.group(1)))).strftime('%Y년 %m월')),
            
            # N주 전
            (r'(\d+)\s*주\s*전', 
             lambda m: (now - timedelta(weeks=int(m.group(1)))).strftime('%Y년 %m월 %d일')),
            
            # N일 전
            (r'(\d+)\s*일\s*전', 
             lambda m: (now - timedelta(days=int(m.group(1)))).strftime('%Y년 %m월 %d일')),
            
            # 작년 N월
            (r'작년\s*(\d+)\s*월', 
             lambda m: f"{now.year - 1}년 {m.group(1)}월"),
            
            # 올해 N월
            (r'올해\s*(\d+)\s*월', 
             lambda m: f"{now.year}년 {m.group(1)}월"),
            
            # 재작년
            (r'재작년', lambda m: f"{now.year - 2}년"),
            
            # 작년
            (r'작년', lambda m: f"{now.year - 1}년"),
            
            # 올해
            (r'올해', lambda m: f"{now.year}년"),
            
            # 내년
            (r'내년', lambda m: f"{now.year + 1}년"),
            
            # 지난달
            (r'지난달', 
             lambda m: (now - relativedelta(months=1)).strftime('%Y년 %m월')),
            
            # 이번 달
            (r'이번\s*달', lambda m: now.strftime('%Y년 %m월')),
            
            # 다음 달
            (r'다음\s*달', 
             lambda m: (now + relativedelta(months=1)).strftime('%Y년 %m월')),
            
            # 그저께
            (r'그저께', 
             lambda m: (now - timedelta(days=2)).strftime('%Y년 %m월 %d일')),
            
            # 어제
            (r'어제', 
             lambda m: (now - timedelta(days=1)).strftime('%Y년 %m월 %d일')),
            
            # 오늘
            (r'오늘', lambda m: now.strftime('%Y년 %m월 %d일')),
            
            # 내일
            (r'내일', 
             lambda m: (now + timedelta(days=1)).strftime('%Y년 %m월 %d일')),
            
            # 모레
            (r'모레', 
             lambda m: (now + timedelta(days=2)).strftime('%Y년 %m월 %d일')),
            
            # 지난주
            (r'지난주', 
             lambda m: (now - timedelta(weeks=1)).strftime('%Y년 %m월 %d일')),
            
            # 이번 주
            (r'이번\s*주', lambda m: now.strftime('%Y년 %m월 %d일')),
            
            # 다음 주
            (r'다음\s*주', 
             lambda m: (now + timedelta(weeks=1)).strftime('%Y년 %m월 %d일')),
        ]
        
        # 패턴 순차 적용 (긴 패턴부터 먼저 적용)
        for pattern, replacement_fn in patterns:
            match = re.search(pattern, normalized)
            if match:
                replacement = replacement_fn(match)
                normalized = re.sub(pattern, replacement, normalized, count=1)
        
        # 변환이 발생했는지 확인
        if normalized != query:
            print(f"[change_date_tool] '{query}' → '{normalized}'")
        else:
            print(f"[change_date_tool] 날짜 표현 없음, 원본 유지")
        
        return normalized
        
    except Exception as e:
        print(f"[change_date_tool] 오류: {e}, 원본 반환")
        return query


# ============================================
# 🔹 Tool 2: 키워드/엔티티 추출 (삭제됨 - retriever에서 수행)
# ============================================
# 키워드/엔티티 추출은 retriever 노드에서 RAG 결과를 통해 수행됨
# 이 함수는 더 이상 사용되지 않음

# ============================================
# 🔹 Tool 2-1: 이전 대화 키워드/엔티티 선택 (LLM 판단) - 삭제됨
# ============================================
# 이전 대화 키워드/엔티티 선택도 retriever에서 처리됨
def context_keyword_selector_tool(
    current_question: str,
    current_keywords: List[str],
    current_entities: List[str],
    previous_history: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    LLM이 이전 대화 키워드/엔티티 중 현재 질문에 필요한 것만 선택
    
    Args:
        current_question: 현재 사용자 질문
        current_keywords: 현재 질문에서 추출된 키워드
        current_entities: 현재 질문에서 추출된 엔티티
        previous_history: 이전 대화 히스토리 (최근 2개 권장)
        
    Returns:
        {
            "selected_keywords": [...],  # 선택된 이전 키워드
            "selected_entities": [...],  # 선택된 이전 엔티티
            "reason": "선택 이유"
        }
    """
    if not previous_history:
        return {
            "selected_keywords": [],
            "selected_entities": [],
            "reason": "이전 대화 히스토리 없음"
        }
    
    # 이전 대화 히스토리 포맷팅
    history_text = ""
    for i, hist in enumerate(previous_history[:2], 1):  # 최근 2개만
        hist_question = hist.get("question", "")
        hist_keywords = hist.get("keywords", [])
        history_text += f"\n{i}. 질문: {hist_question}\n   키워드: {hist_keywords}"
    
    prompt = f"""현재 질문과 이전 대화 히스토리를 분석하여, 이전 대화의 키워드/엔티티 중 현재 질문에 필요한 것만 선택하세요.

현재 질문: {current_question}
현재 질문에서 추출된 키워드: {current_keywords}
현재 질문에서 추출된 엔티티: {current_entities}

이전 대화 히스토리:{history_text}

분석 기준:
1. 현재 질문이 이전 대화를 참조하는가? ("그거", "저거", "그것", "그 단백질" 등 지시대명사 사용)
2. 이전 대화의 키워드/엔티티 중 현재 질문과 관련성이 높은 것은?
3. 주제가 바뀌었는가? (주제가 바뀌면 이전 키워드 사용 안함)
4. 엔티티는 우선순위가 높음 (지시대명사가 가리키는 대상)

규칙:
- 관련성 높은 키워드/엔티티만 선택 (최대 5개)
- 현재 질문 키워드와 중복되지 않는 것만 선택
- 주제가 완전히 바뀌었으면 빈 리스트 반환

출력 형식 (반드시 JSON):
{{
  "selected_keywords": ["protein"],  # 선택된 이전 키워드 (없으면 빈 리스트)
  "selected_entities": ["KaiC"],      # 선택된 이전 엔티티 (없으면 빈 리스트)
  "reason": "현재 질문 '그거 구조는?'이 이전 대화의 'KaiC'를 참조하므로 필수"
}}

JSON만 출력하세요:"""

    try:
        response = rewrite_query_expander_tool_llm(prompt).strip()
        result = json.loads(response)
        
        selected_keywords = result.get("selected_keywords", [])
        selected_entities = result.get("selected_entities", [])
        reason = result.get("reason", "이유 없음")
        
        print(f"[context_keyword_selector_tool] 선택된 키워드: {selected_keywords}")
        print(f"[context_keyword_selector_tool] 선택된 엔티티: {selected_entities}")
        print(f"[context_keyword_selector_tool] 선택 이유: {reason}")
        
        return {
            "selected_keywords": selected_keywords,
            "selected_entities": selected_entities,
            "reason": reason
        }
        
    except Exception as e:
        print(f"[context_keyword_selector_tool] 오류: {e}, 빈 결과 반환")
        return {
            "selected_keywords": [],
            "selected_entities": [],
            "reason": f"오류 발생: {e}"
        }




# ============================================
# 🔹 Tool 2: 질문 단순화
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
        simplified = rewrite_query_simplifier_tool_llm(prompt).strip()
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
    LLM이 2가지 tool을 판단하여 사용하는 에이전트
    
    Input:
        - state["question"]: 사용자 질문
        - state["memory_slot"]: 메모리 슬롯 (선택적)
    
    Output:
        - state["rewritten_query"]: 재작성된 검색 쿼리
    
    Tool 사용:
        - change_date_tool: LLM이 필요시 호출
        - query_simplifier_tool: LLM이 필요시 호출
    
    참고: 키워드/엔티티 추출은 retriever 노드에서 RAG 결과를 통해 수행됨
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
        return state
    
    # LLM에게 tool 사용 여부 판단 요청
    previous_topic = memory_slot.get("topic", "") if memory_slot else ""
    
    # Tool 사용 판단 프롬프트
    tool_decision_prompt = f"""질문을 분석하여 어떤 tool을 사용할지 결정하세요.

질문: {question}"""

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
        decision_response = rewrite_query_node_llm(tool_decision_prompt).strip()
        decision = json.loads(decision_response)
        
        print(f"[Agent] Tool 사용 결정: {decision}")
        
        # 날짜 정규화 (필요시)
        processed_query = question
        if decision.get("use_change_date", False):
            print("[Agent] Step 1: 날짜 정규화 실행")
            processed_query = change_date_tool(processed_query)
        
        # 질문 단순화 (필요시)
        if decision.get("use_simplifier", False):
            print("[Agent] Step 2: 질문 단순화 실행")
            processed_query = query_simplifier_tool(processed_query)
        
        # 최종 재작성 쿼리
        state["rewritten_query"] = processed_query
        
        print(f"[Agent] 최종 쿼리: '{processed_query[:50]}...'")
        
    except Exception as e:
        print(f"[Agent] 오류 발생: {e}")
        # 오류 시 원본 질문 사용
        state["rewritten_query"] = question
    
    # 노드 종료 로그
    print(f"\n[QUERY_REWRITE_AGENT NODE] 종료")
    print(f"  rewritten_query: {str(state.get('rewritten_query', ''))[:30]}...")
    print(f"{'='*60}\n")
    
    return state

