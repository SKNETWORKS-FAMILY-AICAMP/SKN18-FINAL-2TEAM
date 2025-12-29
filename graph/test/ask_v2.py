#!/usr/bin/env python3
"""
ask_v2.py
=============================
graph/compile.py 에서 정의한 LangGraph 워크플로가
실행 환경에서 정상 동작하는지 확인하기 위한 CLI 테스트 스크립트.

사용 방법:
    python ask_v2.py

기능:
    - 그래프 컴파일/로딩 테스트
    - 사용자 질문을 받아 LangGraph 실행
    - 주요 결과 필드 및 RAG 파이프라인 요약 출력
    - 각 질문 실행 결과를 CSV 로 append 저장
"""

import csv
import os
import sys
import traceback
from datetime import datetime
from typing import Any, Dict, List, Tuple

# 루트 경로 설정
BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # .../graph
ROOT_DIR = os.path.dirname(BASE_DIR)                   # 프로젝트 루트

for path in {BASE_DIR, ROOT_DIR}:
    if path not in sys.path:
        sys.path.append(path)

from graph.compile import create_workflow  # noqa: E402


# 실행 로그를 CSV로 기록하기 위한 필드 정의 (RAG 요약 포함)
LOG_HEADER = [
    "timestamp",
    "conversation_id",
    "user_id",
    "question",
    "case_type",
    "final_answer",
    "used_search_db",
    "used_web_search",
    "selected_chunks_count",
    "web_selected_chunks_count",
    "entities",
    "rag_rerank_chunks_preview",
    "chunk_is_relevant",
    "chunk_relevance_score",
    "evaluate_chunks_preview",
    # RAG 파이프라인 관련 요약 정보
    "rag_intent",
    "rag_domains",
    "rag_question_type",
    "rag_need_kg",
    "rag_needs_chunks",
    "rag_plan_summary",
    "rag_contexts_count",
    "rag_primekg_edges_count",
    "error",
]


def print_banner() -> None:
    print("=" * 80)
    print("[GRAPH WORKFLOW TEST]")
    print("=" * 80)
    print("graph/compile.py 의 create_workflow()를 이용해 LangGraph 그래프를 컴파일하고,")
    print("질문을 받아 전체 워크플로가 정상 동작하는지 확인합니다.")
    print("종료하려면 'quit' 또는 'exit' 를 입력하세요.")
    print("=" * 80)


def test_graph_compilation():
    """그래프 컴파일/로딩 여부 확인."""
    print("\n[GRAPH] 워크플로 컴파일/로딩 테스트...")

    try:
        app = create_workflow()
        print("[GRAPH] 그래프 컴파일 성공")
        return app
    except Exception as exc:
        print(f"[GRAPH] 그래프 컴파일 실패: {exc}")
        print(traceback.format_exc())
        return None


def create_test_state(question: str, conversation_id: int = 1) -> dict:
    """초기 BioRAGState 형태의 기본 state."""
    return {
        "question": question,
        "conversation_id": conversation_id,
        "user_id": "test_user",
    }


def _preview_chunks(chunks: List[Any], max_items: int = 3, max_len: int = 120) -> str:
    """청크 리스트에서 앞 N개만 짧게 미리보기 문자열로 변환."""
    if not chunks:
        return ""

    previews: List[str] = []
    for i, ch in enumerate(chunks[:max_items], 1):
        if isinstance(ch, dict):
            text = ch.get("content") or ch.get("text") or str(ch)
        else:
            text = str(ch)
        text = text.replace("\n", " ")
        if len(text) > max_len:
            text = text[: max_len - 3] + "..."
        previews.append(f"[{i}] {text}")
    return " || ".join(previews)


def append_log_row(
    question: str,
    conversation_id: str,
    user_id: str,
    result: Dict[str, Any] | None,
    error: str = "",
) -> Dict[str, Any]:
    """한 번의 실행 결과를 CSV 한 줄(dict)로 구성."""
    ts = datetime.now().isoformat()

    if result is None:
        return {
            "timestamp": ts,
            "conversation_id": conversation_id,
            "user_id": user_id,
            "question": question,
            "case_type": "ERROR",
            "final_answer": "",
            "used_search_db": "",
            "used_web_search": False,
            "selected_chunks_count": 0,
            "web_selected_chunks_count": 0,
            "entities": "",
            "rag_rerank_chunks_preview": "",
            "chunk_is_relevant": None,
            "chunk_relevance_score": None,
            "evaluate_chunks_preview": "",
            "rag_intent": "",
            "rag_domains": "",
            "rag_question_type": "",
            "rag_need_kg": False,
            "rag_needs_chunks": False,
            "rag_plan_summary": "",
            "rag_contexts_count": 0,
            "rag_primekg_edges_count": 0,
            "error": error,
        }

    case_type = result.get("case_type", "UNKNOWN")
    final_answer = result.get("final_answer", "")
    used_web_search = result.get("used_web_search", False)
    selected_chunks = result.get("selected_chunks") or []
    web_selected_chunks = result.get("web_selected_chunks") or []
    entities = result.get("entities") or []
    used_search_db = result.get("used_search_db") or ""

    # rag-rerank 단계에서 선택된 청크들(retrieval_results 가 rerank 적용 결과)
    retrieval_results = result.get("retrieval_results") or []
    rag_rerank_preview = _preview_chunks(retrieval_results)

    # evaluate 단계 결과
    chunk_is_relevant = result.get("chunk_is_relevant")
    chunk_relevance_score = result.get("chunk_relevance_score")
    evaluate_preview = _preview_chunks(selected_chunks)

    # RAG 파이프라인 요약 정보
    rewrite = result.get("rewrite") or {}
    route = result.get("route") or {}
    retrieval_plan = result.get("retrieval_plan") or []
    contexts = result.get("contexts") or []
    primekg_insights = result.get("primekg_insights") or []

    rag_intent = rewrite.get("intent") or route.get("intent") or ""
    rag_domains = rewrite.get("domains") or route.get("domains") or []
    rag_question_type = rewrite.get("question_type") or route.get("question_type") or ""
    rag_need_kg = bool(rewrite.get("need_kg", route.get("need_kg", False)))
    rag_needs_chunks = bool(rewrite.get("needs_chunks", route.get("needs_chunks", True)))

    if retrieval_plan:
        plan_items = [
            f"{step.get('domain')}:{step.get('mode')}"
            for step in retrieval_plan[:5]
        ]
        rag_plan_summary = "|".join(plan_items)
    else:
        rag_plan_summary = ""

    return {
        "timestamp": ts,
        "conversation_id": conversation_id,
        "user_id": user_id,
        "question": question,
        "case_type": case_type,
        "final_answer": final_answer,
        "used_search_db": used_search_db,
        "used_web_search": bool(used_web_search),
        "selected_chunks_count": len(selected_chunks),
        "web_selected_chunks_count": len(web_selected_chunks),
        "entities": "|".join(map(str, entities)),
        "rag_rerank_chunks_preview": rag_rerank_preview,
        "chunk_is_relevant": chunk_is_relevant,
        "chunk_relevance_score": chunk_relevance_score,
        "evaluate_chunks_preview": evaluate_preview,
        "rag_intent": rag_intent,
        "rag_domains": "|".join(map(str, rag_domains)) if isinstance(rag_domains, list) else str(rag_domains),
        "rag_question_type": rag_question_type,
        "rag_need_kg": rag_need_kg,
        "rag_needs_chunks": rag_needs_chunks,
        "rag_plan_summary": rag_plan_summary,
        "rag_contexts_count": len(contexts),
        "rag_primekg_edges_count": len(primekg_insights) if isinstance(primekg_insights, list) else 0,
        "error": error,
    }


def append_row_to_csv(row: Dict[str, Any]) -> None:
    """단일 실행 결과 row 를 CSV 파일에 append."""
    log_dir = os.path.dirname(__file__)
    csv_path = os.path.join(log_dir, "ask_v2_logs_v1.csv")
    file_exists = os.path.exists(csv_path)

    try:
        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=LOG_HEADER)
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)
        print(f"[LOG] 실행 로그를 CSV 에 기록했습니다: {csv_path}")
    except Exception as exc:
        print(f"[LOG] CSV 저장 중 오류 발생: {exc}")


def run_workflow_test(app, question: str) -> Tuple[bool, Dict[str, Any] | None]:
    """워크플로를 실행하고 결과 요약 + CSV 기록."""
    print(f"\n[INPUT] 질문: {question}")
    print("-" * 60)

    initial_state = create_test_state(question)
    conversation_id = initial_state["conversation_id"]
    user_id = initial_state["user_id"]

    try:
        print("[GRAPH] 그래프 실행 중...")
        result = app.invoke(initial_state)

        case_type = result.get("case_type", "UNKNOWN")
        final_answer = result.get("final_answer", "(응답 없음)")
        used_web_search = result.get("used_web_search", False)
        selected_chunks = result.get("selected_chunks") or []
        web_selected_chunks = result.get("web_selected_chunks") or []
        entities = result.get("entities") or []
        used_search_db = result.get("used_search_db")

        rewrite = result.get("rewrite") or {}
        route = result.get("route") or {}
        rag_intent = rewrite.get("intent") or route.get("intent")
        rag_domains = rewrite.get("domains") or route.get("domains")
        rag_question_type = rewrite.get("question_type") or route.get("question_type")

        rag_need_kg = bool(rewrite.get("need_kg", route.get("need_kg", False)))
        rag_needs_chunks = bool(rewrite.get("needs_chunks", route.get("needs_chunks", True)))

        rag_contexts_count = int(result.get("contexts_count", 0))
        primekg_insights = result.get("primekg_insights") or []

        print("\n[RESULT] 실행 결과 요약")
        print(f"  - case_type           : {case_type}")
        print(f"  - final_answer        : {final_answer}")
        if used_search_db:
            print(f"  - 사용 DB             : {used_search_db}")
        print(f"  - 선택된 chunk 개수   : {len(selected_chunks)}")
        print(f"  - web chunk 개수      : {len(web_selected_chunks)}")
        print(f"  - web 검색 사용 여부  : {used_web_search}")
        if entities:
            print(f"  - 추출 엔티티         : {entities}")

        print("  - RAG intent          :", rag_intent)
        print("  - RAG domains         :", rag_domains)
        print("  - RAG question_type   :", rag_question_type)
        print("  - RAG need_kg         :", rag_need_kg)
        print("  - RAG needs_chunks    :", rag_needs_chunks)
        print("  - RAG contexts_count  :", rag_contexts_count)
        print("  - PrimeKG edges       :", len(primekg_insights) if isinstance(primekg_insights, list) else 0)

        row = append_log_row(
            question=question,
            conversation_id=conversation_id,
            user_id=user_id,
            result=result,
        )
        append_row_to_csv(row)

        return True, result

    except Exception as exc:
        print(f"[ERROR] 그래프 실행 중 예외 발생: {exc}")
        print(traceback.format_exc())

        row = append_log_row(
            question=question,
            conversation_id=conversation_id,
            user_id=user_id,
            result=None,
            error=str(exc),
        )
        append_row_to_csv(row)
        return False, None


def main() -> None:
    print_banner()

    # 그래프 컴파일/로딩
    app = test_graph_compilation()
    if app is None:
        print("\n[EXIT] 그래프 컴파일 실패. 테스트를 종료합니다.")
        return

    print("\n[READY] 그래프 준비 완료. 질문을 입력하세요.")

    try:
        while True:
            try:
                print("\n" + "=" * 80)
                user_input = input("질문을 입력하세요 (quit/exit 로 종료): ").strip()

                if user_input.lower() in {"quit", "exit", "q"}:
                    print("\n[EXIT] 테스트를 종료합니다.")
                    break

                if not user_input:
                    print("[WARN] 질문이 비어 있습니다. 다시 입력해주세요.")
                    continue

                success, _ = run_workflow_test(app, user_input)
                if not success:
                    print("[WARN] 실행 중 오류가 발생했습니다. 다시 시도해주세요.")

            except KeyboardInterrupt:
                print("\n\n[EXIT] Ctrl+C 입력으로 종료합니다.")
                break
            except Exception as exc:
                print(f"\n[ERROR] 알 수 없는 예외: {exc}")
                print(traceback.format_exc())
    finally:
        pass


if __name__ == "__main__":
    main()

