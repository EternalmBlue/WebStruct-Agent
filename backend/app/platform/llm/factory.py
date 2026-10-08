"""模型适配器工厂：按凭据是否可用选择具体实现。"""

from app.platform.llm.openai_compatible import OpenAICompatibleModelAdapter
from app.platform.llm.protocol import ModelAdapter
from app.platform.llm.unconfigured import UnconfiguredModelAdapter


def create_model_adapter(
    *,
    api_key: str | None,
    base_url: str,
    model: str,
    timeout_seconds: float,
) -> ModelAdapter:
    if not api_key:
        return UnconfiguredModelAdapter()
    return OpenAICompatibleModelAdapter(
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout_seconds=timeout_seconds,
    )
