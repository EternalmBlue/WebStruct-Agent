from app.features.page_center.single_page import (
    assess_page_intent,
    select_body_content,
)


def test_single_resource_page_has_detail_intent():
    html = """
    <html><body>
      <nav>Home Resources Search</nav>
      <main>
        <h1>Example Resource</h1>
        <div class="meta"><span class="author">Alice</span><time>2026-10-09</time></div>
        <article>
          <p>第一段正文，介绍资源的用途和适用范围。</p>
          <p>第二段正文，提供配置说明与使用步骤。</p>
        </article>
      </main>
      <aside>Recommended</aside>
    </body></html>
    """

    assessment = assess_page_intent(html, requested_intent="single_resource")

    assert assessment.intent in {"single_resource", "article"}
    assert assessment.confidence > 0.5
    assert "unique_primary_heading" in assessment.signals


def test_home_and_list_pages_do_not_pass_single_resource_gate():
    home = """
    <html><body>
      <nav>Home Forum Login</nav>
      <main><h1>Forum Home</h1>
        <ul>
          <li><a href="/a">Resource A</a></li>
          <li><a href="/b">Resource B</a></li>
          <li><a href="/c">Resource C</a></li>
        </ul>
      </main>
    </body></html>
    """
    listing = """
    <html><body><main><h1>Resources</h1>
      <section class="card"><h2>A</h2><p>Summary A</p></section>
      <section class="card"><h2>B</h2><p>Summary B</p></section>
      <section class="card"><h2>C</h2><p>Summary C</p></section>
    </main></body></html>
    """

    home_assessment = assess_page_intent(home, requested_intent="single_resource")
    list_assessment = assess_page_intent(listing, requested_intent="single_resource")

    assert home_assessment.intent in {"home", "list"}
    assert list_assessment.intent == "list"
    assert home_assessment.gate_passed is False
    assert list_assessment.gate_passed is False
    assert "page_intent_mismatch" in home_assessment.reasons
    assert "page_intent_mismatch" in list_assessment.reasons


def test_body_selection_rejects_summary_when_longer_content_exists():
    html = """
    <html><body><main>
      <div class="summary">短简介，只是首段摘要。</div>
      <article class="content">
        <p>完整正文第一段，包含安装和配置说明。</p>
        <p>完整正文第二段，包含命令和注意事项。</p>
        <p>完整正文第三段，包含故障排查内容。</p>
      </article>
    </main></body></html>
    """

    selection = select_body_content(html)

    assert selection.accepted
    assert "完整正文第一段" in selection.text
    assert "完整正文第三段" in selection.text
    assert selection.metrics.visible_text_coverage > 0.5
    assert selection.rejected_reasons == []


def test_body_selection_merges_adjacent_regions_and_excludes_noise():
    html = """
    <html><body>
      <nav>导航菜单和登录入口</nav>
      <main>
        <div class="content"><p>正文上半部分。</p></div>
        <div class="content"><p>正文下半部分。</p></div>
      </main>
      <aside>推荐资源和广告</aside><footer>版权信息</footer>
    </body></html>
    """

    selection = select_body_content(html)

    assert selection.accepted
    assert selection.metrics.merged_candidate_count >= 2
    assert "正文上半部分" in selection.text
    assert "正文下半部分" in selection.text
    assert "推荐资源" not in selection.text
    assert selection.metrics.noise_ratio < 0.35


def test_long_form_article_keeps_clean_text_when_template_noise_is_embedded():
    html = """
    <html><body><main><article class="content">
      <div class="notice">请先阅读编辑提示和免责声明。</div>
      <div class="infobox">人物信息和统计表格</div>
      <p>正文第一段，介绍条目的定义和背景。</p>
      <p>正文第二段，说明发展历史与主要应用。</p>
      <div class="toc">目录 序言 参考文献</div>
      <p>正文第三段，补充争议与未来方向。</p>
    </article></main></body></html>
    """

    selection = select_body_content(html)

    assert selection.accepted
    assert "正文第一段" in selection.text
    assert "正文第三段" in selection.text
    assert "免责声明" not in selection.text
    assert selection.metrics.noise_ratio > 0
