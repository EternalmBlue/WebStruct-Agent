"""多视图归一化：把 PageObservation 变成 ViewBundle（文本、行、标题、文本块）。

行为契约：specs/features/page-center.feature
"""

from __future__ import annotations

import re
from typing import Any

from app.contracts import PageObservation, ViewBundle
from app.platform.dom import element_text, parse_html
from app.platform.text_processing import html_to_text


def normalize_page_view(observation: PageObservation) -> ViewBundle:
    text, title, headings = html_to_text(observation.html)
    lines = [line for line in text.splitlines() if line.strip()]
    text_blocks = observation.metadata.get("text_blocks") or extract_text_blocks(observation.html)
    return ViewBundle(
        url=observation.url,
        raw_html=observation.html,
        text=text,
        lines=lines,
        title=title or observation.title,
        headings=headings,
        metadata={
            "line_count": len(lines),
            "heading_count": len(headings),
            "text_blocks": text_blocks,
            "text_block_count": len(text_blocks),
            "collector": observation.metadata.get("collector", ""),
            "page_classification": observation.metadata.get("page_classification", "unknown"),
            "page_intent": observation.metadata.get("page_intent"),
            "body_selection": observation.metadata.get("body_selection"),
            "page_hash": observation.metadata.get("page_hash"),
        },
    )


def extract_text_blocks(html: str, *, limit: int = 200) -> list[dict[str, Any]]:
    root = parse_html(html)
    tree = root.getroottree()
    block_tags = {"h1", "h2", "h3", "p", "li", "td", "th"}
    blocks = []
    for element in root.iter():
        if element.tag not in block_tags or any(
            ancestor.tag in block_tags for ancestor in element.iterancestors()
        ):
            continue
        text = element_text(element)
        if not text:
            continue
        xpath = tree.getpath(element)
        # Tree paths use sibling-local indices and remain valid around void/nested tags.
        selector = " > ".join(
            re.sub(r"\[(\d+)\]", r":nth-of-type(\1)", part)
            for part in xpath.strip("/").split("/")
        )
        blocks.append({"tag": element.tag, "selector": selector, "xpath": xpath, "text": text})
        if len(blocks) >= limit:
            break
    return blocks
