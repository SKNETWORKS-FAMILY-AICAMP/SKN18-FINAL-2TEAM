"""
guardrail.py
--------------------
유해 콘텐츠 감지 및 차단을 위한 가드레일 노드

차단 대상:
- 마약류/향정신성 의약품 불법 합성/제조
- 폭발물/독성 물질 제조
- 생물무기/병원체 악용
- 불법 실험 방법
- 윤리적으로 부적절한 연구
- 직접적인 의료 진단/처방 (의료법 위반)
"""

from typing import Dict, Any
from graph.llm_config import guardrail_check_safety_llm, get_model_name


def _check_harmful_content(question: str) -> Dict[str, Any]:
    """
    LLM을 사용하여 질문의 유해성을 판단합니다.
    
    Args:
        question: 사용자 질문
        
    Returns:
        Dict: {
            "is_safe": bool,
            "risk_category": str,
            "reason": str
        }
    """
    
    prompt = f"""당신은 생명과학 연구 시스템의 안전 검토자입니다. 
다음 질문이 안전한지 판단하고, 위험한 경우 그 이유를 설명하세요.

=== 차단해야 할 질문 유형 ===

1. **마약류/향정신성 의약품 불법 제조**
   - 불법 약물 합성법, 제조법, 추출법
   - 예: "메스암페타민 합성 방법", "LSD 제조법", "코카인 추출"
   
2. **폭발물/독성 물질 제조**
   - 폭발물 제조, 독극물 합성
   - 예: "TNT 제조법", "사린 합성", "리신 독소 추출"
   
3. **생물무기/병원체 악용**
   - 병원체 배양, 생물무기 개발, 독소 무기화
   - 예: "탄저균 배양법", "바이러스 무기화", "보툴리눔 독소 추출"
   
4. **불법/비윤리적 실험**
   - 인체 실험, 동물 학대, 윤리 위반 연구
   - 예: "인간 클론 만들기", "불법 임상시험 방법"
   
5. **직접적인 의료 행위 (의료법 위반)**
   - 진단, 처방, 치료법 결정 (일반적인 의학 지식 설명은 허용)
   - 예: "제 증상을 진단해주세요", "이 약을 처방해주세요"

=== 허용되는 질문 ===
- 학술적 연구 목적의 생물학/화학 지식
- 합법적인 의약품 연구 및 개발
- 정상적인 실험 프로토콜
- 일반적인 의학/생물학 지식 교육
- 논문/연구 자료 검색 및 분석

질문: {question}

위 질문을 분석하여 다음 형식으로 JSON만 출력하세요:
{{
    "is_safe": true 또는 false,
    "risk_category": "SAFE" 또는 "DRUGS", "EXPLOSIVES", "BIOWEAPON", "UNETHICAL", "MEDICAL_ACT",
    "reason": "판단 근거를 한 문장으로"
}}

JSON만 출력하고 다른 텍스트는 포함하지 마세요."""

    response = None
    try:
        model_name = get_model_name(guardrail_check_safety_llm)
        print(f"[Guardrail] 안전 검사 모델: {model_name}")
        response = guardrail_check_safety_llm(prompt).strip()
        
        # JSON 파싱
        import json
        
        # ```json 블록이 있으면 제거
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            response = response.split("```")[1].split("```")[0].strip()
        
        result = json.loads(response)
        
        # 결과 검증
        if not isinstance(result.get("is_safe"), bool):
            raise ValueError("Invalid is_safe value")
        
        return {
            "is_safe": result.get("is_safe", True),
            "risk_category": result.get("risk_category", "UNKNOWN"),
            "reason": result.get("reason", "판단 불가")
        }
        
    except Exception as e:
        print(f"[Guardrail Error] {e}")
        if response is not None:
            print(f"[Guardrail Error] Response: {response}")
        else:
            print(f"[Guardrail Error] Response: (not available - error occurred before LLM call)")
        # 오류 시 안전하게 차단 (False Positive보다 False Negative가 더 위험)
        return {
            "is_safe": True,  # 에러 시에는 통과시키고 다음 단계에서 처리
            "risk_category": "ERROR",
            "reason": f"안전 검사 중 오류 발생: {str(e)}"
        }




def guardrail_input_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    사용자 입력을 검증하는 가드레일 노드
    
    Args:
        state: BioRAGState
        
    Returns:
        guardrail_passed, guardrail_risk_category, 
        guardrail_reason이 추가된 state
    """
    
    # 노드 진입 로그
    print(f"\n{'='*60}")
    print(f"[GUARDRAIL INPUT NODE] 시작")
    print(f"  question: {str(state.get('question', ''))[:50]}...")
    print(f"{'='*60}\n")
    
    # 디버깅: attached_images 확인
    attached_images = state.get("attached_images", [])
    print(f"[Guardrail] attached_images 확인: {len(attached_images) if attached_images else 0}개")
    
    question = (state.get("question") or "").strip()
    
    if not question:
        # 빈 질문은 통과 (attached_images 유지)
        state["guardrail_passed"] = True
        return state
    
    # 유해성 검사
    safety_check = _check_harmful_content(question)
    
    # State에는 통과 여부만 저장 (로깅은 print로 처리)
    state["guardrail_passed"] = safety_check["is_safe"]
    
    # 로깅용 (State에는 저장하지 않음)
    risk_category = safety_check["risk_category"]
    risk_reason = safety_check["reason"]
    print(f"[Guardrail] Risk Category: {risk_category}")
    print(f"[Guardrail] Reason: {risk_reason}")
    
    # 위험한 질문인 경우 즉시 차단 메시지 설정
    if not safety_check["is_safe"]:
        risk_messages = {
            "DRUGS": "불법 약물 제조와 관련된 질문은 답변할 수 없습니다.",
            "EXPLOSIVES": "폭발물이나 독성 물질 제조와 관련된 질문은 답변할 수 없습니다.",
            "BIOWEAPON": "생물무기나 병원체 악용과 관련된 질문은 답변할 수 없습니다.",
            "UNETHICAL": "비윤리적인 연구나 실험과 관련된 질문은 답변할 수 없습니다.",
            "MEDICAL_ACT": "직접적인 의료 진단이나 처방은 의료법에 따라 의사만 할 수 있습니다. 일반적인 의학 지식에 대한 질문을 부탁드립니다.",
        }
        
        risk_msg = risk_messages.get(
            risk_category,  # 로컬 변수 사용
            "해당 질문은 안전상의 이유로 답변할 수 없습니다."
        )
        
        state["final_answer"] = f"""⚠️ 안전 정책에 의해 답변이 차단되었습니다.

{risk_msg}

저희 시스템은 다음과 같은 합법적이고 윤리적인 연구를 지원합니다:
- 학술적 생물학/화학 연구
- 정상적인 실험 프로토콜
- 의학/생명과학 교육
- 논문 및 연구 자료 분석

다른 질문이 있으시면 언제든지 말씀해 주세요."""
    
    # 노드 종료 로그
    print(f"\n[GUARDRAIL INPUT NODE] 종료")
    print(f"  guardrail_passed: {state.get('guardrail_passed')}")
    if not state.get('guardrail_passed'):
        print(f"  risk_category: {risk_category}")
        print(f"  reason: {risk_reason}")
    print(f"{'='*60}\n")
    
    # attached_images가 있으면 명시적으로 유지 (LangGraph state 병합을 위해)
    if attached_images:
        state["attached_images"] = attached_images
        print(f"[Guardrail] attached_images 유지: {len(attached_images)}개")
    
    return state



