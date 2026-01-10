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
from graph.logger_config import get_logger

logger = get_logger(__name__)

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
    question_preview = str(question)[:30]
    selected_chunks_count = len(state.get('selected_chunks', []))
    web_selected_chunks_count = len(state.get('web_selected_chunks', []))
    logger.info(f"[GENERATE_ANSWER NODE] 시작 - question: {question_preview}..., case_type: {case_type}, selected_chunks: {selected_chunks_count}개, web_selected_chunks: {web_selected_chunks_count}개")
    
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
    final_answer_preview = str(state.get('final_answer', ''))[:30]
    logger.info(f"[GENERATE_ANSWER NODE] 종료 - final_answer: {final_answer_preview}...")
    
    return state


def _generate_user_info_answer(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    USER_INFO: 사용자 인적사항 관련 질문
    사용자의 인적사항을 언급하며 친근하게 응답
    """
    question = state.get("question", "")
    
    # 사용 모델 확인
    model_name = get_model_name(generate_answer_info_llm)
    logger.info(f"[USER_INFO] 사용 모델: {model_name}")
    
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
    logger.info(f"[USER_INFO] sLLM에 전달되는 최종 프롬프트:\n{prompt}")
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
        logger.debug(f"web_selected_chunks 수신: {len(web_selected_chunks)}개, 타입: {type(web_selected_chunks)}")
        for i, chunk in enumerate(web_selected_chunks[:3], 1):  # 최대 3개만 로깅
            chunk_type = type(chunk)
            chunk_preview = str(chunk)[:80] if chunk else "None"
            logger.debug(f"  [{i}] 타입: {chunk_type}, 값: {chunk_preview}...")
        
        context_parts.append("\n=== 웹 검색 결과 ===")
        for i, chunk in enumerate(web_selected_chunks, 1):
            # 문자열로 변환 (하위 호환성)
            chunk_str = str(chunk) if not isinstance(chunk, str) else chunk
            context_parts.append(f"[웹자료 {i}] {chunk_str}")
    
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

📋 답변 작성 지침:
- 이전 대화 맥락이 있다면 고려하여 답변해주세요
- web search 노드를 거쳤음에도 불구하고 적절한 내용이 없었다면 해당 질문에 대한 답변은 제공하지 않아도 됩니다.
- 과학적 근거를 바탕으로 설명해주세요
- 가능한 한 구체적인 정보를 포함해주세요
- 출처가 있는 정보는 해당 출처를 언급해주세요
- 불확실한 정보는 그렇다고 명시해주세요

📝 답변 형식 (반드시 마크다운 형식으로 작성):
1. **구조화된 형식 사용**: 주요 내용은 제목(## 또는 ###)으로 구분해주세요
2. **리스트 활용**: 여러 항목이 있을 경우 번호 있는 리스트(1., 2., 3.) 또는 불릿 포인트(-)를 사용해주세요
3. **단락 구분**: 각 주제는 명확하게 단락으로 구분해주세요
4. **가독성**: 간결하고 명확하게 작성하되, 구조화된 형식을 유지해주세요

예시 형식:
```markdown
[주제에 대한 간단한 소개 문단]

## 주요 특징
- 특징 1: 설명
- 특징 2: 설명
- 특징 3: 설명

## 기능 및 역할
1. 기능 1: 상세 설명
2. 기능 2: 상세 설명

## 활용 분야
- 활용 1: 설명
- 활용 2: 설명

[요약 문단]
```

답변:"""

    try:
        # 사용 모델 확인
        model_name = get_model_name(generate_answer_bio_llm)
        logger.info(f"[BIO_Q] 사용 모델: {model_name}")
        
        # LLM으로 답변 생성
        logger.info(f"[BIO_Q] sLLM에 전달되는 최종 프롬프트:\n{prompt}")
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
        logger.info(f"[SIMULATION_Q] 사용 모델: {model_name}")
        
        # LLM으로 답변 생성
        logger.info(f"[SIMULATION_Q] sLLM에 전달되는 최종 프롬프트:\n{prompt}")
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
        logger.debug(f"web_selected_chunks 수신: {len(web_selected_chunks)}개, 타입: {type(web_selected_chunks)}")
        for i, chunk in enumerate(web_selected_chunks[:3], 1):  # 최대 3개만 로깅
            chunk_type = type(chunk)
            chunk_preview = str(chunk)[:80] if chunk else "None"
            logger.debug(f"  [{i}] 타입: {chunk_type}, 값: {chunk_preview}...")
        
        context_parts.append("\n=== 웹 검색 결과 ===")
        for i, chunk in enumerate(web_selected_chunks, 1):
            # 문자열로 변환 (하위 호환성)
            chunk_str = str(chunk) if not isinstance(chunk, str) else chunk
            context_parts.append(f"[웹자료 {i}] {chunk_str}")
    
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

📋 답변 작성 지침:
- 이전 대화 맥락이 있다면 고려하여 답변해주세요
- 단계별 실험 절차를 명확히 설명해주세요
- 필요한 시약, 장비, 조건을 구체적으로 제시해주세요
- 주의사항이나 트러블슈팅 팁을 포함해주세요
- 예상 결과나 해석 방법을 안내해주세요
- 출처가 있는 정보는 해당 출처를 언급해주세요

📝 답변 형식 (반드시 마크다운 형식으로 작성):
1. **구조화된 형식 사용**: 주요 내용은 제목(## 또는 ###)으로 구분해주세요
2. **리스트 활용**: 여러 항목이 있을 경우 번호 있는 리스트(1., 2., 3.) 또는 불릿 포인트(-)를 사용해주세요
3. **단락 구분**: 각 주제는 명확하게 단락으로 구분해주세요
4. **가독성**: 간결하고 명확하게 작성하되, 구조화된 형식을 유지해주세요
5. **프로토콜 특화**: 실험 절차나 방법은 단계별로 번호 있는 리스트로 작성해주세요

예시 형식:
```markdown
[프로토콜에 대한 간단한 소개 문단]

## 개요
[프로토콜의 목적과 배경 설명]

## 준비 사항
- 재료 1: 설명
- 재료 2: 설명
- 장비 1: 설명

## 실험 절차
1. 단계 1: 상세 설명
2. 단계 2: 상세 설명
3. 단계 3: 상세 설명

## 주의사항
- 주의 1: 설명
- 주의 2: 설명

[요약 문단]
```

답변:"""

    try:
        # 사용 모델 확인
        model_name = get_model_name(generate_answer_protocol_llm)
        logger.info(f"[PROTOCOL_Q] 사용 모델: {model_name}")
        
        # LLM으로 답변 생성
        logger.info(f"[PROTOCOL_Q] sLLM에 전달되는 최종 프롬프트:\n{prompt}")
        answer = generate_answer_protocol_llm(prompt)
        state["final_answer"] = answer
        state["final_context"] = final_context
        state["answer_sources"] = answer_sources
        
    except Exception as e:
        # 실패 시 fallback 모델 사용 (있는 경우에만)
        if generate_answer_protocol_fallback_llm is not None:
            try:
                fallback_model_name = get_model_name(generate_answer_protocol_fallback_llm)
                logger.warning(f"[PROTOCOL_Q] Fallback 모델 사용: {fallback_model_name}")
                logger.info(f"[PROTOCOL_Q] Fallback 모델에 전달되는 최종 프롬프트:\n{prompt}")
                answer = generate_answer_protocol_fallback_llm(prompt)
                state["final_answer"] = answer
            except Exception as fallback_error:
                logger.error(f"[PROTOCOL_Q] Fallback 모델도 실패: {fallback_error}", exc_info=True)
                state["final_answer"] = f"프로토콜 답변 생성 중 오류가 발생했습니다: {str(e)}"
        else:
            logger.warning("[PROTOCOL_Q] Fallback 모델이 설정되지 않음")
            state["final_answer"] = f"프로토콜 답변 생성 중 오류가 발생했습니다: {str(e)}"
    
    return state


def _generate_inference_answer(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    INFERENCE_Q: 실험 결과 해석 관련 질문
    Gemma3-12B-it 기반 파인튜닝 sLLM 모델용
    이미지 분석 결과(image_analysis_markdown)를 포함하여 답변 생성

    주의: Stage 2, 3은 비활성화되어 있으므로 마크다운만 사용
    """
    question = state.get("question", "")
    image_analysis_markdown = state.get("image_analysis_markdown")

    # 이전 대화 컨텍스트 구성 (영어 프롬프트와 일치)
    previous_context = ""
    relevant_history = state.get("relevant_history", [])

    if relevant_history:
        history_parts = ["\n=== Previous Conversation Reference ==="]
        for i, hist in enumerate(relevant_history[:3], 1):  # 최근 3개만
            history_parts.append(f"[Conversation {i}] Q: {hist['question'][:60]}")
            history_parts.append(f"        A: {hist['summary'][:100]}\n")
        previous_context = "\n".join(history_parts)
    else:
        # fallback: memory_slot 사용
        memory_slot = state.get("memory_slot", {})
        if memory_slot.get("last_summary"):
            previous_context = f"\nPrevious Summary: {memory_slot.get('last_summary')}"

    # Stage 1 마크다운 결과를 image_context로 변환
    image_context = ""

    # 디버깅 로그
    logger.info(f"[INFERENCE_Q] image_analysis_markdown 존재 여부: {image_analysis_markdown is not None}")
    if image_analysis_markdown:
        logger.info(f"[INFERENCE_Q] image_analysis_markdown 길이: {len(image_analysis_markdown)} chars")
        logger.info(f"[INFERENCE_Q] image_analysis_markdown 미리보기 (첫 500자):\n{image_analysis_markdown[:500]}")

        # 마크다운을 image_context로 사용 (Stage 2, 3 비활성화)
        logger.info(f"[INFERENCE_Q] Stage 1 마크다운 사용 - 길이: {len(image_analysis_markdown)} chars")
        # 영어 프롬프트 (마크다운도 영어로 작성됨)
        image_context = f"""=== Attached Experimental Image Analysis Results (Markdown Format) ===
{image_analysis_markdown}

Please refer to the above experimental results data (in markdown format) when answering the question."""
    else:
        logger.warning("[INFERENCE_Q] 이미지 분석 결과가 없습니다! state에 image_analysis_markdown이 없음")
        image_context = "No experimental image data available."
    
    # System Prompt: 규칙과 지침 (영어 - 파인튜닝 데이터셋과 일치)
    # Gemma3-12B-it 기반 파인튜닝 모델은 영어 데이터셋으로 학습되었으므로 영어 프롬프트 사용
    system_prompt = """You are a grounded interpretation assistant for experimental results.

    Your role is to:
    - Organize extracted facts into a coherent scientific summary
    - Evaluate whether interpretation is possible based only on evidence
    - Explicitly state when interpretation is NOT possible

    Absolute Rules:
    A) Evidence Restriction (CRITICAL - MOST IMPORTANT):
    - You MUST NOT introduce any fact not present in the extracted figure data.
    - You MUST NOT invent time points, concentrations, or experimental conditions.
    - If a piece of information (e.g., "24 hours", "48 hours", specific concentrations) is NOT explicitly mentioned in the extracted data, DO NOT mention it in your response.
    - All statements must be directly traceable to the extracted figure facts.
    - If you cannot find certain information in the data, write "데이터에 명시되지 않음" instead of guessing.

    B) Inference Restriction:
    - You may describe numerical or structural relationships (higher/lower, larger/smaller, present/absent).
    - You MUST NOT assert causality, function, mechanism, or biological meaning without explicit experimental evidence.

    C) Language Restriction:
    - Prohibited: "causes", "leads to", "results in", "because of", "therefore", "suggests mechanism".
    - Allowed: "higher than", "lower than", "present", "absent", "different", "similar".

    D) Insufficient Evidence Handling:
    - If a section cannot be filled, explicitly write: "판단 불가 — [구체적 이유]".
    - Example: If time points are not mentioned in the data, write "판단 불가 — 시간 정보가 데이터에 명시되지 않음"

    E) Mechanism:
    - Only include if the target, intervention, and system are explicitly specified.
    - Otherwise omit the section entirely.

    F) Follow-up Experiments:
    - Only propose experiments that extend what is already present in the extracted data (e.g., more time points, more doses, additional groups).
    - DO NOT propose experiments based on information you hallucinated.

    G) Data Grounding Verification:
    - Before writing each statement, verify that it is directly supported by the extracted figure facts.
    - If you find yourself writing something that is not in the data, STOP and revise.

    Output style:
    - Structured Markdown
    - Professional scientific tone in Korean
    - No speculation, no narrative, no persuasion
    - No hallucination of experimental conditions
    """


    # User Prompt: 실제 데이터만 (영어 - 파인튜닝 데이터셋과 일치)
    # 질문은 사용자 입력 그대로 사용 (한글 질문도 가능)
    user_prompt = f"""Question: {question}

[Extracted Figure Facts]
{image_context}

[Additional Context]
{previous_context if previous_context else "No previous context available."}

CRITICAL INSTRUCTION:
- The [Extracted Figure Facts] section above contains ALL the information available from the experimental figure.
- You MUST base your entire response ONLY on the facts explicitly stated in [Extracted Figure Facts].
- DO NOT add any information that is not present in the extracted data (e.g., time points, concentrations, conditions).
- If the data does not mention specific information (e.g., "24 hours", "48 hours"), DO NOT mention it in your response.
- If you find yourself about to write something not in the extracted facts, write "데이터에 명시되지 않음" instead.
- 그래프가 여러개라면, 각각의 그래프를 구분해서 답변하기. 다른 그래프의 값을 섞어서 대답하지 말 것. 
Please provide a professional and structured interpretation strictly based on the extracted facts.

Response Structure:

## 실험 결과 요약
- 핵심 관측 사실을 요약 (추출된 데이터에 있는 내용만)

## 확인된 사실
- 추출된 데이터에서 직접 확인되는 사항만 나열
- 데이터에 없는 정보는 절대 추가하지 말 것

## 관찰된 수치적 관계
- higher/lower, present/absent 등 관계만 기술 (의미/원인 금지)
- 추출된 데이터에 있는 그룹/조건 이름만 사용

## 해석
- 해석 가능하면 조건부로 작성
- 불가능하면: "판단 불가 — [이유]"


## 메커니즘 가능성
- 명확히 주어진 경우만 기술
- 불충분하면 섹션 생략

## 한계점
- 데이터 자체의 한계만 기술
- 추출된 데이터에서 누락된 정보가 있으면 명시

## 후속 실험 제안
- 추출된 데이터에 있는 조건/그룹을 기반으로만 제안
- 데이터에 없는 조건을 가정하지 말 것
- 실험을 통해 확인해야한다는 것을 명시

Response (in Korean, Markdown only):
"""

    # 디버깅: 생성된 프롬프트 길이 확인
    logger.info(f"[INFERENCE_Q] image_context 길이: {len(image_context)} chars")
    logger.info(f"[INFERENCE_Q] user_prompt 총 길이: {len(user_prompt)} chars")
    logger.debug(f"[INFERENCE_Q] user_prompt 전체:\n{user_prompt}")

    try:
        # 사용 모델 확인
        model_name = get_model_name(generate_answer_inference_llm)
        logger.info(f"[INFERENCE_Q] 사용 모델: {model_name} (Gemma3-12B-it 기반)")
        
        # LLM으로 답변 생성 (System/User role 분리, max_tokens 증가)
        logger.info(f"[INFERENCE_Q] System Prompt 길이: {len(system_prompt)} chars")
        logger.info(f"[INFERENCE_Q] User Prompt 길이: {len(user_prompt)} chars")
        logger.debug(f"[INFERENCE_Q] System Prompt:\n{system_prompt}")
        logger.debug(f"[INFERENCE_Q] User Prompt:\n{user_prompt}")
        
        # sllm 함수에 system_prompt 전달 (Gemma3-12B-it 기반 파인튜닝 모델용)
        # generate_answer_inference_llm은 sllm을 직접 참조하므로 sllm을 직접 호출
        from graph.nodes.call_llm import sllm
        answer = sllm(prompt=user_prompt, system_prompt=system_prompt, temperature=0.7, max_tokens=2048)
        
        state["final_answer"] = answer
        state["final_context"] = f"질문: {question}"
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"[INFERENCE_Q] 답변 생성 실패: {error_msg}", exc_info=True)
        
        # 사용자 친화적인 에러 메시지 생성
        user_friendly_message = "죄송합니다. 실험 결과 해석을 생성하는 중에 문제가 발생했습니다."
        
        # 특정 에러 타입별 처리
        if "max_tokens" in error_msg or "max_completion_tokens" in error_msg:
            user_friendly_message = "죄송합니다. 입력한 이미지 데이터가 너무 커서 처리할 수 없습니다. 더 작은 이미지로 다시 시도해주세요."
            logger.warning("[INFERENCE_Q] max_tokens 에러 발생 - 입력 데이터가 너무 큼")
        elif "Pod가 비활성화" in error_msg or "연결" in error_msg:
            user_friendly_message = "죄송합니다. 현재 서비스를 일시적으로 사용할 수 없습니다. 잠시 후 다시 시도해주세요."
            logger.warning("[INFERENCE_Q] 서버 연결 에러 발생")
        elif "timeout" in error_msg.lower():
            user_friendly_message = "죄송합니다. 응답 시간이 초과되었습니다. 잠시 후 다시 시도해주세요."
            logger.warning("[INFERENCE_Q] 타임아웃 에러 발생")
        
        # 실패 시 fallback 모델 사용 (gpt-5.2)
        if generate_answer_inference_fallback_llm is not None:
            try:
                fallback_model_name = get_model_name(generate_answer_inference_fallback_llm)
                logger.warning(f"[INFERENCE_Q] Fallback 모델 사용 시도: {fallback_model_name}")
                logger.info(f"[INFERENCE_Q] Fallback 모델에 전달되는 User Prompt:\n{user_prompt}")
                # Fallback 모델 (gpt-5.2) 호출 - system_prompt 지원
                answer = generate_answer_inference_fallback_llm(
                    prompt=user_prompt, 
                    system_prompt=system_prompt, 
                    temperature=0.7, 
                    max_tokens=2048
                )
                state["final_answer"] = answer
                logger.info("[INFERENCE_Q] Fallback 모델(gpt-5.2)로 답변 생성 성공")
            except Exception as fallback_error:
                logger.error(f"[INFERENCE_Q] Fallback 모델도 실패: {fallback_error}", exc_info=True)
                state["final_answer"] = user_friendly_message
        else:
            logger.warning("[INFERENCE_Q] Fallback 모델이 설정되지 않음")
            state["final_answer"] = user_friendly_message
    
    return state