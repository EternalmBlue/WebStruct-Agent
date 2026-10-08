"""通用 JSON 载荷读写。

各功能中心的仓储都在做同一件事：拿一个业务键 upsert 一条记录、把契约对象序列化成 JSON、
再按业务键把 JSON 读回来。这里把这部分重复模式收敛为一处，
具体业务字段仍由各功能中心的仓储自己维护。
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy.orm import Session

from app.platform.persistence.database import SessionLocal, init_storage


def dump_payload(payload: Any) -> str:
    """把任意可 JSON 化的载荷序列化为统一格式的 JSON 字符串。"""
    return json.dumps(payload, ensure_ascii=False)


def load_payload(raw: str) -> dict[str, Any]:
    """把数据库中的 JSON 列读回字典。"""
    value = json.loads(raw)
    return value if isinstance(value, dict) else {}


@contextmanager
def session_scope() -> Iterator[Session]:
    """开启一个业务会话：自动初始化库表、提交事务、失败回滚。"""
    init_storage()
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
