"""行为测试：绑定 specs/features/page-center.feature"""

from __future__ import annotations

from types import SimpleNamespace

from app.features.page_center.collector import collect_page
from app.features.page_center.views import normalize_page_view
from pytest_bdd import given, scenarios, then, when

from tests.bdd.feature_paths import feature_path
from tests.support.samples import NOTICE_HTML

scenarios(feature_path("page-center.feature"))


@given("一段包含标题与发布日期的高校通知 HTML")
def given_notice_html(context):
    context["html"] = NOTICE_HTML


@when("页面采集中心采集该 HTML")
def collect_supplied_html(context):
    context["observation"] = collect_page(
        target_url="https://example.edu/notice/001",
        input_html=context["html"],
    )


@then("产出包含最终 URL 与原始 HTML 的页面观测")
def expect_observation(context):
    observation = context["observation"]
    assert observation.url
    assert "2026年大学生创新训练项目申报" in observation.html


@then("页面观测没有采集错误")
def expect_no_collection_error(context):
    assert context["observation"].metadata.get("errors", []) == []


@when("页面采集中心归一化该页面观测")
def normalize_observation(context):
    context["view_bundle"] = normalize_page_view(context["observation"])


@then("视图包包含纯文本视图")
def expect_text_view(context):
    bundle = context["view_bundle"]
    assert len(bundle.lines) >= 1
    assert "发布单位" in bundle.text


@then("视图包包含文本块视图")
def expect_blocks_view(context):
    assert context["view_bundle"].metadata["text_block_count"] >= 1


@then("视图包保留标题与行级别视图")
def expect_line_and_heading_views(context):
    bundle = context["view_bundle"]
    assert bundle.headings
    assert bundle.metadata["line_count"] == len(bundle.lines)


@given("配置允许 CloakBrowser 自动下载且 binary 尚未准备")
def allow_browser_auto_download(context, monkeypatch, tmp_path):
    from app.platform.browser import CloakBrowserAdapter
    from app.platform.config import settings

    monkeypatch.setattr(settings, "browser_auto_download", True)
    monkeypatch.setattr(settings, "browser_executable_path", "")
    monkeypatch.setattr(settings, "browser_cache_path", str(tmp_path))
    context["download_calls"] = []
    binary_path = (
        tmp_path
        / f"chromium-{settings.browser_binary_version}"
        / "chrome.exe"
    )

    class FakePage:
        def wait_for_timeout(self, milliseconds):
            assert milliseconds == settings.browser_post_navigation_wait_ms

        def on(self, *_args):
            pass

        def goto(self, _url, timeout=None):
            return SimpleNamespace(status=200)

        def content(self):
            return NOTICE_HTML

    class FakeBrowser:
        def new_page(self):
            return FakePage()

        def close(self):
            return None

    class FakeCloakBrowser:
        __version__ = settings.browser_sdk_version

        @staticmethod
        def ensure_binary(**kwargs):
            context["download_calls"].append(kwargs)
            binary_path.parent.mkdir(parents=True, exist_ok=True)
            binary_path.write_bytes(b"fake-binary")
            return str(binary_path)

        @staticmethod
        def launch(**_kwargs):
            return FakeBrowser()

    monkeypatch.setattr(
        "app.platform.browser.importlib.import_module",
        lambda _name: FakeCloakBrowser,
    )
    context["browser_adapter"] = CloakBrowserAdapter()
    monkeypatch.setattr(
        "app.features.page_center.collector.adapter",
        context["browser_adapter"],
    )
    context["binary_path"] = binary_path


@when("页面采集中心采集一个需要渲染的目标 URL")
def collect_url_with_auto_download(context):
    context["observation"] = collect_page(
        target_url="https://example.edu/auto-download",
    )


@then("系统先下载 config.toml 指定的 CloakBrowser binary")
def expect_binary_download(context):
    assert len(context["download_calls"]) == 1
    assert context["binary_path"].is_file()


@then("后续启动使用已下载的固定版本")
def expect_downloaded_binary_used(context):
    assert context["observation"].metadata["collector"] == "cloakbrowser_rendered"
    assert context["browser_adapter"].binary_path() == context["binary_path"].resolve()


@then("不自动升级到其他版本")
def expect_pinned_download(context):
    assert context["download_calls"][0]["browser_version"]


@then("每个文本块都带有 CSS 选择器或 XPath")
def expect_block_locators(context):
    blocks = context["view_bundle"].metadata["text_blocks"]
    assert blocks
    for block in blocks:
        assert block.get("selector") or block.get("xpath")


@given("一个渲染后没有可见文本的目标 URL")
def given_blank_rendered_url(context, monkeypatch):
    monkeypatch.setattr(
        "app.features.page_center.collector.fetch_rendered_html",
        lambda _url: ("<html><body></body></html>", 200),
    )
    monkeypatch.setattr(
        "app.features.page_center.collector.fetch_html",
        lambda _url: ("<html><body></body></html>", 200),
    )


@when("页面采集中心采集该 URL")
def collect_remote_url(context):
    try:
        collect_page(target_url="https://example.edu/empty/not-found")
    except Exception as exc:  # 采集失败必须显式抛出，不能返回空观测
        context["error"] = exc
    else:  # pragma: no cover - 正常情况下不会走到这里
        context["error"] = None


@then("采集过程抛出异常")
def expect_collection_error(context):
    assert context["error"] is not None


@then("异常信息中包含可见文本不足的提示")
def expect_empty_page_message(context):
    assert "visible text" in str(context["error"])
