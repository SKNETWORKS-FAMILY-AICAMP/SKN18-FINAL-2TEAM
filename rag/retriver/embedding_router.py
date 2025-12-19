# -*- coding: utf-8 -*-
"""
embedding_router.py

3) 임베딩 라우팅(Embedding Routing)
- retrieval_plan을 읽고, step에 필요한 임베딩을 생성해 state["embeddings"]에 저장한다.
- Paper/Clinical: 1536 (OpenAI text-embedding-3-small) -> OpenAI API 사용
- Protocol: 1024 (BAAI/bge-m3) -> Hugging Face Inference API 사용 (API Token 필요)

[수정 사항]
- 로컬 모델 다운로드 방식 제거 -> Hugging Face API 사용 (가볍고 빠름)
- langchain_openai, langchain_huggingface 최신 패키지 사용
- Lazy Loading 적용 (필요할 때만 연결)
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

# [규칙 준수] OpenAI -> langchain_openai, HF API -> langchain_huggingface
from langchain_openai import OpenAIEmbeddings
from langchain_huggingface import HuggingFaceEndpointEmbeddings
from rag_state import PipelineRAGState

class EmbeddingRoutingNode:
    def __init__(
        self,
        embed_main: Optional[OpenAIEmbeddings] = None,
        embed_protocol: Optional[HuggingFaceEndpointEmbeddings] = None,
    ) -> None:
        # 1. Main Embedder (OpenAI API)
        # OpenAIEmbeddings는 초기화 시 자동으로 os.environ["OPENAI_API_KEY"]를 확인합니다.
        self.embed_main = embed_main or OpenAIEmbeddings(
            model=os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
        )

        # 2. Protocol Embedder (Hugging Face API)
        # 초기화 시점에는 연결하지 않고 설정만 저장 (Lazy Loading)
        self._embed_protocol_instance = embed_protocol
        self._protocol_model_name = os.getenv("PROTOCOL_EMBED_MODEL", "BAAI/bge-m3")
        
        # API 사용 시에는 로컬 device(cpu/cuda) 설정이 필요 없습니다.

    def _get_protocol_embedder(self) -> HuggingFaceEndpointEmbeddings:
        """
        Lazy Loader for Hugging Face Inference API.
        최초 호출 시 .env에서 로드된 API 토큰을 사용하여 연결합니다.
        """
        if self._embed_protocol_instance is None:
            # .env에서 로드된 토큰 확인
            api_token = os.getenv("HUGGINGFACEHUB_API_TOKEN")
            if not api_token:
                raise ValueError("❌ HUGGINGFACEHUB_API_TOKEN not found in environment variables. Please check your .env file.")

            print(f"🔄 Connecting to Hugging Face API for model: {self._protocol_model_name}...")
            
            # [API 연결] 로컬 모델 대신 원격 추론 API 사용
            self._embed_protocol_instance = HuggingFaceEndpointEmbeddings(
                model=self._protocol_model_name,
                task="feature-extraction",
                huggingfacehub_api_token=api_token,
            )
        return self._embed_protocol_instance

    def __call__(self, state: PipelineRAGState) -> PipelineRAGState:
        question = (state.get("question") or "").strip()
        plan = state.get("retrieval_plan") or []
        
        if not question or not plan:
            state["embeddings"] = {}
            return state

        # 캐시: 같은 embedder는 한 번만 생성하여 재사용
        emb: Dict[str, Any] = {}
        
        for step in plan:
            embedder = step.get("embedder")
            if not embedder or embedder in emb:
                continue

            # 1536 dim (Paper/Clinical) -> OpenAI API
            if embedder == "main_1536":
                emb[embedder] = self.embed_main.embed_query(question)
            
            # 1024 dim (Protocol) -> Hugging Face API
            elif embedder == "protocol_1024":
                proto_emb = self._get_protocol_embedder()
                emb[embedder] = proto_emb.embed_query(question)
            
            else:
                continue

        state["embeddings"] = emb
        return state