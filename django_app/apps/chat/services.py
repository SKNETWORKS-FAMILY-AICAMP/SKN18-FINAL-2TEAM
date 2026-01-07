from __future__ import annotations

import sys
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Sequence
from decimal import Decimal

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
from .models.papers_models import PaperGraph, PaperNode, PaperEdge, ChatMessagePaperGraph

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

    # selected_chunks: evaluate_chunk에서 선별된 청크 (관련성 있는 것만)
    selected_chunks = raw_result.get("selected_chunks") or []
    web_selected_chunks = raw_result.get("web_selected_chunks") or []
    web_results = raw_result.get("web_results") or []  # 웹 검색 원본 결과 (title 포함)

    # case_type을 reference_type으로 사용
    case_type = raw_result.get("case_type") or "NO_RELATION"

    formatted = []

    # ⚠️ 중요: selected_chunks가 비어있으면 참고문헌을 생성하지 않음
    # retrieval_results가 있어도 evaluate_chunk에서 관련성이 없다고 판단되면 selected_chunks가 비어있음
    if not selected_chunks and not web_selected_chunks:
        print(f"[DEBUG _format_citations] selected_chunks와 web_selected_chunks가 모두 비어있음 → citations 생성 안 함")
        return [], case_type

    # retrieval_results에서 메타데이터 추출 (reranked_results 우선)
    if reranked_results and selected_chunks:
        for idx, result in enumerate(reranked_results[:5], 1):  # 상위 5개만
            # RAG 파이프라인에서 반환하는 실제 구조: article.title, journal_title 등
            article = result.get("article") or {}
            metadata = result.get("metadata") or {}
            
            # 🔍 DEBUG: RAG에서 추출된 필드 확인
            title = article.get("title") or metadata.get("title") or f"검색 결과 {idx}"
            journal = result.get("journal_title") or metadata.get("journal") or ""
            year = str(article.get("year") or metadata.get("year") or "")
            doi = article.get("doi") or metadata.get("doi") or ""
            pmid = article.get("pmid") or metadata.get("pmid") or ""
            
            print(f"\n{'='*60}")
            print(f"[DEBUG _format_citations] Citation #{idx} 필드 추출 결과:")
            print(f"  title: {title[:80] if title else 'N/A'}...")
            print(f"  pmid: {pmid or 'N/A'}")
            print(f"  journal_name: {journal or 'N/A'}")
            print(f"  year: {year or 'N/A'}")
            print(f"  doi: {doi or 'N/A'}")
            print(f"  article 구조: {list(article.keys()) if article else 'empty'}")
            print(f"  result.keys: {list(result.keys())}")
            if article:
                print(f"  article 내용: {article}")
            print(f"{'='*60}\n")
            
            # article 구조에서 먼저 찾고, 없으면 metadata에서 찾기 (fallback)
            formatted.append({
                "id": idx,
                "title": title,
                "journal": journal,
                "year": year,
                "doi": doi,
                "pmid": pmid,
                "source_type": metadata.get("source_type") or metadata.get("db") or "",
                "score": result.get("rerank_score") or result.get("score") or 0.0,
            })
    elif retrieval_results and selected_chunks:
        for idx, result in enumerate(retrieval_results[:5], 1):
            # RAG 파이프라인에서 반환하는 실제 구조: article.title, journal_title 등
            article = result.get("article") or {}
            metadata = result.get("metadata") or {}
            
            # 🔍 DEBUG: RAG에서 추출된 필드 확인
            title = article.get("title") or metadata.get("title") or f"검색 결과 {idx}"
            journal = result.get("journal_title") or metadata.get("journal") or ""
            year = str(article.get("year") or metadata.get("year") or "")
            doi = article.get("doi") or metadata.get("doi") or ""
            pmid = article.get("pmid") or metadata.get("pmid") or ""
            
            print(f"\n{'='*60}")
            print(f"[DEBUG _format_citations] Citation #{idx} 필드 추출 결과 (retrieval_results):")
            print(f"  title: {title[:80] if title else 'N/A'}...")
            print(f"  pmid: {pmid or 'N/A'}")
            print(f"  journal_name: {journal or 'N/A'}")
            print(f"  year: {year or 'N/A'}")
            print(f"  doi: {doi or 'N/A'}")
            print(f"  article 구조: {list(article.keys()) if article else 'empty'}")
            print(f"  result.keys: {list(result.keys())}")
            if article:
                print(f"  article 내용: {article}")
            print(f"{'='*60}\n")
            
            # article 구조에서 먼저 찾고, 없으면 metadata에서 찾기 (fallback)
            formatted.append({
                "id": idx,
                "title": title,
                "journal": journal,
                "year": year,
                "doi": doi,
                "pmid": pmid,
                "source_type": metadata.get("source_type") or metadata.get("db") or "",
                "score": result.get("score") or 0.0,
            })

    # answer_sources (웹 검색 URL)도 추가 - web_selected_chunks가 있을 때만
    if web_selected_chunks and web_results:
        # operator.add로 인한 중복 제거 (안전장치)
        unique_chunks = []
        seen_chunks = set()
        for chunk in web_selected_chunks:
            chunk_str = str(chunk) if not isinstance(chunk, str) else chunk
            if chunk_str and chunk_str not in seen_chunks:
                seen_chunks.add(chunk_str)
                unique_chunks.append(chunk_str)
        
        if len(web_selected_chunks) != len(unique_chunks):
            print(f"[DEBUG _format_citations] ⚠️ web_selected_chunks 중복 제거: {len(web_selected_chunks)}개 → {len(unique_chunks)}개")
        
        print(f"[DEBUG _format_citations] web_selected_chunks 처리 중: {len(unique_chunks)}개 (원본: {len(web_selected_chunks)}개)")
        print(f"[DEBUG _format_citations] web_selected_chunks 타입: {type(unique_chunks)}")
        print(f"[DEBUG _format_citations] web_selected_chunks 내용:")
        for i, chunk in enumerate(unique_chunks[:5], 1):  # 최대 5개만 로깅
            print(f"  [{i}] 타입: {type(chunk)}, 값: {str(chunk)[:100]}...")
        
        # "웹자료 N:" 형식에서 인덱스 추출 (중복 제거)
        selected_indices = []
        seen_indices = set()  # 중복 방지용
        for chunk in unique_chunks:
            try:
                # 문자열 형식 체크
                chunk_str = str(chunk) if not isinstance(chunk, str) else chunk
                
                if chunk_str.startswith('웹자료') and ':' in chunk_str:
                    idx_str = chunk_str.split(':')[0].replace('웹자료', '').strip()
                    idx = int(idx_str) - 1  # 0-based index
                    # 중복 인덱스 제거
                    if idx not in seen_indices:
                        selected_indices.append(idx)
                        seen_indices.add(idx)
                        print(f"[DEBUG] 웹자료 인덱스 추출: '{chunk_str[:30]}...' → idx: {idx}")
                    else:
                        print(f"[DEBUG] 중복 인덱스 제거: idx={idx}")
                else:
                    print(f"[DEBUG] 웹자료 형식 아님: '{chunk_str[:30]}...' (startswith 체크 실패 또는 ':' 없음)")
            except Exception as e:
                print(f"[DEBUG] 웹자료 인덱스 추출 실패: chunk={chunk[:30] if isinstance(chunk, str) else str(chunk)[:30]}, error: {e}")
                import traceback
                traceback.print_exc()
                pass

        print(f"[DEBUG] selected_indices (중복 제거 후): {selected_indices}")

        # 선택된 인덱스의 web_results만 references로 추가
        for idx in selected_indices:
            if 0 <= idx < len(web_results):
                web_result = web_results[idx]
                result_title = web_result.get("title", "")
                result_url = web_result.get("url", "")
                result_snippet = web_result.get("snippet", "")

                # 제목이 없으면 URL에서 도메인 추출
                if not result_title and result_url:
                    try:
                        from urllib.parse import urlparse
                        parsed = urlparse(result_url)
                        result_title = parsed.netloc.replace("www.", "")
                    except:
                        result_title = "웹 출처"

                formatted.append({
                    "id": len(formatted) + 1,
                    "title": result_title or f"웹 자료 {idx + 1}",
                    "journal": "",
                    "year": "",
                    "doi": "",
                    "pmid": "",
                    "authors": "",
                    "source_type": "web",
                    "url": result_url,
                    "snippet": result_snippet[:200],  # 200자까지
                    "score": 0.9,  # 웹서치는 evaluate_web에서 이미 관련성 평가 통과 → 높은 관련성
                })
                print(f"[DEBUG] 웹 reference 추가: idx={idx}, title={result_title[:50]}")

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


def generate_ai_response(conversation: Chat, prompt: str, return_state: bool = False, filter_type: str = None) -> tuple:
    """
    LangGraph RAG 워크플로우를 호출하여 답변과 참고문헌 정보를 생성한다.

    Args:
        conversation: Chat 인스턴스
        prompt: 사용자 질문
        return_state: result_state도 반환할지 여부 (논문 네트워크 생성용)
        filter_type: 필터 타입 (paper, clinical, protocol, simulation, interpretation)

    Returns:
        return_state=False: (content, citations, scores, reference_type, chat_title)
        return_state=True: (content, citations, scores, reference_type, chat_title, result_state)
    """

    app = _get_graph_app() # workflow.compile() 결과
    payload = {
        "question": prompt,
        "conversation_id": str(conversation.chat_sid),  # Chat 모델의 PK (문자열로 전달, memory.py에서 정수 변환)
        "user_id": str(conversation.created_id),  # User ID 문자열
    }
    
    # 필터 타입이 있으면 payload에 추가
    if filter_type:
        payload["filter_type"] = filter_type
    result_state = app.invoke(payload) # ⭐ 워크플로우 시작!
    structured = result_state.get("structured_answer") or {}
    content = (
        result_state.get("final_answer")
        or structured.get("answer")
        or "죄송합니다. 답변을 생성하지 못했습니다."
    )
    citations, reference_type = _format_citations(result_state)
    scores = _extract_scores(result_state)

    # chat_title 추출 (LangGraph에서 생성한 채팅방 제목)
    chat_title = result_state.get("chat_title") or ""

    if return_state:
        return content, citations, scores, reference_type, chat_title, result_state
    return content, citations, scores, reference_type, chat_title


def summarize_conversation_title(prompt: str) -> str:
    """
    사용자 첫 메시지를 기반으로 대화 타이틀을 요약한다.
    GPT-4o-mini 사용 (비용 절감)
    """
    from langchain_openai import ChatOpenAI

    # GPT-4o-mini 사용 (저렴한 모델)
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.3,
        max_tokens=20
    )

    system_prompt = SystemMessage(
        content="사용자의 첫 질문을 간결하게 요약하여 12자 이내의 채팅방 제목을 만들어주세요. "
                "핵심 키워드만 사용하고, 구체적이고 명확하게 작성하세요."
    )
    messages = [system_prompt, HumanMessage(content=prompt)]
    response = llm.invoke(messages)
    content = response.content if hasattr(response, "content") else str(response)
    return content.strip()[:50] or "새로운 대화"


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


def extract_pmids_from_rag_result(result_state: Dict[str, Any], max_count: int = 20) -> tuple[List[int], Dict[int, str]]:
    """
    RAG 결과에서 논문 pmid를 추출하고 논문 타입을 분류합니다.
    
    Args:
        result_state: LangGraph state 결과
        max_count: 최대 추출 개수 (기본값: 20)
        
    Returns:
        (pmid 리스트, {pmid: paper_type} 딕셔너리)
        paper_type: 'central' (중심 논문), 'related' (관련 논문), 'derived' (파생 논문)
    """
    pmids = []
    pmid_types = {}  # {pmid: 'central'|'related'|'derived'}
    
    # 1. citations에서 중심 논문 추출 (AI 응답에서 직접 인용된 논문)
    citations_pmids = set()
    selected_chunks = result_state.get("selected_chunks", [])
    web_selected_chunks = result_state.get("web_selected_chunks", [])
    
    for chunk in selected_chunks + web_selected_chunks:
        # chunk가 문자열인 경우 건너뛰기
        if not isinstance(chunk, dict):
            continue
        
        article = chunk.get("article", {})
        if not isinstance(article, dict):
            continue
            
        pmid = article.get("pmid")
        if pmid:
            try:
                pmid_int = int(pmid)
                citations_pmids.add(pmid_int)
                pmid_types[pmid_int] = 'central'
            except (ValueError, TypeError):
                pass
    
    # 2. reranked_results에서 관련 논문 추출 (RAG로 검색된 상위 논문)
    reranked_results = result_state.get("reranked_results", [])
    for result in reranked_results[:max_count]:
        # result가 문자열인 경우 건너뛰기
        if not isinstance(result, dict):
            continue
            
        article = result.get("article", {})
        if not isinstance(article, dict):
            continue
            
        pmid = article.get("pmid")
        if pmid:
            try:
                pmid_int = int(pmid)
                if pmid_int not in citations_pmids:
                    pmids.append(pmid_int)
                    pmid_types[pmid_int] = 'related'
            except (ValueError, TypeError):
                pass
    
    # 3. citations를 중심 논문으로 추가
    pmids = list(citations_pmids) + pmids
    
    # 4. reranked_results가 없거나 부족하면 retrieval_results에서 추출
    if len(pmids) < max_count:
        retrieval_results = result_state.get("retrieval_results", [])
        for result in retrieval_results[:max_count]:
            # result가 문자열인 경우 건너뛰기
            if not isinstance(result, dict):
                continue
                
            article = result.get("article", {})
            if not isinstance(article, dict):
                continue
                
            pmid = article.get("pmid")
            if pmid:
                try:
                    pmid_int = int(pmid)
                    if pmid_int not in pmids:
                        pmids.append(pmid_int)
                        if pmid_int not in pmid_types:
                            pmid_types[pmid_int] = 'related'
                except (ValueError, TypeError):
                    pass
    
    # 5. contexts에서 직접 추출 (fallback)
    if len(pmids) < max_count:
        contexts = result_state.get("contexts", [])
        for context in contexts[:max_count]:
            # context가 문자열인 경우 건너뛰기
            if not isinstance(context, dict):
                continue
                
            article = context.get("article", {})
            if not isinstance(article, dict):
                continue
                
            pmid = article.get("pmid")
            if pmid:
                try:
                    pmid_int = int(pmid)
                    if pmid_int not in pmids:
                        pmids.append(pmid_int)
                        if pmid_int not in pmid_types:
                            pmid_types[pmid_int] = 'related'
                except (ValueError, TypeError):
                    pass
    
    # 중복 제거 및 최대 개수 제한
    unique_pmids = list(set(pmids))[:max_count]
    print(f"[PaperGraph] 추출된 pmid 개수: {len(unique_pmids)}개 (중심: {sum(1 for p in unique_pmids if pmid_types.get(p) == 'central')}개, 관련: {sum(1 for p in unique_pmids if pmid_types.get(p) == 'related')}개)")
    return unique_pmids, pmid_types


def query_neo4j_paper_network(pmids: List[int], pmid_types: Dict[int, str] = None) -> Dict[str, Any]:
    """
    Neo4j에서 논문 네트워크를 조회합니다.
    
    Args:
        pmids: 논문 pmid 리스트
        pmid_types: {pmid: 'central'|'related'|'derived'} 딕셔너리
        
    Returns:
        {
            "nodes": [{"id": pmid, "label": title, "year": year, "paper_type": "central|related|derived", ...}],
            "edges": [[source_pmid, target_pmid], ...]
        }
    """
    if not pmids:
        print("[PaperGraph] pmid가 없어 Neo4j 조회를 건너뜁니다.")
        return {"nodes": [], "edges": []}
    
    if pmid_types is None:
        pmid_types = {}
    
    try:
        from graph.nodes.rag_retriever_bridge import _get_neo4j_driver
        
        driver = _get_neo4j_driver()
        nodes = []
        edges = []
        original_pmids_set = set(pmids)  # 원본 pmid 집합 (파생 논문 구분용)
        
        with driver.session() as session:
            # 1. 논문 노드 조회
            cypher_nodes = """
            MATCH (a:Article)
            WHERE a.pmid IN $pmids
            OPTIONAL MATCH (a)-[:PUBLISHED_IN]->(j:Journal)
            RETURN a.pmid AS pmid,
                   a.title AS title,
                   a.year AS year,
                   a.doi AS doi,
                   j.name AS journal_name
            LIMIT 50
            """
            
            result = session.run(cypher_nodes, pmids=pmids)
            for record in result:
                pmid = record.get("pmid")
                if pmid:
                    pmid_int = int(pmid) if isinstance(pmid, str) else pmid
                    # 논문 타입 결정: pmid_types에 있으면 그대로, 없으면 'related'
                    paper_type = pmid_types.get(pmid_int, 'related')
                    
                    nodes.append({
                        "id": str(pmid),
                        "label": record.get("title") or f"Paper {pmid}",
                        "year": record.get("year") or "",
                        "doi": record.get("doi") or "",
                        "journal": record.get("journal_name") or "",
                        "paper_type": paper_type,
                    })
            
            # 2. 논문 간 인용 관계 조회 (CitedWork를 통한 간접 관계)
            if len(nodes) > 1:
                cypher_edges = """
                MATCH (a1:Article)-[:CITES_WORK]->(cw:CitedWork)<-[:CITES_WORK]-(a2:Article)
                WHERE a1.pmid IN $pmids AND a2.pmid IN $pmids AND a1.pmid <> a2.pmid
                RETURN DISTINCT a1.pmid AS source_pmid, a2.pmid AS target_pmid
                LIMIT 100
                """
                
                result = session.run(cypher_edges, pmids=pmids)
                for record in result:
                    source = record.get("source_pmid")
                    target = record.get("target_pmid")
                    if source and target:
                        edges.append([str(source), str(target)])
            
            # 3. 파생 논문 조회: 원본 논문들이 인용하는 논문들 중 원본에 없는 것
            cypher_derived = """
            MATCH (a1:Article)-[:CITES_WORK]->(cw:CitedWork)<-[:CITES_WORK]-(a2:Article)
            WHERE a1.pmid IN $pmids AND NOT a2.pmid IN $pmids
            WITH DISTINCT a2.pmid AS derived_pmid, COUNT(DISTINCT a1.pmid) AS citation_count
            ORDER BY citation_count DESC
            LIMIT 10
            MATCH (a2:Article {pmid: derived_pmid})
            OPTIONAL MATCH (a2)-[:PUBLISHED_IN]->(j:Journal)
            RETURN a2.pmid AS pmid,
                   a2.title AS title,
                   a2.year AS year,
                   a2.doi AS doi,
                   j.name AS journal_name,
                   citation_count
            """
            
            result = session.run(cypher_derived, pmids=pmids)
            for record in result:
                pmid = record.get("pmid")
                if pmid:
                    pmid_int = int(pmid) if isinstance(pmid, str) else pmid
                    # 파생 논문 추가
                    nodes.append({
                        "id": str(pmid),
                        "label": record.get("title") or f"Paper {pmid}",
                        "year": record.get("year") or "",
                        "doi": record.get("doi") or "",
                        "journal": record.get("journal_name") or "",
                        "paper_type": "derived",
                    })
                    # 파생 논문과 원본 논문 간 엣지 추가
                    # 원본 논문 중 이 파생 논문을 인용하는 것들 찾기
                    for original_pmid in pmids:
                        edges.append([str(original_pmid), str(pmid)])
            
            print(f"[PaperGraph] Neo4j 조회 완료: 노드 {len(nodes)}개 (중심: {sum(1 for n in nodes if n.get('paper_type') == 'central')}개, 관련: {sum(1 for n in nodes if n.get('paper_type') == 'related')}개, 파생: {sum(1 for n in nodes if n.get('paper_type') == 'derived')}개), 엣지 {len(edges)}개")
            
    except Exception as e:
        print(f"[PaperGraph] Neo4j 조회 오류: {e}")
        import traceback
        traceback.print_exc()
        return {"nodes": [], "edges": []}
    
    return {"nodes": nodes, "edges": edges}


def create_paper_graph_from_neo4j(
    message: ChatMessage,
    paper_network: Dict[str, Any],
    graph_title: str = None,
    graph_description: str = None
) -> PaperGraph:
    """
    Neo4j에서 조회한 논문 네트워크를 PaperGraph로 저장합니다.
    
    Args:
        message: ChatMessage 인스턴스
        paper_network: {"nodes": [...], "edges": [...]}
        graph_title: 그래프 제목 (기본값: "관련 논문 네트워크")
        graph_description: 그래프 설명
        
    Returns:
        생성된 PaperGraph 인스턴스
    """
    nodes_data = paper_network.get("nodes", [])
    edges_data = paper_network.get("edges", [])
    
    if not nodes_data:
        print("[PaperGraph] 노드가 없어 그래프를 생성하지 않습니다.")
        return None
    
    try:
        # 1. PaperGraph 생성
        graph = PaperGraph.objects.create(
            graph_title=graph_title or "관련 논문 네트워크",
            graph_description=graph_description or "RAG 결과를 기반으로 조회한 논문 간 인용 관계 네트워크",
            status='E',
            created_id='system',
        )
        
        # 2. PaperNode 생성
        import random
        import math
        
        # 원형 레이아웃으로 노드 위치 계산
        node_count = len(nodes_data)
        radius = 200.0
        center_x = 0.0
        center_y = 0.0
        
        # 논문 타입별로 그룹화하여 배치
        central_nodes = [n for n in nodes_data if n.get("paper_type") == "central"]
        related_nodes = [n for n in nodes_data if n.get("paper_type") == "related"]
        derived_nodes = [n for n in nodes_data if n.get("paper_type") == "derived"]
        
        # 타입별 색상 정의 (더 세련된 색상 팔레트)
        type_colors = {
            "central": "#E63946",  # 빨간색 (중심 논문) - 더 세련된 빨강
            "related": "#457B9D",  # 파란색 (관련 논문) - 더 세련된 파랑
            "derived": "#A8DADC",  # 연한 청록색 (파생 논문) - 더 부드러운 청록
        }
        
        # 타입별 크기 정의
        type_sizes = {
            "central": 35,  # 중심 논문은 크게
            "related": 25,  # 관련 논문은 중간
            "derived": 20,  # 파생 논문은 작게
        }
        
        node_idx = 0
        # 중심 논문을 중심에 배치
        for node_data in central_nodes:
            angle = 2 * math.pi * node_idx / max(node_count, 1)
            x = center_x + radius * 0.3 * math.cos(angle)  # 중심에 가깝게
            y = center_y + radius * 0.3 * math.sin(angle)
            
            paper_type = node_data.get("paper_type", "related")
            PaperNode.objects.create(
                graph=graph,
                paper_id=node_data.get("id", str(node_idx)),
                paper_label=node_data.get("label", f"Paper {node_idx}"),
                node_size=type_sizes.get(paper_type, 25),
                node_color=type_colors.get(paper_type, "#5B8E7E"),
                x_position=Decimal(str(x)),
                y_position=Decimal(str(y)),
                created_id='system',
            )
            node_idx += 1
        
        # 관련 논문을 중간 원에 배치
        for node_data in related_nodes:
            angle = 2 * math.pi * node_idx / max(node_count, 1)
            x = center_x + radius * 0.7 * math.cos(angle)
            y = center_y + radius * 0.7 * math.sin(angle)
            
            paper_type = node_data.get("paper_type", "related")
            PaperNode.objects.create(
                graph=graph,
                paper_id=node_data.get("id", str(node_idx)),
                paper_label=node_data.get("label", f"Paper {node_idx}"),
                node_size=type_sizes.get(paper_type, 25),
                node_color=type_colors.get(paper_type, "#5B8E7E"),
                x_position=Decimal(str(x)),
                y_position=Decimal(str(y)),
                created_id='system',
            )
            node_idx += 1
        
        # 파생 논문을 외곽에 배치
        for node_data in derived_nodes:
            angle = 2 * math.pi * node_idx / max(node_count, 1)
            x = center_x + radius * 1.2 * math.cos(angle)  # 외곽에
            y = center_y + radius * 1.2 * math.sin(angle)
            
            paper_type = node_data.get("paper_type", "derived")
            PaperNode.objects.create(
                graph=graph,
                paper_id=node_data.get("id", str(node_idx)),
                paper_label=node_data.get("label", f"Paper {node_idx}"),
                node_size=type_sizes.get(paper_type, 20),
                node_color=type_colors.get(paper_type, "#95E1D3"),
                x_position=Decimal(str(x)),
                y_position=Decimal(str(y)),
                created_id='system',
            )
            node_idx += 1
        
        # 3. PaperEdge 생성
        for edge_data in edges_data:
            if len(edge_data) >= 2:
                source_id = str(edge_data[0])
                target_id = str(edge_data[1])
                
                # 노드가 존재하는지 확인
                source_exists = PaperNode.objects.filter(graph=graph, paper_id=source_id).exists()
                target_exists = PaperNode.objects.filter(graph=graph, paper_id=target_id).exists()
                
                if source_exists and target_exists:
                    PaperEdge.objects.get_or_create(
                        graph=graph,
                        source_paper_id=source_id,
                        target_paper_id=target_id,
                        defaults={
                            'edge_size': 1,
                            'edge_color': '#CCCCCC',
                        }
                    )
        
        # 4. ChatMessagePaperGraph 연결
        ChatMessagePaperGraph.objects.get_or_create(
            message=message,
            graph=graph,
            defaults={
                'sort_order': 0,
                'created_id': 'system',
            }
        )
        
        print(f"[PaperGraph] 그래프 생성 완료: graph_sid={graph.graph_sid}, 노드 {node_count}개, 엣지 {len(edges_data)}개")
        return graph
        
    except Exception as e:
        print(f"[PaperGraph] 그래프 생성 오류: {e}")
        import traceback
        traceback.print_exc()
        return None


def generate_paper_graph_background(
    message: ChatMessage,
    result_state: Dict[str, Any],
    user_question: str = None
):
    """
    백그라운드에서 논문 네트워크를 생성합니다.
    
    Args:
        message: ChatMessage 인스턴스
        result_state: LangGraph state 결과
        user_question: 사용자 질문 (선택적)
    """
    try:
        print(f"[PaperGraph] 백그라운드 논문 네트워크 생성 시작: message_id={message.message_sid}")
        
        # 1. RAG 결과에서 pmid 추출 및 타입 분류 (최대 20개)
        pmids, pmid_types = extract_pmids_from_rag_result(result_state, max_count=20)
        
        if not pmids:
            print("[PaperGraph] 추출된 pmid가 없어 논문 네트워크를 생성하지 않습니다.")
            return
        
        # 2. Neo4j에서 논문 네트워크 조회 (타입 정보 포함)
        paper_network = query_neo4j_paper_network(pmids, pmid_types)
        
        if not paper_network.get("nodes"):
            print("[PaperGraph] Neo4j에서 조회된 노드가 없습니다.")
            return
        
        # 3. PaperGraph 생성 및 저장
        graph_title = f"관련 논문 네트워크 ({len(pmids)}개 논문)"
        graph_description = user_question or "RAG 결과를 기반으로 조회한 논문 간 인용 관계"
        
        create_paper_graph_from_neo4j(
            message=message,
            paper_network=paper_network,
            graph_title=graph_title,
            graph_description=graph_description
        )
        
        print(f"[PaperGraph] 백그라운드 논문 네트워크 생성 완료: message_id={message.message_sid}")
        
    except Exception as e:
        print(f"[PaperGraph] 백그라운드 논문 네트워크 생성 오류: {e}")
        import traceback
        traceback.print_exc()
