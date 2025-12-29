# -*- coding: utf-8 -*-
"""
embedding_router.py

Embedding Routing
- retrieval_plan 을 보고, 필요한 embedder 에 대해 질문을 임베딩해서
  state["embeddings"] 에 저장한다.
- Paper/Clinical: 1536 (OpenAI text-embedding-3-small) -> OpenAI API
- Protocol: 1024 (BAAI/bge-m3) -> Hugging Face Inference API

요구사항:
- protocol HY search 를 수행할 때만 main_1536 + protocol_1024 두 개 임베딩을 모두 계산한다.
- 그 외에는 plan 에서 실제로 필요한 embedder 만 계산한다.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

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
        self.embed_main = embed_main or OpenAIEmbeddings(
            model=os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
        )

        # 2. Protocol Embedder (Hugging Face API, Lazy Loading)
        self._embed_protocol_instance = embed_protocol
        self._protocol_model_name = os.getenv("PROTOCOL_EMBED_MODEL", "BAAI/bge-m3")

    def _get_protocol_embedder(self) -> HuggingFaceEndpointEmbeddings:
        """
        Lazy Loader for Hugging Face Inference API.
        최초 호출 시 .env 에서 토큰을 읽어 인스턴스를 생성한다.
        """
        if self._embed_protocol_instance is None:
            api_token = os.getenv("HUGGINGFACEHUB_API_TOKEN")
            if not api_token:
                raise ValueError(
                    "HUGGINGFACEHUB_API_TOKEN not found in environment variables. "
                    "Please check your .env file."
                )

            print(f"[EmbeddingRouter] Connecting to Hugging Face API: {self._protocol_model_name}")
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

        emb: Dict[str, Any] = {}

        # 1) protocol HY/VEC 스텝이 포함된 경우:
        #    -> main_1536 + protocol_1024 두 개 임베딩을 모두 계산
        has_protocol_hy = any(
            (step.get("domain") == "protocol") and (step.get("mode") in ("HY", "VEC"))
            for step in plan
        )

        if has_protocol_hy:
            # Paper/Clinical 용 기본 임베딩
            emb["main_1536"] = self.embed_main.embed_query(question)

            # Protocol 전용 임베딩 (HF API)
            proto_emb = self._get_protocol_embedder()
            emb["protocol_1024"] = proto_emb.embed_query(question)

        else:
            # 2) 그 외의 경우: plan 에서 실제로 필요한 embedder 만 계산
            for step in plan:
                embedder = step.get("embedder")
                if not embedder or embedder in emb:
                    continue

                if embedder == "main_1536":
                    emb[embedder] = self.embed_main.embed_query(question)
                elif embedder == "protocol_1024":
                    proto_emb = self._get_protocol_embedder()
                    emb[embedder] = proto_emb.embed_query(question)

        state["embeddings"] = emb
        return state

