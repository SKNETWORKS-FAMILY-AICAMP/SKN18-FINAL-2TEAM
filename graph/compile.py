'''
LangGraph의 StateGraph를 생성하고 노드 간 엣지 정의
(러프한 버전) - 케이스 

'''
# create_workflow에 맞게 파일과 함수 임포트하기
from langgraph.graph import END, StateGraph

# 노드 함수 import
from graph.state import BioRAGState
from graph.nodes.memory import memory_read_node, memory_write_node
from graph.nodes.classifier import classify_agent_node
from graph.nodes.rewrite_query import query_rewrite_agent_node
from graph.nodes.retrieval import retriever_protocol_node, retriever_bio_node
from graph.nodes.rerank import rerank_node
from graph.nodes.evaluate_chunk import bio_evaluate_chunk_node, protocol_evaluate_chunk_node
from graph.nodes.web_search import web_search_node
from graph.nodes.evaluate_web import evaluate_web_node
from graph.nodes.generate_answer import generate_answer_node


# ============================================
# 🔹  Routing Logic (Main Flow)
# ============================================

def route_case(state: BioRAGState):
    return state["case_type"]


def route_retrieval_or_web(state: BioRAGState):
    if not state["retrieval_results"]:
        return "web_search"
    if state["chunk_is_relevant"] is False:
        return "web_search"
    return "skip_web"


# ============================================
# 🔹  Build Graph
# ============================================
def create_workflow(): 
    graph = StateGraph(BioRAGState)

    # 1단계: 공통 전처리
    graph.add_node("classify_agent", classify_agent_node)
    graph.add_node("memory_read", memory_read_node)
    graph.add_node("query_rewrite_agent", query_rewrite_agent_node)

    # 시작점 설정
    graph.set_entry_point("classify_agent")

    # classify에서 조건부 분기 추가
    graph.add_conditional_edges(
        "classify_agent",
        route_case,
        {
            "NO_RELATION": END,  # 바로 종료 (메모리 저장 안함)
            "BIO_Q": "memory_read",
            "SIMULATION_Q": "generate_answer",  # 일관성을 위해 memory_read로 변경
            "PROTOCOL_Q": "memory_read",
            "INFERENCE_Q": "generate_answer",
        }
    )
    
    graph.add_edge("memory_read", "query_rewrite_agent")


    # 2단계: bio_q 로 분류된 경우 RAG → Evaluate → Fallback → Answer
    graph.add_node("retriever_bio_node", retriever_bio_node)
    graph.add_node("retriever_protocol_node", retriever_protocol_node)
    graph.add_node("rerank", rerank_node)
    graph.add_node("bio_evaluate_chunk_node", bio_evaluate_chunk_node)
    graph.add_node("protocol_evaluate_chunk_node", protocol_evaluate_chunk_node)
    graph.add_node("web_search", web_search_node)
    graph.add_node("evaluate_web", evaluate_web_node)
    graph.add_node("generate_answer", generate_answer_node)
    graph.add_node("memory_write", memory_write_node)


    # case_type 기반 라우팅 (query_rewrite_agent 이후)
    graph.add_conditional_edges(
        "query_rewrite_agent",
        route_case,
        {
            "BIO_Q": "retriever_bio_node",
            "PROTOCOL_Q": "retriever_protocol_node",
        }
    )


    # retrieval → rerank → case별 evaluate
    graph.add_edge("retriever_bio_node", "rerank")
    graph.add_edge("retriever_protocol_node", "rerank")
    
    # rerank → case_type에 따라 적절한 evaluate 노드로 분기
    graph.add_conditional_edges(
        "rerank",
        route_case,
        {
            "BIO_Q": "bio_evaluate_chunk_node",
            "PROTOCOL_Q": "protocol_evaluate_chunk_node",
        }
    )

    # BIO_Q: evaluate_chunk → web fallback or skip_web
    graph.add_conditional_edges(
        "bio_evaluate_chunk_node",
        route_retrieval_or_web,
        {
            "web_search": "web_search",
            "skip_web": "generate_answer"
        }
    )

    # PROTOCOL_Q: evaluate_chunk → generate_answer (web fallback 없음)
    graph.add_edge("protocol_evaluate_chunk_node", "generate_answer")

    # web_search → evaluate_web → generate_answer
    graph.add_edge("web_search", "evaluate_web")
    graph.add_edge("evaluate_web", "generate_answer")

    # 마지막에 메모리 저장 후 종료
    graph.add_edge("generate_answer", "memory_write")
    graph.add_edge("memory_write", END)
    
    # Compile
    app = graph.compile()
    return app