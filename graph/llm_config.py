"""
llm_config.py
--------------------
각 노드의 함수별 LLM 모델을 중앙에서 관리하는 설정 파일

사용 예:
    from graph.llm_config import classifier_classify_question_node_llm
    response = classifier_classify_question_node_llm(prompt)

네이밍 규칙:
    {파일명}_{함수명}_llm
"""

from graph.nodes.call_llm import gpt4_1_nano, gpt4o_mini, gpt5_nano, sllm


# ===== guardrail.py =====
guardrail_check_safety_llm = gpt4_1_nano


# ===== classifier.py =====
classifier_is_bio_related_simple_check_llm = gpt4_1_nano
classifier_classify_question_node_llm = gpt4_1_nano
generate_answer_info_llm = gpt4_1_nano

# ===== memory.py =====
memory_summarize_tool_llm = gpt4_1_nano


# ===== keyword_extraction.py =====
keyword_extraction_node_llm = gpt4_1_nano


# ===== rewrite_query.py =====
rewrite_query_normalizer_tool_llm = gpt4_1_nano
rewrite_query_expander_tool_llm = gpt4_1_nano
rewrite_query_simplifier_tool_llm = gpt4_1_nano
rewrite_query_node_llm = gpt4_1_nano


# ===== retrieval.py =====
retrieval_decide_search_strategy_llm = gpt4_1_nano


# ===== evaluate_web.py =====
evaluate_web_node_llm = gpt4_1_nano


# ===== evaluate_chunk.py =====
evaluate_chunk_bio_node_llm = gpt4_1_nano
evaluate_chunk_protocol_node_llm = gpt4_1_nano


# ===== generate_answer.py =====
generate_answer_bio_llm = gpt4_1_nano
generate_answer_simulation_llm = gpt4_1_nano
generate_answer_protocol_llm = gpt4_1_nano
generate_answer_protocol_fallback_llm = gpt4_1_nano
generate_answer_inference_llm = gpt4_1_nano
generate_answer_inference_fallback_llm = gpt4_1_nano

