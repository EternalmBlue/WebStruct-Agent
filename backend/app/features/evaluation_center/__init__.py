"""评测中心：数据集加载、基线/本方法运行、指标计算与报告输出。

行为契约：specs/features/evaluation-center.feature
"""

from app.features.evaluation_center.workflow import build_benchmark_graph, run_benchmark_workflow

__all__ = ["build_benchmark_graph", "run_benchmark_workflow"]
