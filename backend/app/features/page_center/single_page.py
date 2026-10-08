"""通用单页意图与正文候选评估。

这里只使用跨站点可解释的 DOM 结构信号，不包含任何站点专用 selector。
"""

from __future__ import annotations

import re

from app.contracts import (
    BodyCandidate,
    BodyQualityMetrics,
    BodySelection,
    PageIntentAssessment,
)
from app.platform.dom import element_text, parse_html
from app.platform.text_processing import normalize_whitespace

_NOISE_TAGS = {"nav", "aside", "footer", "header", "script", "style", "noscript", "form"}
_CONTENT_TOKEN_RE = re.compile(
    r"(?:^|[-_\s])(content|article|body|entry|post|resource|main|description|text-area)(?:$|[-_\s])",
    re.I,
)
_NOISE_TOKEN_RE = re.compile(
    r"(?:^|[-_\s])(header|footer|nav|menu|sidebar|aside|comment|related|recommend|"
    r"history|breadcrumb|rating|author|user|meta|info|stats|notice|message|"
    r"toc|table-of-contents|infobox|metadata|hatnote|mbox|reflist|advert|"
    r"banner|portal|reference)(?:$|[-_\s])",
    re.I,
)


def assess_page_intent(
    html: str,
    *,
    requested_intent: str | None = None,
) -> PageIntentAssessment:
    root = parse_html(html)
    visible_text = _visible_text(root)
    headings = _primary_heading_nodes(root)
    detail_nodes = _detail_nodes(root)
    repeated_items = _repeated_item_count(root)
    repeated_ratio = min(1.0, repeated_items / max(1, len(_content_blocks(root))))
    signals: list[str] = []

    if len(headings) == 1:
        signals.append("unique_primary_heading")
    if detail_nodes:
        signals.append("detail_metadata")
    if _continuous_body_blocks(root) >= 2:
        signals.append("continuous_body")
    if repeated_items:
        signals.append("repeated_items")
    if root.xpath("//main|//article|//*[@role='main']"):
        signals.append("primary_content_region")

    if repeated_ratio >= 0.35 and not detail_nodes:
        intent = "list"
    elif repeated_items >= 3 and not detail_nodes and _continuous_body_blocks(root) == 0:
        intent = "home"
    elif (root.xpath("//article") or detail_nodes) and len(headings) == 1:
        intent = "article"
    elif len(headings) == 1 and (_continuous_body_blocks(root) >= 1 or detail_nodes):
        intent = "single_resource"
    else:
        intent = "unknown"

    confidence = _intent_confidence(
        intent=intent,
        heading_count=len(headings),
        detail_nodes=bool(detail_nodes),
        continuous_blocks=_continuous_body_blocks(root),
        repeated_ratio=repeated_ratio,
    )
    gate_passed = requested_intent != "single_resource" or intent not in {"home", "list"}
    reasons = []
    if not gate_passed:
        reasons.append("page_intent_mismatch")
    elif intent == "unknown":
        reasons.append("page_intent_low_confidence")
    return PageIntentAssessment(
        intent=intent,
        confidence=confidence,
        gate_passed=gate_passed,
        signals=list(dict.fromkeys(signals)),
        reasons=reasons,
        repeated_item_ratio=repeated_ratio,
        visible_text_chars=len(visible_text),
    )


def select_body_content(html: str) -> BodySelection:
    root = parse_html(html)
    candidates = _body_candidates(root)
    if not candidates:
        return BodySelection(
            accepted=False,
            rejected_reasons=["no_body_candidates"],
            metrics=BodyQualityMetrics(),
        )

    visible_text = _main_visible_text(root)
    visible_chars = len(visible_text)
    selected = _select_non_nested_candidates(candidates)
    if not selected:
        return BodySelection(
            accepted=False,
            rejected_reasons=["no_body_candidates"],
            metrics=BodyQualityMetrics(candidate_count=len(candidates)),
        )

    selected = sorted(selected, key=lambda item: item["order"])
    text = normalize_whitespace(" ".join(item["text"] for item in selected))
    candidate_chars = len(text)
    coverage = min(1.0, candidate_chars / max(1, visible_chars))
    block_count = sum(item["block_count"] for item in selected)
    main_blocks = max(
        1,
        max((item["block_count"] for item in candidates), default=0),
    )
    block_coverage = min(1.0, block_count / main_blocks)
    continuity = _continuity_score(selected)
    noise_ratio = _noise_ratio([item["node"] for item in selected], text)
    metrics = BodyQualityMetrics(
        visible_text_coverage=coverage,
        block_coverage=block_coverage,
        continuity_score=continuity,
        noise_ratio=noise_ratio,
        candidate_count=len(candidates),
        merged_candidate_count=len(selected),
    )
    rejected_reasons: list[str] = []
    if coverage < 0.35:
        rejected_reasons.append("body_coverage_too_low")
    if continuity < 0.25:
        rejected_reasons.append("body_continuity_too_low")
    # Long-form encyclopedic pages often contain substantial infobox,
    # reference, or notice subtrees inside the main article wrapper. Treat
    # noise as a rejection signal only when it also coincides with weak body
    # coverage or continuity; otherwise retain the cleaned article text.
    if noise_ratio > 0.65 and (coverage < 0.7 or continuity < 0.4):
        rejected_reasons.append("body_noise_too_high")
    if candidate_chars < 8:
        rejected_reasons.append("body_text_too_short")
    return BodySelection(
        accepted=not rejected_reasons,
        text=text,
        candidates=[
            BodyCandidate(
                selector=item["selector"],
                xpath=item["xpath"],
                text=item["text"],
                score=item["score"],
                block_count=item["block_count"],
                document_order=item["order"],
            )
            for item in selected
        ],
        metrics=metrics,
        rejected_reasons=rejected_reasons,
    )


def _body_candidates(root) -> list[dict]:
    selectors = [
        "article",
        "main",
        "[role='main']",
        "[class]",
        "[id]",
    ]
    nodes = []
    seen: set[int] = set()
    for selector in selectors:
        try:
            matches = root.cssselect(selector)
        except Exception:
            matches = []
        for node in matches:
            if (
                id(node) in seen
                or node.tag in _NOISE_TAGS
                or any(ancestor.tag in _NOISE_TAGS for ancestor in node.iterancestors())
            ):
                continue
            text = _candidate_text(node)
            if not text:
                continue
            classes = f"{node.get('id') or ''} {node.get('class') or ''}"
            semantic = (
                node.tag in {"article", "main"}
                or (
                    _CONTENT_TOKEN_RE.search(classes)
                    and not _NOISE_TOKEN_RE.search(classes)
                )
            )
            if not semantic:
                continue
            seen.add(id(node))
            tree = root.getroottree()
            nodes.append(
                {
                    "node": node,
                    "text": text,
                    "selector": _node_selector(node),
                    "xpath": tree.getpath(node),
                    "score": _candidate_score(node, text),
                    "block_count": len(_content_blocks(node)),
                    "order": _document_order(node),
                }
            )
    if not nodes:
        body = root.xpath("//body")
        if body and _content_blocks(body[0]):
            node = body[0]
            text = _candidate_text(node)
            tree = root.getroottree()
            nodes.append(
                {
                    "node": node,
                    "text": text,
                    "selector": "body",
                    "xpath": tree.getpath(node),
                    "score": _candidate_score(node, text),
                    "block_count": len(_content_blocks(node)),
                    "order": _document_order(node),
                }
            )
    return nodes


def _select_non_nested_candidates(candidates: list[dict]) -> list[dict]:
    # Prefer meaningful leaf regions over a generic main/article wrapper so
    # adjacent content blocks can be merged in document order.
    max_text_length = max(len(item["text"]) for item in candidates)
    leaf_candidates = [
        candidate
        for candidate in candidates
        if not any(
            other is not candidate
            and other["node"] in candidate["node"].iterdescendants()
            and len(other["text"]) >= len(candidate["text"]) * 0.2
            for other in candidates
        )
        and len(candidate["text"]) >= max_text_length * 0.2
    ]
    ordered = sorted(leaf_candidates or candidates, key=lambda item: item["score"], reverse=True)
    selected: list[dict] = []
    for candidate in ordered:
        node = candidate["node"]
        descendants = [item for item in selected if item["node"] in node.iterdescendants()]
        if descendants:
            # Keep leaf candidates when they account for a meaningful part of a
            # larger wrapper; this enables ordered merging of adjacent regions.
            if len(candidate["text"]) >= sum(len(item["text"]) for item in descendants) * 1.15:
                selected = [item for item in selected if item not in descendants]
                selected.append(candidate)
            continue
        ancestors = [item for item in selected if node in item["node"].iterdescendants()]
        if ancestors:
            continue
        selected.append(candidate)
    return selected


def _candidate_score(node, text: str) -> float:
    semantic_bonus = 0.35 if node.tag in {"article", "main"} else 0.15
    return len(text) * (1.0 + semantic_bonus)


def _node_selector(node) -> str:
    identifier = node.get("id")
    if identifier:
        return f"{node.tag}#{identifier}"
    classes = [part for part in (node.get("class") or "").split() if part]
    return f"{node.tag}.{'.'.join(classes[:2])}" if classes else node.tag


def _document_order(node) -> int:
    return node.sourceline or 0


def _visible_text(root) -> str:
    return normalize_whitespace(" ".join(
        element_text(node)
        for node in root.iter()
        if node.tag not in _NOISE_TAGS and not any(
            ancestor.tag in _NOISE_TAGS for ancestor in node.iterancestors()
        )
    ))


def _is_noise_node(node) -> bool:
    if not isinstance(getattr(node, "tag", None), str):
        return True
    if node.tag in {"html", "body"}:
        return False
    if node.tag in _NOISE_TAGS:
        return True
    identity = f"{node.get('id') or ''} {node.get('class') or ''}"
    return bool(_NOISE_TOKEN_RE.search(identity))


def _candidate_text(node) -> str:
    """Read a candidate while omitting common template/utility subtrees."""

    if _is_noise_node(node) and node.tag not in {"article", "main"}:
        return ""
    parts: list[str] = []
    if node.text:
        parts.append(node.text)
    for child in node:
        if not _is_noise_node(child):
            parts.append(_candidate_text(child))
        if child.tail:
            parts.append(child.tail)
    return normalize_whitespace(" ".join(part for part in parts if part))


def _main_visible_text(root) -> str:
    candidates = _body_candidates(root)
    if candidates:
        return max((item["text"] for item in candidates), key=len)
    body = root.xpath("//body")
    target = body[0] if body else root
    return normalize_whitespace(" ".join(element_text(node) for node in _content_blocks(target)))


def _content_blocks(root) -> list:
    if isinstance(getattr(root, "tag", None), str) and root.tag in {
        "p", "li", "td", "th", "h1", "h2", "h3"
    }:
        nodes = [root, *root.xpath(".//p|.//li|.//td|.//th|.//h1|.//h2|.//h3")]
    else:
        nodes = root.xpath(".//p|.//li|.//td|.//th|.//h1|.//h2|.//h3")
    return [
        node for node in nodes
        if element_text(node)
        and not _has_noise_ancestor_within(node, root)
    ]


def _continuous_body_blocks(root) -> int:
    scoped = [
        node for node in root.xpath("//article//p|//main//p|//*[@role='main']//p")
        if element_text(node)
    ]
    if scoped:
        return len(scoped)
    return len([
        node for node in root.xpath("//body//p|//body//div")
        if element_text(node)
        and not _has_noise_ancestor_within(node, root)
    ])


def _detail_nodes(root) -> list:
    return [
        node for node in root.xpath("//time|//*[@class]|//*[@id]")
        if (
            node.tag == "time"
            or any(token in (node.get("class") or "").lower() for token in ("author", "date", "version", "meta"))
            or any(token in (node.get("id") or "").lower() for token in ("author", "date", "version", "meta"))
        )
        and element_text(node)
    ]


def _primary_heading_nodes(root) -> list:
    headings = [node for node in root.xpath("//h1") if element_text(node)]
    if headings:
        return headings
    scoped_headings = [
        node
        for node in root.xpath("//h2|//h3")
        if element_text(node)
        and any(
            re.search(
                r"(?:^|[-_\s])(title|headline|page-name|entry-title|class-title)(?:$|[-_\s])",
                f"{ancestor.get('class') or ''} {ancestor.get('id') or ''}",
                re.I,
            )
            for ancestor in node.iterancestors()
        )
    ]
    if scoped_headings:
        return scoped_headings
    candidates = []
    for node in root.xpath("//*[@class or @id]"):
        identity = f"{node.get('class') or ''} {node.get('id') or ''}"
        if not re.search(r"(?:^|[-_\s])(title|headline|page-name|entry-title|class-title)(?:$|[-_\s])",
                        identity, re.I):
            continue
        text = element_text(node)
        if 3 <= len(text) <= 240:
            candidates.append(node)
    return candidates[:8]


def _repeated_item_count(root) -> int:
    list_items = [
        node for node in root.xpath("//li")
        # Short Chinese labels are still meaningful repeated navigation/list
        # items; requiring long prose made compact home/list pages look like
        # unknown single pages.
        if element_text(node) and len(element_text(node)) >= 3
    ]
    sections = [
        node for node in root.xpath("//section|//div")
        if len(element_text(node)) >= 3
        and any(token in f"{node.get('class') or ''} {node.get('id') or ''}".lower()
                for token in ("card", "item", "entry", "result", "list"))
    ]
    return max(len(list_items), len(sections))


def _intent_confidence(*, intent, heading_count, detail_nodes, continuous_blocks, repeated_ratio):
    if intent in {"list", "home"}:
        return min(1.0, 0.55 + repeated_ratio * 0.5)
    score = 0.25
    score += 0.3 if heading_count == 1 else 0
    score += 0.2 if detail_nodes else 0
    score += min(0.25, continuous_blocks * 0.08)
    return min(1.0, score)


def _continuity_score(selected: list[dict]) -> float:
    if len(selected) <= 1:
        return 1.0
    lines = [item["order"] for item in selected]
    gaps = [max(0, right - left - 1) for left, right in zip(lines, lines[1:])]
    return 1.0 / (1.0 + sum(gaps) / len(gaps))


def _noise_ratio(selected_nodes: list, selected_text: str) -> float:
    noise_nodes = []
    for selected in selected_nodes:
        for node in selected.iterdescendants():
            if _is_noise_node(node) and not any(
                ancestor in noise_nodes for ancestor in node.iterancestors()
            ):
                noise_nodes.append(node)
    noise = normalize_whitespace(" ".join(
        element_text(node) for node in noise_nodes if element_text(node)
    ))
    if not noise:
        return 0.0
    return min(1.0, len(noise) / max(1, len(selected_text) + len(noise)))


def _has_noise_ancestor_within(node, root) -> bool:
    for ancestor in node.iterancestors():
        if ancestor is root:
            break
        if _is_noise_node(ancestor):
            return True
    return False


__all__ = ["assess_page_intent", "select_body_content"]
