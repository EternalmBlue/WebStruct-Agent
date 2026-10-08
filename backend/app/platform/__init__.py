"""跨功能中心复用的技术平台能力。

- config：运行时配置与模型凭据
- persistence：数据库引擎、自动迁移、ORM 模型
- llm：模型适配器（协议 / 未配置 / OpenAI 兼容 / 工厂）
- tracing：LangGraph 节点追踪执行器
- text_processing：文本归一化与证据片段处理
"""

__all__ = ["config", "llm", "persistence", "text_processing", "tracing"]
