"""
generate_answer.py
--------------------
각 케이스 타입별로 최종 답변을 생성하는 노드

케이스별 처리:
- NO_RELATION: classifier에서 이미 처리됨 (여기서는 처리하지 않음)
- BIO_Q: RAG/웹 검색 결과를 바탕으로 LLM이 답변 생성
- SIMULATION_Q: 툴 경로 안내를 프롬프트로 전달하여 LLM이 답변 생성  
- PROTOCOL_Q: RAG/웹 검색 결과를 바탕으로 LLM이 답변 생성
- INFERENCE_Q: 사용자 질문을 그대로 프롬프트로 전달하여 LLM이 답변 생성
"""

from typing import Dict, Any
from graph.llm_config import (
    generate_answer_bio_llm,
    generate_answer_info_llm,
    generate_answer_simulation_llm,
    generate_answer_protocol_llm,
    generate_answer_inference_llm,
    get_model_name
)

# Fallback 모델들은 optional로 처리
try:
    from graph.llm_config import generate_answer_protocol_fallback_llm
except ImportError:
    generate_answer_protocol_fallback_llm = None

try:
    from graph.llm_config import generate_answer_inference_fallback_llm
except ImportError:
    generate_answer_inference_fallback_llm = None

import json


def generate_answer_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    케이스 타입에 따라 최종 답변을 생성하는 노드
    
    Args:
        state: BioRAGState 딕셔너리
        
    Returns:
        final_answer가 추가된 state
    """
    case_type = state.get("case_type", "")
    question = state.get("question", "")
    
    # 노드 진입 로그
    print(f"\n{'='*60}")
    print(f"[GENERATE_ANSWER NODE] 시작")
    print(f"  question: {str(question)[:30]}...")
    print(f"  case_type: {case_type}")
    print(f"  selected_chunks: {len(state.get('selected_chunks', []))}개")
    print(f"  web_selected_chunks: {len(state.get('web_selected_chunks', []))}개")
    print(f"{'='*60}\n")
    
    # NO_RELATION은 classifier에서 이미 처리됨
    if case_type == "NO_RELATION":
        return state
    
    # 케이스별 답변 생성
    if case_type == "USER_INFO":
        return _generate_user_info_answer(state)
    elif case_type == "BIO_Q":
        return _generate_bio_answer(state)
    elif case_type == "SIMULATION_Q":
        return _generate_simulation_answer(state)
    elif case_type == "PROTOCOL_Q":
        return _generate_protocol_answer(state)
    elif case_type == "INFERENCE_Q":
        return _generate_inference_answer(state)
    else:
        # 알 수 없는 케이스 타입
        state["final_answer"] = "죄송합니다. 질문을 처리할 수 없습니다."
    
    # 노드 종료 로그
    print(f"\n[GENERATE_ANSWER NODE] 종료")
    print(f"  final_answer: {str(state.get('final_answer', ''))[:30]}...")
    print(f"{'='*60}\n")
    
    return state


def _generate_user_info_answer(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    USER_INFO: 사용자 인적사항 관련 질문
    사용자의 인적사항을 언급하며 친근하게 응답
    """
    question = state.get("question", "")
    
    # 사용 모델 확인
    model_name = get_model_name(generate_answer_info_llm)
    print(f"[USER_INFO] 사용 모델: {model_name}")
    
    # 이전 USER_INFO 대화 컨텍스트 구성
    previous_user_info = ""
    relevant_history = state.get("relevant_history", [])
    
    if relevant_history:
        # USER_INFO 타입의 이전 대화가 있는 경우
        user_info_parts = ["=== 이전에 알려주신 정보 ==="]
        for i, hist in enumerate(relevant_history[:3], 1):  # 최근 3개만
            user_info_parts.append(f"[정보 {i}] {hist['summary']}")
        previous_user_info = "\n".join(user_info_parts) + "\n"
    
    # 프롬프트 구성
    if previous_user_info:
        # 이전 정보가 있는 경우 (질문형 - "내 이름이 뭐라고?", "내 직업이 뭐더라?")
        prompt = f"""사용자가 이전에 알려준 자신의 정보를 묻고 있습니다.

{previous_user_info}
현재 질문: {question}

위 이전 정보를 바탕으로 사용자의 질문에 답변해주세요.
- 이전에 알려준 정보를 자연스럽게 상기시켜주세요
- 친근하고 따뜻한 어조로 답변해주세요
- 만약 이전 정보에 해당 내용이 없다면, "죄송합니다. 그 정보는 아직 알려주지 않으셨어요. 알려주시겠어요?"라고 응답하세요
- 2-3문장으로 간결하게 작성해주세요

답변:"""
    else:
        # 이전 정보가 없는 경우 (처음 알려주는 경우 - "저는 학생입니다")
        prompt = f"""사용자가 자신의 인적사항을 처음 알려주고 있습니다.

질문: {question}

위 정보를 바탕으로 사용자에게 친근하고 환영하는 답변을 작성해주세요.
- 사용자의 신분/직업을 자연스럽게 언급해주세요
- 따뜻하고 친근한 어조로 환영해주세요
- 해당 신분에 맞는 도움을 제공할 수 있다는 점을 안내해주세요
- 2-3문장으로 간결하게 작성해주세요

답변:"""

    # LLM으로 답변 생성 (Pod 비활성화 시 에러 발생)
    answer = generate_answer_info_llm(prompt)
    state["final_answer"] = answer
    state["final_context"] = f"사용자 정보: {question}\n{previous_user_info}"
    
    return state


def _generate_bio_answer(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    BIO_Q: 논문, 임상연구 관련 질문
    RAG 검색 결과와 웹 검색 결과를 바탕으로 답변 생성
    """
    question = state.get("question", "")
    
    # 컨텍스트 구성
    context_parts = []
    sources = []
    
    # 이전 대화 컨텍스트 추가
    relevant_history = state.get("relevant_history", [])
    if relevant_history:
        context_parts.append("=== 이전 대화 참고 ===")
        for i, hist in enumerate(relevant_history[:2], 1):  # 최근 2개만
            context_parts.append(f"[대화 {i}] Q: {hist['question'][:60]}")
            context_parts.append(f"        A: {hist['summary'][:100]}\n")
    
    # RAG 검색 결과 추가
    selected_chunks = state.get("selected_chunks", [])
    if selected_chunks:
        context_parts.append("=== 논문 및 연구 자료 ===")
        for i, chunk in enumerate(selected_chunks, 1):
            context_parts.append(f"[자료 {i}] {chunk}")
    
    # 웹 검색 결과 추가
    web_selected_chunks = state.get("web_selected_chunks", [])
    if web_selected_chunks:
        context_parts.append("\n=== 웹 검색 결과 ===")
        for i, chunk in enumerate(web_selected_chunks, 1):
            context_parts.append(f"[웹자료 {i}] {chunk}")
    
    # 출처 정보 수집
    answer_sources = state.get("answer_sources", [])
    
    final_context = "\n\n".join(context_parts) if context_parts else ""
    
    # 프롬프트 구성
    prompt = f"""다음은 생물학/의학 관련 질문에 대한 답변을 작성하는 작업입니다.

⚠️ 안전 정책 (반드시 준수):
- 불법 약물 합성/제조 방법은 절대 설명하지 마세요
- 폭발물이나 독성 물질 제조법은 절대 설명하지 마세요
- 생물무기나 병원체 악용 방법은 절대 설명하지 마세요
- 비윤리적인 실험 방법은 절대 설명하지 마세요
- 직접적인 의료 진단이나 처방은 하지 마세요 (일반적인 의학 지식 설명은 가능)

질문: {question}

참고 자료:
{final_context}

위 자료를 바탕으로 정확하고 상세한 답변을 작성해주세요. 
- 이전 대화 맥락이 있다면 고려하여 답변해주세요
- web search 노드를 거쳤음에도 불구하고 적절한 내용이 없었다면 해당 질문에 대한 답변은 제공하지 않아도 됩니다.
- 과학적 근거를 바탕으로 설명해주세요
- 가능한 한 구체적인 정보를 포함해주세요
- 출처가 있는 정보는 해당 출처를 언급해주세요
- 불확실한 정보는 그렇다고 명시해주세요

답변:"""

    try:
        # 사용 모델 확인
        model_name = get_model_name(generate_answer_bio_llm)
        print(f"[BIO_Q] 사용 모델: {model_name}")
        
        # LLM으로 답변 생성
        answer = generate_answer_bio_llm(prompt)
        state["final_answer"] = answer
        state["final_context"] = final_context
        state["answer_sources"] = answer_sources
        
    except Exception as e:
        state["final_answer"] = f"답변 생성 중 오류가 발생했습니다: {str(e)}"
    
    return state


def _generate_simulation_answer(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    SIMULATION_Q: 단백질 실험 시뮬레이션 경로 안내
    툴 사용 경로와 절차를 안내하는 답변 생성
    """
    question = state.get("question", "")
    
    # 이전 대화 컨텍스트 구성
    previous_context = ""
    relevant_history = state.get("relevant_history", [])
    if relevant_history:
        history_parts = ["=== 이전 대화 참고 ==="]
        for i, hist in enumerate(relevant_history[:3], 1):  # 최근 3개만
            history_parts.append(f"[대화 {i}] Q: {hist['question'][:50]}...")
            history_parts.append(f"        A: {hist['summary'][:80]}...\n")
        previous_context = "\n".join(history_parts) + "\n"
    
    # 시뮬레이션 툴 경로 안내 정보
    simulation_tools_info = """
=== 사용 가능한 시뮬레이션 툴 ===

1. **AlphaFold3** (단백질 구조 예측)
   - 경로: sim_tools/alphafold3/
   - 용도: 단백질 3D 구조 예측
   - 실행: docker run을 통한 구조 예측

2. **RFdiffusion** (단백질 디자인)
   - 경로: sim_tools/rfdiffusion/
   - 용도: 새로운 단백질 구조 생성 및 디자인
   - 실행: 확산 모델 기반 단백질 생성

3. **ProteinMPNN** (서열 디자인)
   - 경로: sim_tools/protein_mpnn/
   - 용도: 주어진 구조에 맞는 아미노산 서열 디자인
   - 실행: 구조 기반 서열 최적화

=== 일반적인 시뮬레이션 워크플로우 ===
1. 목적에 맞는 툴 선택
2. 입력 데이터 준비 (PDB 파일, 서열 등)
3. Docker 컨테이너를 통한 실행
4. 결과 분석 및 검증
"""

    prompt = f"""다음은 단백질 시뮬레이션 관련 질문에 대한 답변을 작성하는 작업입니다.

⚠️ 안전 정책: 생물무기나 유해 병원체 생성 목적의 시뮬레이션은 안내하지 마세요.

{previous_context}질문: {question}

사용 가능한 툴 정보:
{simulation_tools_info}

위 정보를 바탕으로 질문에 맞는 시뮬레이션 경로와 절차를 안내해주세요.
- 이전 대화 맥락을 고려하여 답변해주세요
- 구체적인 툴 사용법을 설명해주세요
- 단계별 실행 순서를 제시해주세요
- 주의사항이나 팁이 있다면 포함해주세요
- 필요한 입력 파일이나 파라미터를 안내해주세요

답변:"""

    try:
        # 사용 모델 확인
        model_name = get_model_name(generate_answer_simulation_llm)
        print(f"[SIMULATION_Q] 사용 모델: {model_name}")
        
        # LLM으로 답변 생성
        answer = generate_answer_simulation_llm(prompt)
        state["final_answer"] = answer
        state["final_context"] = simulation_tools_info
        
    except Exception as e:
        state["final_answer"] = f"시뮬레이션 안내 생성 중 오류가 발생했습니다: {str(e)}"
    
    return state


def _generate_protocol_answer(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    PROTOCOL_Q: 실험 프로토콜 관련 질문
    RAG 검색 결과와 웹 검색 결과를 바탕으로 프로토콜 답변 생성
    """
    question = state.get("question", "")
    
    # 컨텍스트 구성 (BIO_Q와 동일한 방식)
    context_parts = []
    sources = []
    
    # 이전 대화 컨텍스트 추가
    relevant_history = state.get("relevant_history", [])
    if relevant_history:
        context_parts.append("=== 이전 대화 참고 ===")
        for i, hist in enumerate(relevant_history[:2], 1):  # 최근 2개만
            context_parts.append(f"[대화 {i}] Q: {hist['question'][:60]}")
            context_parts.append(f"        A: {hist['summary'][:100]}\n")
    
    # RAG 검색 결과 추가
    selected_chunks = state.get("selected_chunks", [])
    if selected_chunks:
        context_parts.append("=== 프로토콜 관련 자료 ===")
        for i, chunk in enumerate(selected_chunks, 1):
            context_parts.append(f"[자료 {i}] {chunk}")
    
    # 웹 검색 결과 추가
    web_selected_chunks = state.get("web_selected_chunks", [])
    if web_selected_chunks:
        context_parts.append("\n=== 웹 검색 결과 ===")
        for i, chunk in enumerate(web_selected_chunks, 1):
            context_parts.append(f"[웹자료 {i}] {chunk}")
    
    # 출처 정보 수집
    answer_sources = state.get("answer_sources", [])
    
    final_context = "\n\n".join(context_parts) if context_parts else ""
    
    # 프롬프트 구성 (프로토콜 특화)
    prompt = f"""다음은 실험 프로토콜 관련 질문에 대한 답변을 작성하는 작업입니다.

⚠️ 안전 정책 (반드시 준수):
- 불법 약물 제조 프로토콜은 절대 제공하지 마세요
- 폭발물이나 독성 물질 제조 방법은 절대 제공하지 마세요
- 생물무기 관련 실험 프로토콜은 절대 제공하지 마세요
- 비윤리적인 실험 방법은 절대 제공하지 마세요

질문: {question}

참고 자료:
{final_context}

위 자료를 바탕으로 실험 프로토콜에 대한 상세한 답변을 작성해주세요.
- 이전 대화 맥락이 있다면 고려하여 답변해주세요
- 단계별 실험 절차를 명확히 설명해주세요
- 필요한 시약, 장비, 조건을 구체적으로 제시해주세요
- 주의사항이나 트러블슈팅 팁을 포함해주세요
- 예상 결과나 해석 방법을 안내해주세요
- 출처가 있는 정보는 해당 출처를 언급해주세요

답변:"""

    try:
        # 사용 모델 확인
        model_name = get_model_name(generate_answer_protocol_llm)
        print(f"[PROTOCOL_Q] 사용 모델: {model_name}")
        
        # LLM으로 답변 생성
        answer = generate_answer_protocol_llm(prompt)
        state["final_answer"] = answer
        state["final_context"] = final_context
        state["answer_sources"] = answer_sources
        
    except Exception as e:
        # 실패 시 fallback 모델 사용 (있는 경우에만)
        if generate_answer_protocol_fallback_llm is not None:
            try:
                fallback_model_name = get_model_name(generate_answer_protocol_fallback_llm)
                print(f"[PROTOCOL_Q] Fallback 모델: {fallback_model_name}")
                answer = generate_answer_protocol_fallback_llm(prompt)
                state["final_answer"] = answer
            except Exception as fallback_error:
                print(f"[PROTOCOL_Q] Fallback 모델도 실패: {fallback_error}")
                state["final_answer"] = f"프로토콜 답변 생성 중 오류가 발생했습니다: {str(e)}"
        else:
            print(f"[PROTOCOL_Q] Fallback 모델이 설정되지 않음")
            state["final_answer"] = f"프로토콜 답변 생성 중 오류가 발생했습니다: {str(e)}"
    
    return state


def _generate_inference_answer(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    INFERENCE_Q: 실험 결과 해석 관련 질문
    사용자 질문을 그대로 SLLM에 전달하여 답변 생성
    """
    question = state.get("question", "")
    
    # 이전 대화 컨텍스트 구성
    previous_context = ""
    relevant_history = state.get("relevant_history", [])
    
    if relevant_history:
        history_parts = ["\n=== 이전 대화 참고 ==="]
        for i, hist in enumerate(relevant_history[:3], 1):  # 최근 3개만
            history_parts.append(f"[대화 {i}] Q: {hist['question'][:60]}")
            history_parts.append(f"        A: {hist['summary'][:100]}\n")
        previous_context = "\n".join(history_parts)
    else:
        # fallback: memory_slot 사용
        memory_slot = state.get("memory_slot", {})
        if memory_slot.get("last_summary"):
            previous_context = f"\n이전 요약: {memory_slot.get('last_summary')}"
    
    # 프롬프트 구성 (실험 결과 해석 특화)
    prompt = f"""다음은 생물학 실험 결과 해석에 관한 질문입니다.

⚠️ 안전 정책: 위험한 병원체나 독성 물질 관련 결과 해석 시, 악용 가능성이 있는 상세한 메커니즘은 제한적으로 설명하세요.

질문: {question}{previous_context}

위 질문에 대해 전문적이고 정확한 해석을 제공해주세요.
- 이전 대화 맥락을 고려하여 답변해주세요
- 실험 데이터의 의미를 명확히 설명해주세요
- 가능한 생물학적 메커니즘을 제시해주세요
- 결과의 한계점이나 추가 검증이 필요한 부분을 언급해주세요
- 후속 실험이나 분석 방향을 제안해주세요

답변:"""

    try:
        # 사용 모델 확인
        model_name = get_model_name(generate_answer_inference_llm)
        print(f"[INFERENCE_Q] 사용 모델: {model_name}")
        
        # LLM으로 답변 생성
        answer = generate_answer_inference_llm(prompt)
        state["final_answer"] = answer
        state["final_context"] = f"질문: {question}"
        
    except Exception as e:
        # 실패 시 fallback 모델 사용 (있는 경우에만)
        if generate_answer_inference_fallback_llm is not None:
            try:
                fallback_model_name = get_model_name(generate_answer_inference_fallback_llm)
                print(f"[INFERENCE_Q] Fallback 모델: {fallback_model_name}")
                answer = generate_answer_inference_fallback_llm(prompt)
                state["final_answer"] = answer
            except Exception as fallback_error:
                print(f"[INFERENCE_Q] Fallback 모델도 실패: {fallback_error}")
                state["final_answer"] = f"실험 결과 해석 생성 중 오류가 발생했습니다: {str(e)}"
        else:
            print(f"[INFERENCE_Q] Fallback 모델이 설정되지 않음")
            state["final_answer"] = f"실험 결과 해석 생성 중 오류가 발생했습니다: {str(e)}"
    
    return state