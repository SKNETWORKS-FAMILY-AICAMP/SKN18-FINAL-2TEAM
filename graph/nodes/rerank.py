"""
rerank.py
-------------------------------------
Cross-Encoder 기반 재순위화 노드

Cross-Encoder란 질문(query)과 문서(document)를 한 번에 모델에 집어넣고,
두 텍스트의 관련성을 직접 계산하는 모델
Query 임베딩, Document 임베딩 -> 이 두 개를 교차(cross) 시켜서 상호작용을 직접 계산
즉, 모델 내부 Attention이:[ Query 토큰 ↔ Document 토큰 ] 이렇게 서로를 직접 참조하면서 의미를 계산

📌 사용 중인 모델 (변경 시 아래 상수 수정):
    - Cross-Encoder: cross-encoder/ms-marco-MiniLM-L-6-v2 (가볍고 빠름)

    [다른 옵션]
    - cross-encoder/ms-marco-TinyBERT-L-2-v2 (더 빠름, 성능 약간 낮음)
    - cross-encoder/ms-marco-electra-base (더 정확함, 느림)
    - cross-encoder/ms-marco-MiniLM-L-12-v2 (가장 정확함, 가장 느림)

📁 모델 저장 위치 (환경에 따라 자동 선택):
    - 로컬 개발: graph/models/ (프로젝트 내부)
    - AWS EC2: /app/models
    - 환경 변수 MODELS_DIR로 명시적 지정 가능
"""

import os
from typing import Dict, Any, List

import huggingface_hub

# Compatibility shim for newer huggingface_hub versions missing cached_download
if not hasattr(huggingface_hub, "cached_download"):
    from huggingface_hub import hf_hub_download

    def cached_download(*args, **kwargs):
        return hf_hub_download(*args, **kwargs)

    huggingface_hub.cached_download = cached_download

from sentence_transformers import CrossEncoder

# 모델 저장 경로 설정 (환경에 따라 자동 선택)
def _get_models_dir():
    """
    환경에 따라 모델 저장 경로 결정
    - 환경 변수 MODELS_DIR이 있으면 우선 사용
    - /app 경로가 존재하면 EC2 환경으로 판단하여 /app/models 사용
    - 그 외에는 로컬 개발 환경으로 graph/models 사용
    """
    # 환경 변수로 명시적으로 지정된 경우
    env_models_dir = os.getenv("MODELS_DIR")
    if env_models_dir:
        return env_models_dir
    
    # EC2 환경 감지: /app 디렉토리 존재 여부 확인
    if os.path.exists("/app"):
        models_dir = "/app/models"
    else:
        # 로컬 개발 환경: 프로젝트 내부 graph/models 폴더
        models_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")
    
    return models_dir

MODELS_DIR = _get_models_dir()
os.makedirs(MODELS_DIR, exist_ok=True)
os.environ["SENTENCE_TRANSFORMERS_HOME"] = MODELS_DIR
os.environ["HF_HOME"] = MODELS_DIR
# Hugging Face 모델 다운로드 타임아웃 설정 (3분)
os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] = "180"


# ============================================
# 🔹 모델 설정 (변경 시 여기만 수정)
# ============================================
CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
# 위 모델 선택지:
# - "cross-encoder/ms-marco-TinyBERT-L-2-v2": 더 빠름
# - "cross-encoder/ms-marco-MiniLM-L-6-v2": 균형 (현재 사용)
# - "cross-encoder/ms-marco-electra-base": 더 정확함
# - "cross-encoder/ms-marco-MiniLM-L-12-v2": 가장 정확함


# Cross-Encoder 모델 로드 (전역 변수로 캐싱)
_cross_encoder_model = None


def get_cross_encoder_model():
    """
    Cross-Encoder 모델 로드 (한번만 로드되도록 캐싱)
    모델은 환경에 따라 자동으로 선택된 경로에 저장됩니다.
    - 로컬 개발: graph/models/
    - AWS EC2: /app/models
    """
    global _cross_encoder_model

    if _cross_encoder_model is None:
        try:
            print(f"[CrossEncoder] 모델 로딩 중: {CROSS_ENCODER_MODEL}")
            print(f"[CrossEncoder] 저장 경로: {MODELS_DIR}")
            print(f"[CrossEncoder] 환경: {'EC2' if os.path.exists('/app') else '로컬 개발'}")
            _cross_encoder_model = CrossEncoder(CROSS_ENCODER_MODEL, cache_folder=MODELS_DIR)
            print(f"[CrossEncoder] {CROSS_ENCODER_MODEL} 모델 로드 완료")
        except Exception as e:
            print(f"[CrossEncoder] 모델 로드 실패: {e}")
            _cross_encoder_model = None

    return _cross_encoder_model


def rerank_with_cross_encoder(query: str, documents: List[Dict[str, Any]], top_k: int = 10) -> List[Dict[str, Any]]:
    """
    Cross-Encoder를 사용하여 문서 재순위화
    
    Args:
        query: 검색 쿼리
        documents: 검색 결과 문서 리스트
        top_k: 상위 K개 반환
        
    Returns:
        재순위화된 문서 리스트
    """
    model = get_cross_encoder_model()
    
    if model is None or not documents:
        print("[CrossEncoder] 모델 없음 또는 문서 없음, 원본 반환")
        return documents[:top_k]
    
    try:
        # Query-Document 쌍 생성
        pairs = []
        for doc in documents:
            if isinstance(doc, dict):
                content = doc.get("content", str(doc))
            else:
                content = str(doc)
            pairs.append([query, content])
        
        # Cross-Encoder로 점수 계산
        print(f"[CrossEncoder] {len(pairs)}개 문서 재점수화 중...")
        scores = model.predict(pairs)
        
        # 점수를 문서에 추가
        reranked = []
        for i, (doc, score) in enumerate(zip(documents, scores)):
            reranked_doc = {**doc} if isinstance(doc, dict) else {"content": str(doc)}
            reranked_doc["rerank_score"] = float(score)
            reranked_doc["original_rank"] = i + 1
            reranked.append(reranked_doc)
        
        # 점수 기준 정렬
        reranked.sort(key=lambda x: x["rerank_score"], reverse=True)
        
        # 상위 K개 선택
        top_results = reranked[:top_k]
        
        print(f"[CrossEncoder] 재순위화 완료: 상위 {len(top_results)}개 선택")
        print(f"[CrossEncoder] 최고 점수: {top_results[0]['rerank_score']:.4f}" if top_results else "")
        
        return top_results
        
    except Exception as e:
        print(f"[CrossEncoder] 오류 발생: {e}")
        return documents[:top_k]


def rerank_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Cross-Encoder 기반 재순위화 노드
    retriever_bio_node()의 결과를 받아 재순위화
    
    매개변수:
        state: BioRAGState
        - retrieval_results: 검색 노드에서 가져온 문서 리스트
        - question: 사용자 원본 질문
        - rewritten_query: 재작성된 쿼리 (우선 사용)
    
    반환값:
        state 업데이트:
        - reranked_results: 상위 N개 재순위화된 문서
        - retrieval_score: 최고 재순위화 점수
    """
    
    # 노드 진입 로그
    print(f"\n{'='*60}")
    print(f"[RERANK NODE] 시작")
    print(f"  question: {str(state.get('question', ''))[:30]}...")
    print(f"  retrieval_results: {len(state.get('retrieval_results', []))}개")
    print(f"{'='*60}\n")
    
    retrieval_results = state.get("retrieval_results", [])
    query = state.get("rewritten_query", state.get("question", ""))
    
    # 검색 결과가 없는 경우
    if not retrieval_results:
        print("[Rerank] 재순위화할 결과가 없습니다.")
        state["reranked_results"] = []
        state["retrieval_score"] = 0.0
        
        print(f"\n[RERANK NODE] 종료 (결과 없음)")
        print(f"{'='*60}\n")
        return state
    
    # Cross-Encoder로 재순위화
    print(f"[Rerank] Cross-Encoder 재순위화 시작 - {len(retrieval_results)}개 문서")
    reranked_results = rerank_with_cross_encoder(
        query=query,
        documents=retrieval_results,
        top_k=10  # 상위 10개만 선택
    )
    
    # 최고 점수 추출
    best_score = reranked_results[0]["rerank_score"] if reranked_results else 0.0
    
    # 상태 업데이트
    state["reranked_results"] = reranked_results
    state["retrieval_score"] = best_score
    
    # 노드 종료 로그
    print(f"\n[RERANK NODE] 종료")
    print(f"  reranked_results: {len(reranked_results)}개")
    print(f"  retrieval_score: {best_score:.4f}")
    print(f"{'='*60}\n")
    
    return state
