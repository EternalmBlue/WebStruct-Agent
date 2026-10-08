"""阶段 1：泛化单页抽取 Gherkin 契约自检。

这里不实现页面抽取行为，只确认阶段 1 的 feature 文件可解析且覆盖完整的
规范边界。阶段 2 会在同一 feature 上增加真正的行为步骤绑定。
"""

from __future__ import annotations

from pathlib import Path

from pytest_bdd.parser import FeatureParser

from tests.bdd.feature_paths import feature_path


def _feature():
    path = Path(feature_path("generalized-extraction.feature")).resolve()
    return FeatureParser(str(path.parent), path.name).parse()


def test_generalized_extraction_feature_is_parseable_and_has_expected_scenarios():
    feature = _feature()

    assert feature.name == "泛化单资源页抽取"
    assert len(feature.scenarios) == 11

    scenario_names = set(feature.scenarios)
    assert "论坛主页不得作为单资源页抽取" in scenario_names
    assert "分类列表页不得作为单资源页抽取" in scenario_names
    assert "正文摘要不能冒充完整正文" in scenario_names
    assert "结构相同的单资源页允许复用已验证 ProgramSpec" in scenario_names
    assert "结构不兼容时必须拒绝复用并重新生成" in scenario_names
    assert "RSI 记录正文质量和复用结果" in scenario_names


def test_generalized_extraction_feature_uses_observable_contract_terms():
    path = Path(feature_path("generalized-extraction.feature")).resolve()
    text = path.read_text(encoding="utf-8")

    for term in (
        "page_intent_mismatch",
        "schema_generation_mode=inferred",
        "正文覆盖率",
        "noise_ratio",
        "compatible",
        "复用被拒绝并记录具体原因",
        "measured、estimated 或 unavailable",
    ):
        assert term in text


def test_generalized_extraction_spec_does_not_introduce_site_specific_rules():
    text = Path("specs/generalized-single-page-extraction.md").read_text(encoding="utf-8")

    assert "MineBBS、MCMod、Wikipedia、萌娘百科只是验证样本" in text
    assert "规范不得" in text
    assert "站点专用 selector" in text
    assert "不做验证码破解、挑战识别、代理轮换、登录绕过或反爬绕过" in text
