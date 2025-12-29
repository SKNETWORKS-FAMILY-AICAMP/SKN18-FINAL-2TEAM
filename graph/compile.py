"""
Graph workflow 정의 모듈.
LangGraph의 StateGraph를 사용해 전체 BioRAG 파이프라인을 구성한다.
"""

from langgraph.graph import END, StateGraph

from graph.state_origin import BioRAGState
from graph.nodes.guardrail import guardrail_input_node
from graph.nodes.memory import memory_read_node, memory_write_node
from graph.nodes.classifier import classify_agent_node
from graph.nodes.rewrite_query import query_rewrite_agent_node
from graph.nodes.retriver import retriever_protocol_node, retriever_bio_node
from graph.nodes.evaluate_chunk import (
    bio_evaluate_chunk_node,
    protocol_evaluate_chunk_node,
)
from graph.nodes.web_search import web_search_node
from graph.nodes.evaluate_web import evaluate_web_node
from graph.nodes.generate_answer import generate_answer_node


# ============================================
# Routing Logic (Main Flow)
# ============================================

def route_guardrail(state: BioRAGState) -> str:
    """guardrail 통과 여부에 따라 blocked / continue 분기."""
    if not state.get("guardrail_passed", True):
        return "blocked"
    return "continue"


def route_case(state: BioRAGState) -> str:
    return state["case_type"]


def route_retrieval_or_web(state: BioRAGState) -> str:
    """retrieval 결과가 없거나 chunk가 relevant 가 아니면 web_search로 분기."""
    if not state["retrieval_results"]:
        return "web_search"
    if state.get("chunk_is_relevant") is False:
        return "web_search"
    return "skip_web"


def route_after_evaluate_web(state: BioRAGState) -> str:
    """
    evaluate_web 이후 should_skip_generation 플래그에 따라
    memory_write 로 바로 갈지(generate 생략) 여부를 결정.
    """
    should_skip = state.get("should_skip_generation", False)
    print(f"\n[ROUTE] route_after_evaluate_web 호출")
    print(f"[ROUTE] should_skip_generation: {should_skip}")

    if should_skip:
        print("[ROUTE] GENERATE_ANSWER 건너뛰고 MEMORY_WRITE로 이동")
        return "skip_generation"

    print("[ROUTE] GENERATE_ANSWER로 이동")
    return "generate_answer"


# ============================================
# Build Graph
# ============================================

def create_workflow():
    graph = StateGraph(BioRAGState)

    # 0단계: 입력 guardrail
    graph.add_node("guardrail_input", guardrail_input_node)

    # 1단계: 공통 처리 (분류, 메모리, 쿼리 리라이트)
    graph.add_node("classify_agent", classify_agent_node)
    graph.add_node("memory_read", memory_read_node)
    graph.add_node("query_rewrite_agent", query_rewrite_agent_node)

    # 2단계: BIO / PROTOCOL RAG 검색 및 평가
    graph.add_node("retriever_bio_node", retriever_bio_node)
    graph.add_node("retriever_protocol_node", retriever_protocol_node)
    graph.add_node("bio_evaluate_chunk_node", bio_evaluate_chunk_node)
    graph.add_node("protocol_evaluate_chunk_node", protocol_evaluate_chunk_node)

    # 웹 검색 및 답변 생성/저장
    graph.add_node("web_search", web_search_node)
    graph.add_node("evaluate_web", evaluate_web_node)
    graph.add_node("generate_answer", generate_answer_node)
    graph.add_node("memory_write", memory_write_node)

    # 진입점 설정
    graph.set_entry_point("guardrail_input")

    # Guardrail 결과에 따른 분기
    graph.add_conditional_edges(
        "guardrail_input",
        route_guardrail,
        {
            "blocked": END,
            "continue": "classify_agent",
        },
    )

    # 분류 결과에 따른 1차 라우팅
    graph.add_conditional_edges(
        "classify_agent",
        route_case,
        {
            "NO_RELATION": END,
            "USER_INFO": "memory_read",
            "BIO_Q": "memory_read",
            "SIMULATION_Q": "generate_answer",
            "PROTOCOL_Q": "memory_read",
            "INFERENCE_Q": "generate_answer",
        },
    )

    # memory_read 이후 USER_INFO는 곧바로 generate_answer,
    # BIO_Q / PROTOCOL_Q 는 query_rewrite_agent 로 이동
    graph.add_conditional_edges(
        "memory_read",
        route_case,
        {
            "USER_INFO": "generate_answer",
            "BIO_Q": "query_rewrite_agent",
            "PROTOCOL_Q": "query_rewrite_agent",
        },
    )

    # query_rewrite_agent 이후 case_type 에 따라 적절한 retriever 선택
    graph.add_conditional_edges(
        "query_rewrite_agent",
        route_case,
        {
            "BIO_Q": "retriever_bio_node",
            "PROTOCOL_Q": "retriever_protocol_node",
        },
    )

    # Retrieval 이후 바로 Evaluate 단계로 연결
    graph.add_edge("retriever_bio_node", "bio_evaluate_chunk_node")
    graph.add_edge("retriever_protocol_node", "protocol_evaluate_chunk_node")

    # BIO_Q: evaluate_chunk 결과에 따라 web fallback 또는 generate_answer
    graph.add_conditional_edges(
        "bio_evaluate_chunk_node",
        route_retrieval_or_web,
        {
            "web_search": "web_search",
            "skip_web": "generate_answer",
        },
    )

    # PROTOCOL_Q: evaluate_chunk 후 바로 generate_answer (web fallback 없음)
    graph.add_edge("protocol_evaluate_chunk_node", "generate_answer")

    # web_search 후 evaluate_web, 그 결과에 따라 generate_answer 또는 memory_write
    graph.add_edge("web_search", "evaluate_web")
    graph.add_conditional_edges(
        "evaluate_web",
        route_after_evaluate_web,
        {
            "generate_answer": "generate_answer",
            "skip_generation": "memory_write",
        },
    )

    # 마지막으로 메모리 저장 후 종료
    graph.add_edge("generate_answer", "memory_write")
    graph.add_edge("memory_write", END)

    # Compile
    app = graph.compile()
    return app

