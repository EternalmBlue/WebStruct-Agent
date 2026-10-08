"""Shared tree-based CSS/XPath selection and bounded model-facing page context."""
from copy import deepcopy

from lxml import etree, html

from app.platform.text_processing import normalize_whitespace


def parse_html(source: str):
    parser = html.HTMLParser(no_network=True)
    root = html.fromstring(source or "<html></html>", parser=parser)
    for element in root.xpath("//script|//style|//noscript|//template"):
        element.drop_tree()
    return root


def element_text(element) -> str:
    if not isinstance(getattr(element, "tag", None), str):
        return ""
    return normalize_whitespace(" ".join(element.itertext()))


def select_values(root, strategy: str, selector: str, attribute: str | None = None):
    matches = root.cssselect(selector) if strategy == "css" else root.xpath(selector)
    if not isinstance(matches, list):
        raise ValueError("XPath must select nodes, text or attributes, not compute a scalar")
    values = []
    for match in matches:
        if isinstance(match, etree._Element):
            value = match.get(attribute) if attribute else element_text(match)
        elif isinstance(match, str) and not attribute:
            value = match
        else:
            raise ValueError("selector must return elements or text")
        values.append(normalize_whitespace(value or ""))
    return values


def page_context(source: str, *, limit: int = 16000):
    """Remove boilerplate; surface semantic and explicit nodes before truncation."""
    root = parse_html(source)
    candidates = []
    used = set()
    for element in root.xpath("//*[@id or @class]"):
        tag = element.tag
        if tag in {"html", "body", "head", "nav", "footer", "header"}:
            continue
        if any(a.tag in {"nav", "footer", "header", "head"} for a in element.iterancestors()):
            continue
        text = element_text(element)
        if not text:
            continue
        identifier = element.get("id")
        classes = (element.get("class") or "").split()
        selector = f"{tag}#{identifier}" if identifier else f"{tag}.{'.'.join(classes[:2])}"
        if selector in used:
            continue
        try:
            values = select_values(root, "css", selector)
        except Exception:
            continue
        used.add(selector)
        candidates.append({"selector": selector, "match_count": len(values),
                           "text_sample": text[:240]})
    candidates.sort(key=lambda c: (
        not any(w in c["selector"].lower() for w in (
            "title", "headline", "author", "version", "content", "article", "body", "description")),
        c["match_count"] != 1,
        len(c["text_sample"]),
    ))
    copy = deepcopy(root)
    for e in copy.xpath("//head|//nav|//header|//footer"):
        if e.getparent() is not None:
            e.drop_tree()
    focus = copy.xpath("//main|//article|//*[@role='main']")
    selected = focus[0] if focus else copy
    return {
        "html_excerpt": html.tostring(selected, encoding="unicode")[:limit],
        "selector_candidates": candidates[:45],
    }
