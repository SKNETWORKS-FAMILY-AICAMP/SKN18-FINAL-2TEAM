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
# 🔹 Tool 2-1: 이전 대화 키워드/엔티티 선택 (LLM 판단)
# ============================================
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
        response = rewrite_query_expander_tool_llm(prompt).strip()
        
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
def query_simplifier_tool(question: str, keywords: List[str] = None, entities: List[str] = None) -> str:
    """
    질문을 검색 엔진이 좋아하는 짧고 명확한 검색 쿼리로 변환
    키워드/엔티티 정보를 활용하여 더 정확한 검색 쿼리 생성
    
    예시:
        "혹시 KaiC 단백질 관련 최신 연구 좀 찾아줄 수 있을까요?"
        keywords=["KaiC", "protein", "research"], entities=["KaiC"]
        → "KaiC protein latest research papers"
    
    Args:
        question: 원본 질문
        keywords: 추출된 키워드 리스트 (선택적)
        entities: 추출된 엔티티 리스트 (선택적)
        
    Returns:
        단순화된 검색 쿼리
    """
    keywords = keywords or []
    entities = entities or []
    
    prompt = f"""다음 질문을 검색 엔진에 최적화된 짧고 명확한 검색 쿼리로 변환하세요.

원본 질문: {question}"""

    # 키워드/엔티티 정보가 있으면 프롬프트에 포함
    if keywords or entities:
        prompt += "\n\n추출된 정보:"
        if entities:
            prompt += f"\n- 엔티티 (반드시 포함): {', '.join(entities)}"
        if keywords:
            prompt += f"\n- 키워드 (우선 포함): {', '.join(keywords)}"
    
    prompt += """

규칙:
1. 핵심 키워드만 남기고 불필요한 조사/어미 제거
2. 영어 전문 용어 우선 사용
3. 5-10단어 이내로 간결하게
4. 검색 의도를 명확히 표현
5. 엔티티는 반드시 포함하고, 키워드는 가능한 한 포함하세요

검색 쿼리만 출력하세요:"""

    try:
        simplified = rewrite_query_simplifier_tool_llm(prompt).strip()
        print(f"[query_simplifier_tool] '{question[:30]}...' → '{simplified}'")
        if keywords or entities:
            print(f"[query_simplifier_tool] 활용된 키워드: {keywords}, 엔티티: {entities}")
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
    
    # 2. 꼬리질문일 때 이전 대화 키워드/엔티티 LLM 판단으로 선택
    is_follow_up = state.get("is_follow_up", False)
    relevant_history = state.get("relevant_history", [])
    
    if is_follow_up and relevant_history:
        print("[Agent] 꼬리질문 감지: 이전 대화 키워드/엔티티 LLM 판단 시작")
        
        # LLM이 이전 대화 키워드/엔티티 중 필요한 것만 선택
        selection_result = context_keyword_selector_tool(
            current_question=question,
            current_keywords=keywords,
            current_entities=entities,
            previous_history=relevant_history
        )
        
        selected_keywords = selection_result["selected_keywords"]
        selected_entities = selection_result["selected_entities"]
        selection_reason = selection_result["reason"]
        
        # 선택된 키워드/엔티티를 현재 것과 병합 (중복 제거)
        if selected_keywords:
            # 현재 키워드에 없는 것만 추가
            new_keywords = [k for k in selected_keywords if k not in keywords]
            keywords = keywords + new_keywords
            print(f"[Agent] 이전 대화 키워드 병합: {new_keywords} (선택 이유: {selection_reason})")
        
        if selected_entities:
            # 현재 엔티티에 없는 것만 추가
            new_entities = [e for e in selected_entities if e not in entities]
            entities = entities + new_entities
            print(f"[Agent] 이전 대화 엔티티 병합: {new_entities} (선택 이유: {selection_reason})")
        
        if not selected_keywords and not selected_entities:
            print(f"[Agent] 이전 대화 키워드/엔티티 미선택 (이유: {selection_reason})")
    
    # state에 키워드/엔티티 저장
    state["extracted_keywords"] = keywords
    state["extracted_entities"] = entities
    
    # 3. LLM에게 tool 사용 여부 판단 요청
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
        decision_response = rewrite_query_node_llm(tool_decision_prompt).strip()
        decision = json.loads(decision_response)
        
        print(f"[Agent] Tool 사용 결정: {decision}")
        
        # 3. 날짜 정규화 (필요시)
        processed_query = question
        if decision.get("use_change_date", False):
            print("[Agent] Step 2: 날짜 정규화 실행")
            processed_query = change_date_tool(processed_query)
        
        # 4. 질문 단순화 (필요시) - 키워드/엔티티 전달
        if decision.get("use_simplifier", False):
            print("[Agent] Step 3: 질문 단순화 실행 (키워드/엔티티 활용)")
            processed_query = query_simplifier_tool(processed_query, keywords=keywords, entities=entities)
        
        # 5. rewritten_query 생성 시 키워드/엔티티 명시적 활용
        # query_simplifier_tool을 사용하지 않았거나, 핵심 엔티티가 누락된 경우 보강
        if not decision.get("use_simplifier", False) or (entities and not any(e.lower() in processed_query.lower() for e in entities)):
            print("[Agent] Step 4: 키워드/엔티티 보강 적용")
            # 엔티티가 쿼리에 없으면 추가
            query_parts = [processed_query]
            
            # 엔티티가 쿼리에 없으면 추가 (최대 3개)
            missing_entities = [e for e in entities[:3] if e.lower() not in processed_query.lower()]
            if missing_entities:
                query_parts.extend(missing_entities)
                print(f"[Agent] 누락된 엔티티 추가: {missing_entities}")
            
            # 핵심 키워드도 일부 추가 (엔티티와 중복되지 않는 것만, 최대 2개)
            if keywords:
                missing_keywords = [
                    k for k in keywords[:5] 
                    if k.lower() not in processed_query.lower() 
                    and not any(k.lower() in e.lower() or e.lower() in k.lower() for e in entities)
                ][:2]
                if missing_keywords:
                    query_parts.extend(missing_keywords)
                    print(f"[Agent] 핵심 키워드 추가: {missing_keywords}")
            
            processed_query = " ".join(query_parts)
        
        # 최종 재작성 쿼리
        state["rewritten_query"] = processed_query
        
        print(f"[Agent] 최종 쿼리: '{processed_query[:50]}...'")
        print(f"[Agent] 활용된 키워드: {keywords}, 엔티티: {entities}")
        
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

