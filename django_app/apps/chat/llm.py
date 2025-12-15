from django.conf import settings
from langchain_openai import ChatOpenAI


def get_llm():
    api_key = getattr(settings, "OPENAI_API_KEY", None)
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY 설정이 필요합니다.")
    return ChatOpenAI(model="gpt-4o-mini", temperature=0.2, api_key=api_key)
