from __future__ import annotations

import sys
import json
from pathlib import Path
from typing import Any, Dict, List, Sequence

# Django 앱(django_app)보다 한 단계 위에 있는 프로젝트 루트를 파이썬 경로에 추가
# graph 모듈을 import하기 전에 프로젝트 루트를 sys.path에 추가해야 함
# services.py -> chat -> apps -> django_app -> PROJECT_ROOT (parents[3])
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from graph.compile import create_workflow

try:
    from django.conf import settings
except ImportError:  # pragma: no cover - django 미설치 환경
    settings = None

from .llm import get_llm
from .models import Chat, ChatMessage

# try:
#     from graph.compile import create_medical_rag_workflow
# except ImportError as exc:  # pragma: no cover - 환경에 따라 graph 패키지가 없을 수 있음
#     create_medical_rag_workflow = None
#     _GRAPH_IMPORT_ERROR = exc
# else:
#     _GRAPH_IMPORT_ERROR = None

_graph_app: Any | None = None


def _get_graph_app():
    """
    LangGraph 워크플로우를 지연 로딩하여 재사용
    """
    global _graph_app
    if create_workflow is None:
        raise RuntimeError("LangGraph 모듈을 불러올 수 없습니다.")
    if _graph_app is None:
        _graph_app = create_workflow()
    return _graph_app


def _format_citations(raw_result: Dict[str, Any]) -> tuple[List[Dict[str, Any]], str]:
    """
    LangGraph state에서 전달된 reference 정보를 프론트엔드가 기대하는 포맷으로 변환.

    목적: LangGraph의 실제 state 필드(answer_sources, retrieval_results, reranked_results)에서
          참고문헌 정보를 추출하여 ChatReference 모델에 저장할 수 있는 형식으로 변환

    수정: 이전에는 존재하지 않는 필드(structured_answer.references, sources)를
          찾고 있어 citations가 빈 배열로 반환되던 문제를 해결
    """
    # answer_sources: 웹 검색 URL이나 출처 리스트
    answer_sources = raw_result.get("answer_sources") or []

    # retrieval_results: RAG 검색 결과 (metadata 포함)
    retrieval_results = raw_result.get("retrieval_results") or []
    reranked_results = raw_result.get("reranked_results") or []

    # case_type을 reference_type으로 사용
    case_type = raw_result.get("case_type") or "NO_RELATION"

    formatted = []

    # retrieval_results에서 메타데이터 추출 (reranked_results 우선)
    if reranked_results:
        for idx, result in enumerate(reranked_results[:5], 1):  # 상위 5개만
            metadata = result.get("metadata") or {}
            formatted.append({
                "id": idx,
                "title": metadata.get("title") or f"검색 결과 {idx}",
                "journal": metadata.get("journal") or "",
                "year": str(metadata.get("year") or ""),
                "month": metadata.get("month") or "",  # 추가: 월 정보
                "day": metadata.get("day") or "",      # 추가: 일 정보
                "doi": metadata.get("doi") or "",
                "pmid": metadata.get("pmid") or "",
                "authors": metadata.get("authors") or "",
                "source_type": metadata.get("source_type") or metadata.get("db") or "",
                "score": result.get("rerank_score") or result.get("score") or 0.0,
            })
    elif retrieval_results:
        for idx, result in enumerate(retrieval_results[:5], 1):
            metadata = result.get("metadata") or {}
            formatted.append({
                "id": idx,
                "title": metadata.get("title") or f"검색 결과 {idx}",
                "journal": metadata.get("journal") or "",
                "year": str(metadata.get("year") or ""),
                "month": metadata.get("month") or "",  # 추가: 월 정보
                "day": metadata.get("day") or "",      # 추가: 일 정보
                "doi": metadata.get("doi") or "",
                "pmid": metadata.get("pmid") or "",
                "authors": metadata.get("authors") or "",
                "source_type": metadata.get("source_type") or metadata.get("db") or "",
                "score": result.get("score") or 0.0,
            })

    # answer_sources (웹 검색 URL)도 추가
    for idx, source in enumerate(answer_sources, len(formatted) + 1):
        if isinstance(source, str):
            formatted.append({
                "id": idx,
                "title": f"웹 출처 {idx - len(formatted)}",
                "journal": "",
                "year": "",
                "doi": "",
                "pmid": "",
                "authors": "",
                "source_type": "web",
                "url": source,
            })

    return formatted, case_type


def _extract_scores(raw_result: Dict[str, Any]) -> Dict[str, Any]:
    """LangGraph state/structured_answer에서 점수를 추출."""
    structured = raw_result.get("structured_answer") or {}

    def _first(*values):
        for value in values:
            if value is not None:
                return value
        return None

    return {
        "llm_score": _first(structured.get("llm_score"), raw_result.get("llm_score")),
        "relevance_score": _first(
            structured.get("relevance_score"), raw_result.get("relevance_score")
        ),
    }


def _build_history(conversation: Chat) -> list:
    """기존 대화 메시지를 LangChain 메시지 포맷으로 변환."""
    messages = []
    for msg in conversation.messages.order_by("created_at").only("role", "content"):
        if msg.role == "U":  # User
            messages.append(HumanMessage(content=msg.content))
        elif msg.role == "A":  # Assistant
            messages.append(AIMessage(content=msg.content))
    return messages


def generate_ai_response(conversation: Chat, prompt: str) -> tuple[str, list, dict, str]:
    """
    LangGraph RAG 워크플로우를 호출하여 답변과 참고문헌 정보를 생성한다.
    """

    app = _get_graph_app() # workflow.compile() 결과
    payload = {
        "question": prompt,
        "conversation_id": str(conversation.chat_sid),  # 수정: conversation.id → conversation.chat_sid (Chat 모델의 실제 PK)
        "user_id": str(conversation.created_id),  # 수정: conversation.user.id → conversation.created_id (Chat 모델에는 user FK가 없음)
    }
    result_state = app.invoke(payload) # ⭐ 워크플로우 시작!
    structured = result_state.get("structured_answer") or {}
    content = (
        result_state.get("final_answer")
        or structured.get("answer")
        or "죄송합니다. 답변을 생성하지 못했습니다."
    )
    citations, reference_type = _format_citations(result_state)
    scores = _extract_scores(result_state)
    return content, citations, scores, reference_type


def summarize_conversation_title(prompt: str) -> str:
    """
    사용자 첫 메시지를 기반으로 대화 타이틀을 요약한다.
    """
    llm = get_llm()
    system_prompt = SystemMessage(
        content="사용자 메시지를 최대 12자 내에서 요약하여 제목을 만들어 주세요. 구체적이고 간결하게."
    )
    messages = [system_prompt, HumanMessage(content=prompt)]
    response = llm.invoke(messages)
    content = response.content if hasattr(response, "content") else str(response)
    return content.strip()[:120] or "새로운 대화"


def generate_concept_graph(message: ChatMessage) -> str:
    """
    주어진 AI 응답 메시지를 기반으로 Mermaid 그래프 코드를 생성한다.
    """
    print(f"[DEBUG] generate_concept_graph() 시작")
    print(f"[DEBUG] 메시지 내용 길이: {len(message.content) if message.content else 0}")
    print(f"[DEBUG] 메시지 내용 미리보기: {message.content[:100] if message.content else 'None'}...")
    
    try:
        llm = get_llm()
        print(f"[DEBUG] LLM 초기화 완료")
        
        system_prompt = SystemMessage(
            content=(
                # "너는 Mermaid graph 전문가다. "
                # "사용자 메시지를 분석해 핵심 개념 간 관계를 flowchart로 표현해라. "
                # "항상 ``` 없이 순수한 Mermaid 코드만 반환하고, graph LR 형식을 사용한다."
                "너는 Mermaid graph 전문가이며, 복잡한 정보를 명확하게 시각화하는 역할을 수행한다. "
                "아래 AI 응답 내용을 기반으로 핵심 개념과 그들의 인과/연관 관계를 분석해, 간단 명료한 flowchart를 만들어라. "
                "꼭 'graph LR'로 시작하되, 한눈에 흐름이 보이도록 최대한 직관적으로 작성한다. "
                "각 노드는 주요 개념(명사, 주제어 등)만 사용하고, 의미 없는 부연 설명이나 장황한 문장은 노드로 만들지 않는다. "
                "모든 엣지는 실제로 언급된 '원인→결과', '주제→속성' 식의 관계만 나타내라. "
                "반드시 ``` 없이 순수 Mermaid 코드만 반환한다. 설명, 주석, 텍스트 없이 결과만 답한다."
            )
        )
        user_prompt = HumanMessage(
            content=(
                "다음 AI 응답을 기반으로 주요 개념/원인의 흐름을 Mermaid flowchart로 만들어줘.\n\n"
                f"AI 응답:\n{message.content}"
            )
        )
        print(f"[DEBUG] LLM 호출 시작...")
        response = llm.invoke([system_prompt, user_prompt])
        print(f"[DEBUG] LLM 호출 완료")
        
        graph_code = response.content if hasattr(response, "content") else str(response)
        print(f"[DEBUG] 생성된 그래프 코드 길이: {len(graph_code) if graph_code else 0}")
        print(f"[DEBUG] 생성된 그래프 코드 미리보기: {graph_code[:200] if graph_code else 'None'}...")
        
        result = graph_code.strip()
        print(f"[DEBUG] generate_concept_graph() 완료, 반환 길이: {len(result)}")
        return result
    except Exception as e:
        print(f"[ERROR] generate_concept_graph() 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        raise


def _clean_question_text(text: str) -> str:
    """
    Remove wrapping 기호/따옴표 등을 정리하고 의미 없는 토큰은 빈 문자열로 반환.
    """
    if text is None:
        return ""
    cleaned = str(text).strip()
    if not cleaned:
        return ""
    # remove trailing commas/brackets commonly returned by code blocks
    cleaned = cleaned.strip(",")
    cleaned = cleaned.strip()

    if cleaned.startswith("["):
        cleaned = cleaned.lstrip("[ ")
    if cleaned.endswith("]"):
        cleaned = cleaned.rstrip("] ")

    def _strip_matching_quotes(value: str) -> str:
        while len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'", "`"}:
            value = value[1:-1].strip()
        return value

    cleaned = _strip_matching_quotes(cleaned)
    cleaned = cleaned.strip()

    junk_tokens = {"", "[", "]", "[,", ",]", "json", "```json", "```", "`json", "`"}
    if cleaned.lower() in junk_tokens:
        return ""
    if cleaned.startswith("```") or cleaned.endswith("```"):
        return ""
    return cleaned


def _normalize_questions(raw: str) -> List[str]:
    """
    LLM 응답 문자열을 안전하게 파싱하여 질문 리스트로 변환.
    """
    questions: List[str] = []
    cleaned = (raw or "").strip()
    if not cleaned:
        return questions

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        data = None

    if isinstance(data, dict):
        # {"questions": [...]} 또는 {"items": [...]} 형태 지원
        for key in ("questions", "items", "data"):
            if key in data and isinstance(data[key], Sequence):
                data = data[key]
                break

    if isinstance(data, Sequence) and not isinstance(data, (str, bytes)):
        for item in data:
            if isinstance(item, str):
                text = item.strip()
            elif isinstance(item, dict):
                text = (
                    item.get("question")
                    or item.get("text")
                    or item.get("value")
                    or ""
                )
                text = text.strip()
            else:
                text = str(item).strip()
            cleaned_text = _clean_question_text(text)
            if cleaned_text:
                questions.append(cleaned_text)
        if questions:
            return _dedupe_limit(questions)

    # JSON 파싱 실패 시 라인 나누기 방식
    for line in cleaned.replace("\r", "\n").split("\n"):
        candidate = line.strip()
        if not candidate:
            continue
        # "- 1. 질문" 형태 정규화
        candidate = candidate.lstrip("-*•0123456789.) ").strip()
        candidate = _clean_question_text(candidate)
        if candidate:
            questions.append(candidate)
        if len(questions) >= 6:
            break
    return _dedupe_limit(questions)


def _dedupe_limit(items: List[str], limit: int = 3) -> List[str]:
    seen = set()
    result: List[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
        if len(result) >= limit:
            break
    return result


def generate_related_questions(message: ChatMessage) -> List[str]:
    """
    AI 응답 메시지를 기반으로 MemorySaver에 도움이 되는 연관 질문을 생성.
    """
    llm = get_llm()
    system_prompt = SystemMessage(
        content=(
            "너는 의료 연구 대화를 이어가는 연관 질문 전문가다. "
            "주어진 AI 응답 내용을 이해하고, MemorySaver 노드가 맥락을 축적할 수 있도록 "
            "핵심 정보(질병, 연구대상, 한계점, 다음 단계)를 구체적으로 참조한 한국어 질문 3개를 만들어라. "
            "임상시험, 치료법, 근거 데이터 등 답변에 언급된 세부 사항을 활용하라. "
            "반드시 JSON 배열 문자열만 출력하고, 각 항목은 짧고 행동지향적인 하나의 질문 문장이어야 한다."
        )
    )
    user_prompt = HumanMessage(
        content=(
            "다음 AI 응답을 참고하여 연관 질문 3개를 만들어 주세요. "
            "각 질문은 서로 다른 시각을 제공하고, 후속 대화에서 기억 관리가 쉬운 형태여야 합니다.\n\n"
            f"AI 응답:\n{message.content}"
        )
    )
    response = llm.invoke([system_prompt, user_prompt])
    raw_content = response.content if hasattr(response, "content") else str(response)
    questions = _normalize_questions(raw_content)
    return questions[:3]
