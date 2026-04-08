"""
API модуль для LM Agent.

Модуль предоставляет клиент для взаимодействия с LLM API,
включая поддержку LM Studio и других OpenAI-совместимых серверов.
"""

from lm_agent.api.lmstudio import LMStudioClient
from lm_agent.api.models import ModelList, ModelInfo

__all__ = [
    'LMStudioClient',
    'ModelList',
    'ModelInfo',
]
