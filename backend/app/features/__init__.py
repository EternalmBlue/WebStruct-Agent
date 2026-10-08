"""功能中心注册中心（Feature Center Registry）。

每个「功能中心」都是自治模块：自带 API 路由、领域服务、LangGraph 节点/工作流与仓储，
并在 `specs/features/<center>.feature` 中拥有一份行为契约。

新增能力时的顺序：先改 spec → 再补行为测试 → 最后实现并在本文件注册。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import APIRouter, FastAPI

SPECS_DIR = "specs/features"


@dataclass(frozen=True)
class FeatureCenter:
    """一个功能中心的元数据。"""

    key: str
    title: str
    spec_file: str
    router_loader: Callable[[], APIRouter] | None = None
    note: str = ""

    @property
    def spec_path(self) -> str:
        return f"{SPECS_DIR}/{self.spec_file}"


def _load(kind: str, module: str) -> Callable[[], APIRouter]:
    def loader() -> APIRouter:
        import importlib

        return getattr(importlib.import_module(f"app.features.{kind}.{module}"), "router")

    return loader


FEATURE_CENTERS: tuple[FeatureCenter, ...] = (
    FeatureCenter(
        key="ops_center",
        title="运行保障中心",
        spec_file="ops-center.feature",
        router_loader=_load("ops_center", "router"),
        note="健康检查与节点追踪，对应 platform/tracing 的执行器",
    ),
    FeatureCenter(
        key="schema_center",
        title="模式中心",
        spec_file="schema-center.feature",
        router_loader=_load("schema_center", "router"),
        note="用户或模型生成的 Schema、校验与版本留存",
    ),
    FeatureCenter(
        key="page_center",
        title="页面采集与多视图中心",
        spec_file="page-center.feature",
        note="页面采集、HTML→文本、多视图归一化（由抽取编排中心调用）",
    ),
    FeatureCenter(
        key="program_center",
        title="ProgramSpec 中心",
        spec_file="program-center.feature",
        router_loader=_load("program_center", "router"),
        note="确定性程序生成、LLM 候选净化、用户验证程序的复用",
    ),
    FeatureCenter(
        key="extraction_center",
        title="抽取编排中心",
        spec_file="extraction-center.feature",
        router_loader=_load("extraction_center", "router"),
        note="LangGraph 主链路：九节点抽取工作流",
    ),
    FeatureCenter(
        key="evaluation_center",
        title="评测中心",
        spec_file="evaluation-center.feature",
        router_loader=_load("evaluation_center", "router"),
        note="五种方法对比评测与指标报告",
    ),
    FeatureCenter(
        key="review_center",
        title="人工复核中心",
        spec_file="review-center.feature",
        router_loader=_load("review_center", "router"),
        note="人工复核回写与已验证程序的登记",
    ),
    FeatureCenter(
        key="spec_assistant_center",
        title="对话式规格助手",
        spec_file="spec-assistant-center.feature",
        router_loader=_load("spec_assistant_center", "router"),
        note="用自然语言修订 Schema 与 ProgramSpec",
    ),
)


def feature_centers() -> tuple[FeatureCenter, ...]:
    """返回全部功能中心元数据。"""
    return FEATURE_CENTERS


def feature_routers() -> list[APIRouter]:
    """返回全部对外 APIRouter（按中心声明顺序）。"""
    routers: list[APIRouter] = []
    for center in FEATURE_CENTERS:
        if center.router_loader is not None:
            routers.append(center.router_loader())
    return routers


def register_feature_routers(app: FastAPI, *, prefix: str = "/api") -> None:
    """把所有功能中心的路由挂载到 FastAPI 应用。"""
    for router in feature_routers():
        app.include_router(router, prefix=prefix)


__all__ = [
    "FEATURE_CENTERS",
    "FeatureCenter",
    "feature_centers",
    "feature_routers",
    "register_feature_routers",
]
