"""
evaluate_web.py
--------------------
웹 검색 결과의 관련성을 평가하는 노드
BioRAGState 구조에 맞게 구현

변경 사항:
- JSON 형식으로 LLM 출력 요청 (파싱 안정성 향상)
- LLM 출력 원본 및 파싱 결과 상세 로깅
- 하위 호환성 유지 (최종 출력은 기존 문자열 형식)
"""

from typing import Dict, Any, Optional, List
import json
import re
from graph.llm_config import evaluate_web_node_llm, get_model_name


def _safe_json_loads(raw: str) -> Optional[Dict[str, Any]]:
    """
    evaluate_chunk.py의 _safe_json_loads와 동일한 안전한 JSON 파서
    LLM 출력에서 JSON 블록을 추출하여 파싱
    """
    if not raw:
        return None
    s = raw.strip()

    # 1) 바로 파싱
    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    # 2) 문자열 내부에서 첫 { ... } 블록만 추출
    m = re.search(r"\{.*\}", s, flags=re.DOTALL)
    if not m:
        return None

    try:
        obj = json.loads(m.group(0))
        if isinstance(obj, dict):
            return obj
    except Exception:
        return None

    return None


def evaluate_web_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    웹 검색 결과 평가 노드
    웹 검색 결과에서 질문과 관련된 내용만 선별하여 정제
    
    Input:
        - state["question"]: 사용자 질문
        - state["web_results"]: 웹 검색 결과
    
    Output:
        - state["web_selected_chunks"]: 선별된 웹 검색 청크들
    """
    
    # 노드 진입 로그
    print(f"\n{'='*60}")
    print(f"[EVALUATE_WEB NODE] 시작")
    print(f"  question: {str(state.get('question', ''))[:30]}...")
    print(f"  web_results: {len(state.get('web_results', []))}개")
    print(f"{'='*60}\n")
    
    question = state.get("question", "")
    web_results = state.get("web_results", [])
    
    # operator.add로 인한 중복 누적 방지: 기존 값 초기화
    existing_chunks = state.get("web_selected_chunks", [])
    if existing_chunks:
        print(f"[EvaluateWeb] ⚠️ 기존 web_selected_chunks 발견 ({len(existing_chunks)}개) - 초기화합니다")
        print(f"[EvaluateWeb] 기존 내용 샘플: {existing_chunks[0][:50] if existing_chunks else 'None'}...")
        state["web_selected_chunks"] = []  # 초기화
    
    print(f"[EvaluateWeb] 시작 - {len(web_results)}개 웹 검색 결과 평가")
    
    # 웹 검색 결과가 없는 경우
    if not web_results:
        state["web_selected_chunks"] = []

        # BIO_Q인 경우 조기 종료 메시지 설정
        case_type = state.get("case_type", "")
        if case_type == "BIO_Q":
            state["final_answer"] = "죄송합니다. 요청하신 정보를 찾을 수 없습니다. 다른 질문을 해주시거나, 더 구체적인 정보를 제공해주시면 도움을 드리겠습니다."
            state["should_skip_generation"] = True
            print("[EvaluateWeb] BIO_Q - 웹 검색 결과 없음, 조기 종료")
        else:
            print("[EvaluateWeb] 완료 - 웹 검색 결과 없음")

        return state
    
    # 웹 검색 결과를 컨텍스트로 변환
    context_parts = []
    for i, result in enumerate(web_results, 1):
        title = result.get("title", "")
        snippet = result.get("snippet", "")
        url = result.get("url", "")
        
        # 각 웹 검색 결과의 앞 50글자 로그 출력
        snippet_preview = snippet[:50] if snippet else ""
        print(f"  [웹자료 {i}] {title[:40]}")
        print(f"      내용: {snippet_preview}...")
        
        content = f"제목: {title}\n내용: {snippet}"
        if url:
            content += f"\n출처: {url}"
        
        context_parts.append(f"[웹자료 {i}]\n{content}")
    
    context = "\n\n".join(context_parts)
    
    # LLM을 사용하여 관련성 평가 및 정제 (JSON 형식으로 요청)
    prompt = f"""다음 웹 검색 결과에서 사용자 질문과 **직접적으로 관련된** 핵심 정보만 선별하세요.

사용자 질문: {question}

웹 검색 결과:
---
{context}
---

**중요 지침:**
1. 질문과 직접적으로 관련된 웹 자료만 선택하세요 (관련성이 높은 것만)
2. 최대 3개의 웹 자료만 선택하세요
3. 각 자료는 한 줄로 핵심만 요약하세요 (최대 100자)
4. 관련성이 낮거나 부정확한 정보는 제외하세요

**출력 형식 (JSON만 출력):**
관련 자료가 있으면:
{{
  "selected": [
    {{
      "index": 1,
      "summary": "핵심 내용 한 줄 요약"
    }},
    {{
      "index": 2,
      "summary": "핵심 내용 한 줄 요약"
    }}
  ]
}}

관련 자료가 없으면:
{{
  "selected": []
}}

⚠️ 중요: 반드시 유효한 JSON 형식으로만 출력하세요. 설명이나 추가 텍스트는 포함하지 마세요.
"""

    try:
        # 사용 모델 확인
        model_name = get_model_name(evaluate_web_node_llm)
        print(f"[EvaluateWeb] 사용 모델: {model_name}")
        
        # LLM을 사용하여 웹 검색 결과 정제
        result = evaluate_web_node_llm(prompt)
        
        # LLM 출력 원본 로깅 (디버깅용)
        print(f"[EvaluateWeb] LLM 원본 출력:")
        print(f"{'='*60}")
        print(result)
        print(f"{'='*60}")
        print(f"[EvaluateWeb] LLM 출력 길이: {len(result)}자")
        
        # JSON 파싱 시도
        web_selected_chunks: List[str] = []
        json_parse_success = False
        
        try:
            obj = _safe_json_loads(result)
            
            if obj and isinstance(obj, dict):
                selected = obj.get("selected", [])
                
                if isinstance(selected, list) and len(selected) > 0:
                    # JSON 파싱 성공 - 기존 문자열 형식으로 변환 (하위 호환성 유지)
                    for item in selected:
                        if isinstance(item, dict):
                            idx = item.get("index", 1)
                            summary = item.get("summary", "")
                            if summary:
                                web_selected_chunks.append(f"웹자료 {idx}: {summary}")
                    
                    json_parse_success = True
                    print(f"[EvaluateWeb] ✅ JSON 파싱 성공 - {len(web_selected_chunks)}개 항목 추출")
                    print(f"[EvaluateWeb] 파싱된 항목:")
                    for i, chunk in enumerate(web_selected_chunks, 1):
                        print(f"  [{i}] {chunk[:80]}...")
                else:
                    print(f"[EvaluateWeb] ⚠️ JSON 파싱 성공했지만 selected 배열이 비어있음")
            else:
                print(f"[EvaluateWeb] ⚠️ JSON 파싱 실패 - 유효한 JSON 객체가 아님")
        
        except Exception as json_error:
            print(f"[EvaluateWeb] ⚠️ JSON 파싱 중 오류: {json_error}")
        
        # JSON 파싱 실패 시 기존 텍스트 기반 파싱 시도 (fallback)
        if not json_parse_success or not web_selected_chunks:
            print(f"[EvaluateWeb] 텍스트 기반 파싱 시도 (fallback)...")
            fallback_chunks = []
            
            # "웹자료 N:" 형식 찾기
            lines = result.strip().split('\n')
            for line in lines:
                line = line.strip()
                if line and ('웹자료' in line or '웹 자료' in line) and ':' in line:
                    # 정규식으로 인덱스와 내용 추출
                    match = re.search(r'(?:웹\s*자료|웹자료)\s*(\d+)(?:번|\)|\.|:)?\s*[:\-\.]\s*(.+)', line)
                    if match:
                        idx = int(match.group(1))
                        summary = match.group(2).strip()
                        fallback_chunks.append(f"웹자료 {idx}: {summary}")
                    elif line.startswith('웹자료') or line.startswith('웹 자료'):
                        # 간단한 형식: "웹자료 N: 내용"
                        parts = line.split(':', 1)
                        if len(parts) == 2:
                            idx_str = re.search(r'\d+', parts[0])
                            if idx_str:
                                idx = int(idx_str.group())
                                summary = parts[1].strip()
                                fallback_chunks.append(f"웹자료 {idx}: {summary}")
            
            if fallback_chunks:
                web_selected_chunks = fallback_chunks
                print(f"[EvaluateWeb] ✅ 텍스트 기반 파싱 성공 - {len(web_selected_chunks)}개 항목 추출")
                print(f"[EvaluateWeb] 파싱된 항목:")
                for i, chunk in enumerate(web_selected_chunks, 1):
                    print(f"  [{i}] {chunk[:80]}...")
            else:
                print(f"[EvaluateWeb] ❌ 텍스트 기반 파싱도 실패")

        # BIO_Q이고 관련 정보가 없는 경우 조기 종료 (citations 추가하지 않음)
        if not web_selected_chunks:
            case_type = state.get("case_type", "")
            if case_type == "BIO_Q":
                state["final_answer"] = "죄송합니다. 요청하신 정보를 찾을 수 없습니다. 다른 질문을 해주시거나, 더 구체적인 정보를 제공해주시면 도움을 드리겠습니다."
                state["should_skip_generation"] = True
                state["web_selected_chunks"] = []
                print("[EvaluateWeb] ⚠️ BIO_Q - 관련 정보 없음, GENERATE_ANSWER 건너뛰고 END로 이동")
                print(f"[EvaluateWeb] should_skip_generation = {state.get('should_skip_generation')}")
                print(f"[EvaluateWeb] final_answer = {state.get('final_answer')[:50]}...")
                print(f"[EvaluateWeb] citations = {len(state.get('citations', []))}개 (citations 추가 안 함)")
                return state

        # 중복 제거 (operator.add로 인한 누적 방지)
        seen = set()
        unique_chunks = []
        for chunk in web_selected_chunks:
            chunk_str = str(chunk) if not isinstance(chunk, str) else chunk
            if chunk_str and chunk_str not in seen:
                seen.add(chunk_str)
                unique_chunks.append(chunk_str)
        
        original_count = len(web_selected_chunks)
        unique_count = len(unique_chunks)
        
        if original_count != unique_count:
            print(f"[EvaluateWeb] ⚠️ 중복 제거: {original_count}개 → {unique_count}개")
            print(f"[EvaluateWeb] 중복 제거 상세:")
            for i, dup in enumerate(web_selected_chunks, 1):
                is_dup = "중복" if str(dup) not in seen else "유니크"
                print(f"  [{i}] {is_dup}: {str(dup)[:60]}...")
        
        # operator.add로 인한 누적 방지: 빈 리스트로 초기화 후 새 값만 추가
        # LangGraph의 operator.add는 기존 값에 새 값을 추가하므로, 
        # 기존 값을 먼저 제거하기 위해 빈 리스트로 초기화
        state["web_selected_chunks"] = []  # 명시적 초기화
        state["web_selected_chunks"] = unique_chunks  # 새 값 할당
        
        print(f"[EvaluateWeb] ✅ 완료 - {unique_count}개 청크 선별 (원본: {original_count}개, 중복 제거: {original_count - unique_count}개)")
        print(f"[EvaluateWeb] 최종 web_selected_chunks 개수: {len(state.get('web_selected_chunks', []))}개")
        print(f"[EvaluateWeb] 최종 web_selected_chunks 형식: {type(unique_chunks[0]) if unique_chunks else 'None'}")
        
        # 저장 직후 값 확인 (디버깅용)
        final_chunks = state.get("web_selected_chunks", [])
        print(f"[EvaluateWeb] 저장 직후 확인: {len(final_chunks)}개")
        if final_chunks:
            print(f"[EvaluateWeb] 저장된 첫 번째 항목: {final_chunks[0][:60]}...")
        
    except Exception as e:
        print(f"[EvaluateWeb] ❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        
        # 오류 시 원본 웹 검색 결과를 간단히 변환
        web_selected_chunks = []
        for i, result in enumerate(web_results[:2], 1):  # 최대 2개만
            content = result.get("content", "")
            snippet = result.get("snippet", "")
            title = result.get("title", "")
            
            # content가 없으면 snippet이나 title 사용
            if not content:
                content = snippet if snippet else title
            
            if content:
                web_selected_chunks.append(f"웹자료 {i}: {content[:200]}...")
        
        state["web_selected_chunks"] = web_selected_chunks
        print(f"[EvaluateWeb] Fallback: {len(web_selected_chunks)}개 청크 생성")
    
    # 노드 종료 로그
    print(f"\n[EVALUATE_WEB NODE] 종료")
    print(f"  web_selected_chunks: {len(state.get('web_selected_chunks', []))}개")
    print(f"{'='*60}\n")
    
    return state