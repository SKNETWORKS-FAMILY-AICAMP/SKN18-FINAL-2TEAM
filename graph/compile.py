'''
LangGraph의 StateGraph를 생성하고 노드 간 엣지 정의
(러프한 버전) - 케이스 

'''
# create_workflow에 맞게 파일과 함수 임포트하기
from langgraph.graph import END

# 노드 함수 import
from .state import BioRAGState
from .nodes.memory import memory_read_node, memory_write_node
from .nodes.keyword_extraction import keyword_extract_node
from .nodes.classifier import classifier_node
from .nodes.rewrite_query import rewrite_query_node
from .nodes.retrieval import retrieval_node
from .nodes.evaluate_chunk import evaluate_chunk_node
from .nodes.web_search import web_search_node
from .nodes.evaluate_web import evaluate_web_node
from .nodes.generate_answer import generate_answer_node


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
    graph.add_node("memory_read", memory_read_node)
    graph.add_node("keyword_extract", keyword_extract_node)
    graph.add_node("classify", classifier_node)
    graph.add_node("rewrite_query", rewrite_query_node)

    graph.add_edge("memory_read", "keyword_extract")
    graph.add_edge("keyword_extract", "classify")
    graph.add_edge("classify", "rewrite_query")


    # 2단계: bio_q 로 분류된 경우 RAG → Evaluate → Fallback → Answer
    graph.add_node("retrieval", retrieval_node)
    graph.add_node("evaluate_chunk", evaluate_chunk_node)
    graph.add_node("web_search", web_search_node)
    graph.add_node("evaluate_web", evaluate_web_node)
    graph.add_node("generate_answer", generate_answer_node)
    graph.add_node("memory_write", memory_write_node)


    # case_type 기반 라우팅 
    graph.add_conditional_edges(
        "rewrite_query",
        route_case,
        {
            "bio_q": "retrieval",
            "simulation_q": "generate_answer",
            "protocol_q": "retrieval",
            "inference_q": "generate_answer",
            "no_relation": "generate_answer",
        }
    )


    # retrieval → evaluate_chunk
    graph.add_edge("retrieval", "evaluate_chunk")

    # evaluate_chunk → web fallback or skip_web
    graph.add_conditional_edges(
        "evaluate_chunk",
        route_retrieval_or_web,
        {
            "web_search": "web_search",
            "skip_web": "generate_answer"
        }
    )

    # web_search → evaluate_web → generate_answer
    graph.add_edge("web_search", "evaluate_web")
    graph.add_edge("evaluate_web", "generate_answer")

    # 마지막에 메모리 저장 후 종료
    graph.add_edge("generate_answer", "memory_write")
    graph.add_edge("memory_write", END)

    # Compile
    app = graph.compile()
    return app