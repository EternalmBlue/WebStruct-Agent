import pytest
from app.features.page_center.classification import classify_page
from app.platform.text_processing import html_to_text


@pytest.mark.parametrize("html, expected", [
    ("<article><h1>WAF documentation</h1><pre>SafeLineChallenge()</pre></article>", "usable_content"),
    ('<article>Discuss cf-chl- and challenges.cloudflare.com/turnstile</article>', "usable_content"),
    ("<div id='slg-box'>Access Forbidden</div><script>SafeLineChallenge()</script>", "usable_content"),
    ("<title>Just a moment</title><p>Verifying</p>", "usable_content"),
    ("<script>document.write('example')</script><style>body { color:red }</style>", "empty_page"),
])
def test_classification_distinguishes_markup_from_article_examples(html, expected):
    text, _, _ = html_to_text(html)
    classification, _ = classify_page(html, text, 200)
    assert classification == expected
