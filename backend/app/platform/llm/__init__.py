"""LLM 平台能力：统一的 ModelAdapter 抽象与其实现。

对外只需要 `create_model_adapter`，工作流无需关心具体厂商实现。
"""

from app.platform.llm.factory import create_model_adapter
from app.platform.llm.openai_compatible import OpenAICompatibleModelAdapter
from app.platform.llm.protocol import (
    MissingModelConfigurationError,
    ModelAdapter,
    ModelProviderError,
)
from app.platform.llm.unconfigured import UnconfiguredModelAdapter

__all__ = [
    "MissingModelConfigurationError",
    "ModelAdapter",
    "ModelProviderError",
    "OpenAICompatibleModelAdapter",
    "UnconfiguredModelAdapter",
    "create_model_adapter",
]
