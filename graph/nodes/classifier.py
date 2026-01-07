from typing import Dict, Any
from graph.llm_config import (
    classifier_is_bio_related_simple_check_llm,
    classifier_classify_question_node_llm,
    get_model_name
)
from graph.nodes.memory import memory_read_basic_tool
from graph.logger_config import get_logger

logger = get_logger(__name__)


def _check_needs_previous_context(q: str) -> bool:
    """
    LLM을 사용하여 질문이 이전 대화를 참조하는지 판단합니다.
    
    Args:
        q: 사용자 질문
        
    Returns:
        bool: 이전 대화 참조가 필요하면 True, 아니면 False
    """
    prompt = f"""다음 질문이 이전 대화 내용을 참조하고 있는지 판단하세요.

질문: {q}

이전 대화 참조 판단 기준:
- 지시대명사 사용 ("그거", "저거", "그것", "그 단백질", "그 논문" 등)
- 시간적 참조 ("앞에서", "방금", "위에서", "전에" 등)
- 생략된 주어나 목적어 ("구조는?", "어떻게 진행해?", "결과는?" 등)
- 대화의 연속성을 전제로 한 질문

반드시 "YES" 또는 "NO"만 출력하세요:"""

    try:
        model_name = get_model_name(classifier_is_bio_related_simple_check_llm)
        logger.info(f"이전 대화 참조 판단 모델: {model_name}")
        response = classifier_is_bio_related_simple_check_llm(prompt).strip().upper()
        return response == "YES"
    except Exception as e:
        logger.error(f"이전 대화 참조 판단 실패: {e}", exc_info=True)
        # 오류 시 안전하게 False 반환 (메모리 없이 진행)
        return False


def _classify_with_llm(q: str, chat_room_id: str = None, user_id: str = "default") -> str:
    """
    GPT-5-nano를 사용하여 질문을 5가지 카테고리 중 하나로 분류합니다.
    매개변수:
        q (str): 사용자가 입력한 질문 문자열
    반환값:
        str: 분류된 카테고리 이름 (NO_RELATION, BIO_Q, SIMULATION_Q, PROTOCOL_Q, INFERENCE_Q 중 하나)
    """
    
    # LLM에게 이전 대화 참조 여부를 판단하도록 요청
    previous_context = ""
    needs_previous = _check_needs_previous_context(q)
    
    logger.info(f"이전 대화 참조 필요: {needs_previous}")
    
    if needs_previous and chat_room_id:
        try:
            prev_data = memory_read_basic_tool(chat_room_id, user_id)
            if prev_data["has_previous"]:
                previous_context = f"""
이전 대화 정보:
- 이전 질문: {prev_data['last_question']}
- 이전 요약: {prev_data['last_summary']}
- 이전 케이스 타입: {prev_data['last_case_type']}
- 이전 주제: {prev_data['last_topic']}
"""
                logger.info("이전 대화 로드 완료")
        except Exception as e:
            logger.error(f"이전 대화 로드 실패: {e}", exc_info=True)
    
    # AI에게 보낼 프롬프트(Prompt)를 만듭니다
    system_prompt = (
        "다음 사용자 질문을 6가지 카테고리 중 하나로 분류하세요.\n\n"
        "⚠️ 중요: 꼬리질문(이전 대화 참조)이어도, 원본 질문의 주제와 의도를 먼저 파악하세요.\n"
        "예: '내가 최근에 물어봤던 논문 내용이 뭐더라?' → '논문'이 핵심이므로 BIO_Q로 분류\n\n"

        "USER_INFO (사용자 인적사항)\n"
        " - 사용자가 자신의 신분, 직업, 배경 등을 알려주는 경우\n"
        " - 사용자가 이전에 알려준 자신의 정보를 묻는 경우\n"
        " - 키워드: '학생', '연구원', '대학원생', '교수', '포닥', '박사과정', '석사과정', '학부생', '내 이름', '내 직업', '나는 누구' 등\n"
        " - 예: '저는 생물학과 학생입니다', '저는 단백질 연구하는 연구원이에요', '내 이름이 뭐라고?', '내 직업이 뭐더라?', '나는 누구야?'\n\n"

        "BIO_Q (생물학/의학/과학 용어, 개념, 논문, 임상연구 질문) ⭐ 최우선 분류 대상 ⭐\n"
        " - 생물학/의학/과학 용어나 약어의 의미, 정의, 기능을 묻는 질문 (매우 중요!)\n"
        " - 단백질명, 유전자명, 화합물명, 약물명, 질병명, 실험 기법명 등의 설명 요청\n"
        " - 논문 내용, 단백질 구조/기능, 생물학적 메커니즘, 임상연구 배경\n"
        " - '~이란?', '~가 뭐야?', '~는?', '~설명해줘', '~에 대해 알려줘' 형태의 용어 질문\n"
        " - 대문자 약어(PD-1, CAR-T, CRISPR, mRNA, Tm, IC50, Kd, EC50 등)는 거의 100% 과학 용어\n"
        " - 키워드: '논문', '연구', '임상', '단백질', '유전자', '구조', '메커니즘', '기전', '치료', '약물' 등\n"
        " - 예시:\n"
        "   * 'PD-1이 뭐야?' → BIO_Q (단백질명 질문)\n"
        "   * 'CAR-T는?' → BIO_Q (치료법 약어)\n"
        "   * 'Tm이란?' → BIO_Q (생물학 용어)\n"
        "   * 'IC50 설명해줘' → BIO_Q (약리학 용어)\n"
        "   * 'CRISPR가 뭐야?' → BIO_Q (기술명)\n"
        "   * 'mRNA 백신이란?' → BIO_Q (개념 질문)\n"
        "   * '단백질 폴딩 논문 정리해줘' → BIO_Q\n"
        "   * 'CAR-T 치료 기전은?' → BIO_Q\n"
        "   * 'PD-1 inhibitor 임상연구 결과는?' → BIO_Q\n\n"

        "SIMULATION_Q (단백질 등 생물학적 실험 경로 안내 질문)\n"
        " - 단백질 실험이나 시뮬레이션의 절차, 방법, 경로를 묻는 질문\n"
        " - 예: '단백질 구조 예측 시뮬레이션 어떻게 해?', '분자 동역학 시뮬레이션 순서는?'\n\n"

        "PROTOCOL_Q (단백질 등 생물학적 실험 프로토콜 질문)\n"
        " - 구체적인 실험 프로토콜, 실험 조건, 파라미터 설정에 대한 질문\n"
        " - 예: 'ProteinMPNN 파라미터 설정법은?', 'RFdiffusion 실행 조건은?'\n\n"

        "INFERENCE_Q (단백질 등 생물학적 실험 결과 해석 질문)\n"
        " - 실험 결과, 데이터, 그래프를 해석하거나 의미를 분석하는 질문\n"
        " - 예: '이 단백질 구조가 안정한가?', 'RMSD 값이 높으면 어떤 의미?'\n\n"

        "NO_RELATION\n"
        " - 생물학/의학/과학과 전혀 관련 없는 일상적인 질문\n"
        " - 예: '오늘 날씨?', '파이썬 코드 작성해줘', '점심 메뉴 추천해줘', '영화 추천'\n\n"

        f"{previous_context}"

        "⚠️ 분류 기준 (우선순위 순서):\n"
        "1. 사용자가 자신의 신분/배경을 밝히는 경우 → USER_INFO\n"
        "2. 생물학/의학/과학 용어나 약어 질문 ('~이란?', '~가 뭐야?', '~는?') → BIO_Q\n"
        "3. 대문자 약어(PD-1, CAR-T, CRISPR, Tm, IC50 등) → 거의 100% BIO_Q\n"
        "4. 단백질명, 유전자명, 화합물명, 질병명 등 과학 관련 고유명사 → BIO_Q\n"
        "5. 논문, 연구, 임상 관련 내용 → BIO_Q\n"
        "6. 실험 절차/경로 질문 → SIMULATION_Q\n"
        "7. 실험 프로토콜/조건 질문 → PROTOCOL_Q\n"
        "8. 실험 결과 해석 질문 → INFERENCE_Q\n"
        "9. 위 어느 것에도 해당하지 않는 일상적 질문 → NO_RELATION\n\n"

        "⚠️ 주의사항:\n"
        "- 짧은 질문(2-3단어)이라도 과학 용어가 포함되어 있으면 반드시 BIO_Q로 분류\n"
        "- '~이 뭐야?', '~란?', '~는?' 형태는 용어 설명 요청이므로 BIO_Q\n"
        "- 대문자 약어는 거의 대부분 과학/의학 용어입니다\n"
        "- 확실하지 않으면 BIO_Q로 분류 (과학 관련 질문을 놓치는 것보다 나음)\n\n"

        "반드시 아래 중 하나만 출력하세요:\n"
        "USER_INFO, BIO_Q, SIMULATION_Q, PROTOCOL_Q, INFERENCE_Q, NO_RELATION"
    )

    # 사용자가 입력한 실제 질문을 AI에게 전달할 형식으로 만듭니다
    user_prompt = f"질문: {q}"

    try:
        # 사용 모델 확인
        model_name = get_model_name(classifier_classify_question_node_llm)
        logger.info(f"질문 분류 모델: {model_name}")
        
        # LLM을 사용하여 질문을 분류합니다
        # 전체 프롬프트를 하나로 합쳐서 전달합니다
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        response = classifier_classify_question_node_llm(full_prompt)
        
        # AI가 반환한 답변에서 카테고리 이름을 추출합니다
        # .strip()은 앞뒤 공백을 제거하는 함수입니다
        label = response.strip()

        # 허용된 카테고리 목록 (정확히 이 6가지만 유효합니다)
        valid_categories = {
            "USER_INFO",
            "NO_RELATION",
            "BIO_Q",
            "SIMULATION_Q",
            "PROTOCOL_Q",
            "INFERENCE_Q",
        }

        # AI가 반환한 답변이 허용된 카테고리 중 하나인지 확인합니다
        # 만약 정확한 카테고리 이름이면 그대로 반환합니다
        if label in valid_categories:
            logger.info(f"질문 분류 결과: {label}")
            return label

        # AI가 예상치 못한 답변을 했을 경우 (오타나 잘못된 형식 등)
        # 안전하게 기본값인 "NO_RELATION"을 반환합니다
        logger.warning(f"예상치 못한 분류 결과: {label}, 기본값 NO_RELATION 반환")
        return "NO_RELATION"

    except Exception as e:
        # 오류가 발생했을 때 (예: 인터넷 연결 문제, API 오류 등)
        # 오류 메시지를 로깅하고 기본값을 반환합니다
        logger.error(f"질문 분류 중 오류 발생: {e}", exc_info=True)
        return "NO_RELATION"


def classify_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    
    # 노드 진입 로그
    question = str(state.get('question', ''))[:30]
    conversation_id = state.get('conversation_id', '')
    logger.info(f"[CLASSIFIER NODE] 시작 - question: {question}..., conversation_id: {conversation_id}")

    # case_type이 이미 지정되어 있으면 LLM 호출 없이 바로 다음 노드로 이동
    existing_case_type = state.get("case_type")
    if existing_case_type and existing_case_type != "N/A":
        logger.info(f"case_type이 이미 지정됨: '{existing_case_type}' (LLM 호출 건너뜀)")
        # is_follow_up만 설정하고 바로 반환
        q = (state.get("question") or "").strip()
        if q:
            needs_previous = _check_needs_previous_context(q)
            state["is_follow_up"] = needs_previous
        else:
            state["is_follow_up"] = False
        
        # 노드 종료 로그
        logger.info(f"[CLASSIFIER NODE] 종료 (기존 case_type 사용) - case_type: {state.get('case_type', '')}, is_follow_up: {state.get('is_follow_up', False)}")
        
        return state

    # 필터 타입이 있으면 LLM 호출 없이 직접 case_type 설정
    filter_type = state.get("filter_type")
    if filter_type:
        # 필터 타입을 case_type으로 매핑
        filter_to_case_type = {
            "paper": "BIO_Q",  # 논문/임상
            "clinical": "BIO_Q",  # 임상 (하위 호환성)
            "protocol": "PROTOCOL_Q",
            "simulation": "SIMULATION_Q",
            "interpretation": "INFERENCE_Q",  # 결과 해석
        }
        
        case_label = filter_to_case_type.get(filter_type)
        if case_label:
            logger.info(f"필터 타입 '{filter_type}' → case_type '{case_label}' (LLM 호출 건너뜀)")
            state["case_type"] = case_label
            state["is_follow_up"] = False
            
            # 노드 종료 로그
            logger.info(f"[CLASSIFIER NODE] 종료 (필터 기반) - case_type: {state.get('case_type', '')}, is_follow_up: {state.get('is_follow_up', False)}")
            
            return state

    # state 딕셔너리에서 'question' 키의 값을 가져옵니다
    # 만약 값이 없으면 빈 문자열("")을 사용합니다
    # .strip()은 앞뒤 공백을 제거합니다 (예: "  안녕  " → "안녕")
    q = (state.get("question") or "").strip()

    # 질문이 비어있는지 확인합니다 (사용자가 아무것도 입력하지 않았거나 공백만 입력한 경우)
    if not q:
        # 질문이 없으면 기본값으로 "NO_RELATION"을 설정합니다
        state["case_type"] = "NO_RELATION"
        state["is_follow_up"] = False
        return state  # 결과를 반환하고 함수를 종료합니다

    # 질문이 있으면 AI를 사용해서 질문을 분류합니다
    # _classify_with_llm 함수를 호출하여 카테고리 이름을 받아옵니다
    chat_room_id = state.get("conversation_id")
    user_id = state.get("user_id", "default")
    
    # 꼬리질문 여부 판단
    needs_previous = _check_needs_previous_context(q)
    state["is_follow_up"] = needs_previous
    
    # 꼬리질문인 경우 이전 대화의 case_type 가져오기
    if needs_previous and chat_room_id:
        try:
            prev_data = memory_read_basic_tool(chat_room_id, user_id)
            if prev_data["has_previous"] and prev_data["last_case_type"]:
                state["reference_case_type"] = prev_data["last_case_type"]
                logger.info(f"꼬리질문 감지: 참조 케이스 타입 = {prev_data['last_case_type']}")
        except Exception as e:
            logger.error(f"참조 케이스 타입 가져오기 실패: {e}", exc_info=True)
    
    case_label = _classify_with_llm(q, chat_room_id, user_id)
    
    # 분류 결과를 state 딕셔너리에 'case_type'이라는 키로 저장합니다
    # 이렇게 하면 다른 함수에서도 이 분류 결과를 사용할 수 있습니다
    state["case_type"] = case_label
    
    # NO_RELATION일 때 안내 메시지 추가
    if case_label == "NO_RELATION":
        state["final_answer"] = (
            "죄송합니다. 해당 질문은 생물학/단백질 관련 질문이 아닌 것으로 판단됩니다.\n"
            "생물학, 단백질, 임상연구, 실험 프로토콜 등에 관한 질문을 해주세요."
        )

    # 노드 종료 로그
    final_answer_preview = str(state.get('final_answer', ''))[:30]
    logger.info(
        f"[CLASSIFIER NODE] 종료 - case_type: {state.get('case_type', '')}, "
        f"is_follow_up: {state.get('is_follow_up', False)}, "
        f"reference_case_type: {state.get('reference_case_type', 'N/A')}, "
        f"final_answer: {final_answer_preview}..."
    )
    
    # 분류 결과가 저장된 state를 반환합니다
    return state
