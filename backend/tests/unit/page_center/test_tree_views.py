from app.features.page_center.views import extract_text_blocks
from app.platform.dom import parse_html, select_values


def test_text_block_paths_match_nested_and_void_markup():
    source = """<html><body><section><p>One<img src="x"><strong> bold</strong></p>
    <p>Two<br> lines<script>ignored()</script></p></section>
    <section><p>Three</p><ul><li>Outer<p>Nested</p></li></ul></section></body></html>"""
    blocks = extract_text_blocks(source)
    root = parse_html(source)
    assert len(blocks) == 4
    for block in blocks:
        assert select_values(root, "css", block["selector"]) == [block["text"]]
        assert select_values(root, "xpath", block["xpath"]) == [block["text"]]
        assert "ignored" not in block["text"]


def test_empty_html_and_block_limit():
    assert extract_text_blocks("") == []
    assert len(extract_text_blocks("<p>One</p><p>Two</p>", limit=1)) == 1
