from typing import Dict, Any
from graph.nodes.call_llm import gpt5_nano
from graph.nodes.memory import memory_read_basic_tool


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
        response = gpt5_nano(prompt).strip().upper()
        return response == "YES"
    except Exception as e:
        print(f"[Check previous context error] {e}")
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
    
    print(f"[Classifier] 이전 대화 참조 필요: {needs_previous}")
    
    if needs_previous and chat_room_id:
        try:
            prev_data = memory_read_basic_tool(chat_room_id, user_id)
            if prev_data["has_previous"]:
                previous_context = f"""
이전 대화 정보:
- 이전 질문: {prev_data['last_question']}
- 이전 답변 요약: {prev_data['last_answer_summary']}
- 이전 케이스 타입: {prev_data['last_case_type']}
- 이전 주제: {prev_data['last_topic']}
"""
                print(f"[Classifier] 이전 대화 로드 완료")
        except Exception as e:
            print(f"[Previous context error] {e}")
    
    # AI에게 보낼 프롬프트(Prompt)를 만듭니다
    system_prompt = (
        "다음 사용자 질문을 5가지 카테고리 중 하나로 분류하세요.\n\n"
        "NO_RELATION\n"
        " - 단백질 등 생물학적 관련 질문이 아닌 질문\n"
        " - 예: '오늘 날씨?', '파이썬 코드 작성해줘', '점심 메뉴 추천해줘'\n\n"

        "BIO_Q (단백질 등 생물학적 관련 논문, 임상연구 관련 질문)\n"
        " - 논문 내용, 단백질 구조/기능, 생물학적 메커니즘, 임상연구 배경에 대한 질문\n"
        " - 예: '단백질 폴딩 논문 정리해줘', 'CAR-T 치료 기전은?', 'PD-1 inhibitor 임상연구 결과는?'\n\n"

        "SIMULATION_Q (단백질 등 생물학적 실험 경로 안내 질문)\n"
        " - 단백질 실험이나 시뮬레이션의 절차, 방법, 경로를 묻는 질문\n"
        " - 예: '단백질 구조 예측 시뮬레이션 어떻게 해?', '분자 동역학 시뮬레이션 순서는?'\n\n"

        "PROTOCOL_Q (단백질 등 생물학적 실험 프로토콜 질문)\n"
        " - 구체적인 실험 프로토콜, 실험 조건, 파라미터 설정에 대한 질문\n"
        " - 예: 'ProteinMPNN 파라미터 설정법은?', 'RFdiffusion 실행 조건은?'\n\n"

        "INFERENCE_Q (단백질 등 생물학적 실험 결과 해석 질문)\n"
        " - 실험 결과, 데이터, 그래프를 해석하거나 의미를 분석하는 질문\n"
        " - 예: '이 단백질 구조가 안정한가?', 'RMSD 값이 높으면 어떤 의미?'\n\n"
        
        f"{previous_context}"
        
        "반드시 아래 중 하나만 출력하세요:\n"
        "NO_RELATION, BIO_Q, SIMULATION_Q, PROTOCOL_Q, INFERENCE_Q"
    )

    # 사용자가 입력한 실제 질문을 AI에게 전달할 형식으로 만듭니다
    user_prompt = f"질문: {q}"

    try:
        # GPT-5-nano를 사용하여 질문을 분류합니다
        # 전체 프롬프트를 하나로 합쳐서 전달합니다
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        response = gpt5_nano(full_prompt)
        
        # AI가 반환한 답변에서 카테고리 이름을 추출합니다
        # .strip()은 앞뒤 공백을 제거하는 함수입니다
        label = response.strip()

        # 허용된 카테고리 목록 (정확히 이 5가지만 유효합니다)
        valid_categories = {
            "NO_RELATION",
            "BIO_Q",
            "SIMULATION_Q",
            "PROTOCOL_Q",
            "INFERENCE_Q",
        }

        # AI가 반환한 답변이 허용된 카테고리 중 하나인지 확인합니다
        # 만약 정확한 카테고리 이름이면 그대로 반환합니다
        if label in valid_categories:
            return label

        # AI가 예상치 못한 답변을 했을 경우 (오타나 잘못된 형식 등)
        # 안전하게 기본값인 "NO_RELATION"을 반환합니다
        return "NO_RELATION"

    except Exception as e:
        # 오류가 발생했을 때 (예: 인터넷 연결 문제, API 오류 등)
        # 오류 메시지를 출력하고 기본값을 반환합니다
        print(f"[Classifier Error] {e}")
        return "NO_RELATION"


def classify_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    
    # 노드 진입 로그
    print(f"\n{'='*60}")
    print(f"[CLASSIFIER NODE] 시작")
    print(f"  question: {str(state.get('question', ''))[:30]}...")
    print(f"  conversation_id: {state.get('conversation_id', '')}")
    print(f"{'='*60}\n")

    # state 딕셔너리에서 'question' 키의 값을 가져옵니다
    # 만약 값이 없으면 빈 문자열("")을 사용합니다
    # .strip()은 앞뒤 공백을 제거합니다 (예: "  안녕  " → "안녕")
    q = (state.get("question") or "").strip()

    # 질문이 비어있는지 확인합니다 (사용자가 아무것도 입력하지 않았거나 공백만 입력한 경우)
    if not q:
        # 질문이 없으면 기본값으로 "NO_RELATION"을 설정합니다
        state["case_type"] = "NO_RELATION"
        return state  # 결과를 반환하고 함수를 종료합니다

    # 질문이 있으면 AI를 사용해서 질문을 분류합니다
    # _classify_with_llm 함수를 호출하여 카테고리 이름을 받아옵니다
    chat_room_id = state.get("conversation_id")
    user_id = state.get("user_id", "default")
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
    print(f"\n[CLASSIFIER NODE] 종료")
    print(f"  case_type: {state.get('case_type', '')}")
    print(f"  final_answer: {str(state.get('final_answer', ''))[:30]}...")
    print(f"{'='*60}\n")
    
    # 분류 결과가 저장된 state를 반환합니다
    return state
