'''
사용자의 질문과 메모리 내용을 참고해,
1) 정확한 실체 이름(단백질명, 유전자명, 기법명 등)은 entities로,
2) 검색 강화를 위해 필요한 요약된 주제 표현은 keywords로
각각 구분하여 출력하라.

출력 예:
{
  "keywords": [...],
  "entities": [...]
}

다음의 예시를 참고하야 출력하라. 

    입력:
    "KaiC 단백질의 phosphorylation 상태를 측정하는 실험 다시 설명해줘"

    LLM 분류 결과:
    entities: ["KaiC", "phosphorylation"]
    keywords: [
        "KaiC protein phosphorylation assay",
        "phosphorylation state measurement",
        "experiment description"
    ]
'''

from typing import Dict, Any
import json
from graph.nodes.call_llm import gpt4o_mini


def keyword_extract_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    사용자 질문과 메모리 내용을 참고하여 키워드와 엔티티를 추출합니다.
    
    입력 (Input):
        - state["question"]: 사용자 질문
        - state.get("memory_slot"): 메모리 슬롯 내용 (선택적)
    
    출력 (Output):
        - state["extracted_keywords"]: 검색 강화를 위한 키워드 리스트
        - state["extracted_entities"]: 정확한 실체 이름 리스트 (단백질명, 유전자명, 기법명 등)
    
    작동 방식:
        1. 사용자 질문과 메모리 내용을 가져옵니다
        2. GPT-4o-mini를 사용하여 키워드와 엔티티를 추출합니다
        3. 결과를 파싱하여 state에 저장합니다
    """
    
    # state에서 사용자 질문을 가져옵니다
    question = state.get("question", "")
    
    # 메모리 슬롯 내용이 있으면 함께 사용합니다 (선택적)
    memory_slot = state.get("memory_slot", {})
    memory_context = ""
    if memory_slot:
        topic = memory_slot.get("topic", "")
        last_case = memory_slot.get("last_case", "")
        if topic or last_case:
            memory_context = f"이전 주제: {topic}, 이전 케이스: {last_case}"
    
    # 질문이 없으면 빈 결과를 반환합니다
    if not question:
        state["extracted_keywords"] = []
        state["extracted_entities"] = []
        return state
    
    # 프롬프트를 구성합니다
    # 사용자 질문과 메모리 내용을 포함하여 키워드와 엔티티를 추출하도록 지시합니다
    prompt = f"""사용자의 질문과 메모리 내용을 참고하여 키워드와 엔티티를 추출하세요.

규칙:
1) 정확한 실체 이름(단백질명, 유전자명, 기법명 등)은 entities로 분류
2) 검색 강화를 위해 필요한 요약된 주제 표현은 keywords로 분류

출력 형식은 반드시 JSON 형식으로:
{{
  "keywords": [...],
  "entities": [...]
}}

예시:
입력: "KaiC 단백질의 phosphorylation 상태를 측정하는 실험 다시 설명해줘"
출력:
{{
  "entities": ["KaiC", "phosphorylation"],
  "keywords": [
    "KaiC protein phosphorylation assay",
    "phosphorylation state measurement",
    "experiment description"
  ]
}}

사용자 질문: {question}
"""
    
    # 메모리 내용이 있으면 프롬프트에 추가합니다
    if memory_context:
        prompt += f"\n메모리 내용: {memory_context}\n"
    
    try:
        # GPT-4o-mini를 사용하여 키워드와 엔티티를 추출합니다
        # 플로우차트에 따르면 Keyword Extraction은 GPT-4o-mini를 사용합니다
        response = gpt4o_mini(prompt)
        
        # JSON 형식으로 파싱을 시도합니다
        try:
            # JSON 형식으로 파싱
            result = json.loads(response)
            keywords = result.get("keywords", [])
            entities = result.get("entities", [])
        except json.JSONDecodeError:
            # JSON 파싱 실패 시, 응답에서 직접 추출을 시도합니다
            # 또는 기본값을 사용합니다
            print(f"[Keyword Extraction Warning] JSON 파싱 실패: {response}")
            keywords = []
            entities = []
        
        # 결과를 state에 저장하고 반환합니다
        state["extracted_keywords"] = keywords
        state["extracted_entities"] = entities
        
        print(f"[KeywordExtract] keywords: {keywords}, entities: {entities}")
        return state
        
    except Exception as e:
        # 오류 발생 시 빈 결과를 반환합니다
        print(f"[Keyword Extraction Error] {e}")
        state["extracted_keywords"] = []
        state["extracted_entities"] = []
        return state