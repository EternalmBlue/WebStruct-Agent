"""持久化平台能力：引擎、会话、自动迁移、ORM 模型与 JSON 载荷读写。

各功能中心的仓储放在各自中心内，这里只提供与业务无关的基础设施。
"""

from app.platform.persistence.database import (
    Base,
    SessionLocal,
    engine,
    get_db,
    init_storage,
)

__all__ = ["Base", "SessionLocal", "engine", "get_db", "init_storage"]
