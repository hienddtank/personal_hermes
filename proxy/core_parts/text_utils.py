import re
from typing import List, Optional

from .config import (
    THINK_TAGS,
    VISIBLE_XML_BLOCK_TAGS,
    VISIBLE_XML_TAG_PREFIXES,
)
from .models import SessionState

VISIBLE_XML_INLINE_OPEN_RE = re.compile(r"<(function|parameter)(?:=[^>\s]+)?>")
VISIBLE_XML_INLINE_CLOSE_TAGS = {
    "function": "</function>",
    "parameter": "</parameter>",
}
VISIBLE_XML_STRAY_TAG_RE = re.compile(
    r"</?(?:tool_call|tool_response|result|command|function|parameter)(?:=[^>\s]+)?>"
)


def split_safe_prefix(text: str, tags: tuple[str, ...]) -> tuple[str, str]:
    hold_len = longest_partial_tag_suffix(text, tags)
    if hold_len:
        return text[:-hold_len], text[-hold_len:]
    return text, ""


def escape_xml_like_text(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def tool_call_prefix_is_structural(prefix: str) -> bool:
    if inside_markdown_code_fence(prefix):
        return False
    if not prefix.strip():
        return True
    line_start = max(prefix.rfind("\n"), prefix.rfind("\r")) + 1
    return not prefix[line_start:].strip()


def tool_call_block_is_structural_in_text(text: str, complete_tool: str) -> bool:
    start = text.rfind(complete_tool)
    if start == -1:
        return True
    return tool_call_prefix_is_structural(text[:start])


def tool_call_open_is_structural_in_text(text: str) -> bool:
    start = text.find("<tool_call>")
    if start == -1:
        return False
    return tool_call_prefix_is_structural(text[:start])


def tool_call_block_is_structural(session: SessionState, complete_tool: str) -> bool:
    return tool_call_block_is_structural_in_text(session.raw_text_buffer, complete_tool)


def tool_call_body(text: str) -> Optional[str]:
    start = text.find("<tool_call>")
    if start == -1:
        return None
    end = text.find("</tool_call>", start + len("<tool_call>"))
    if end == -1:
        return None
    return text[start + len("<tool_call>") : end]


def tool_call_block_looks_like_json(text: str) -> bool:
    body = tool_call_body(text)
    if body is None:
        return bool(
            re.search(r"<tool_call>\s*(?:```(?:json)?\s*)?\{", text, flags=re.IGNORECASE | re.DOTALL)
        )
    candidate = body.strip()
    candidate = re.sub(r"^```(?:json)?\s*\n?", "", candidate, flags=re.IGNORECASE)
    candidate = candidate.lstrip()
    return candidate.startswith("{")


def tool_capture_buffer_is_actionable(session: SessionState) -> bool:
    return (
        ("<function=" in session.tool_call_buffer or tool_call_block_looks_like_json(session.tool_call_buffer))
        and tool_call_block_is_structural(session, session.tool_call_buffer)
    )


def inside_markdown_code_fence(prefix: str) -> bool:
    fence_count = len(re.findall(r"(?m)^[ \t]*(?:```|~~~)", prefix))
    return fence_count % 2 == 1


def longest_partial_tag_suffix(text: str, tags: tuple[str, ...]) -> int:
    max_hold = 0
    for tag in tags:
        max_len = min(len(tag) - 1, len(text))
        for size in range(1, max_len + 1):
            if tag.startswith(text[-size:]):
                max_hold = max(max_hold, size)
    return max_hold


def remove_control_tags(text: str) -> str:
    text = text.replace("<think>", "").replace("</think>", "")
    return sanitize_visible_tool_xml(text).strip()


def sanitize_visible_tool_xml(text: str) -> str:
    if not text:
        return text
    for opener, closer in VISIBLE_XML_BLOCK_TAGS.items():
        text = re.sub(re.escape(opener) + r".*?" + re.escape(closer), "", text, flags=re.DOTALL)
    text = re.sub(r"<function(?:=[^>\s]+)?>.*?</function>", "", text, flags=re.DOTALL)
    text = re.sub(r"<parameter(?:=[^>\s]+)?>.*?</parameter>", "", text, flags=re.DOTALL)
    text = VISIBLE_XML_STRAY_TAG_RE.sub("", text)
    return text


def scrub_visible_tool_xml(text: str, session: Optional[SessionState] = None) -> str:
    if not text:
        return text
    if session is None:
        return sanitize_visible_tool_xml(text)

    text = session.visible_xml_buffer + text
    session.visible_xml_buffer = ""
    output: List[str] = []
    index = 0

    while index < len(text):
        if session.hidden_xml_closer:
            close_pos = text.find(session.hidden_xml_closer, index)
            if close_pos == -1:
                session.visible_xml_buffer = text[max(index, len(text) - len(session.hidden_xml_closer) + 1) :]
                return "".join(output)
            index = close_pos + len(session.hidden_xml_closer)
            session.hidden_xml_closer = None
            continue

        next_pos = len(text)
        next_closer: Optional[str] = None

        for opener, closer in VISIBLE_XML_BLOCK_TAGS.items():
            pos = text.find(opener, index)
            if pos != -1 and pos < next_pos:
                next_pos = pos
                next_closer = closer

        for match in VISIBLE_XML_INLINE_OPEN_RE.finditer(text, index):
            if match.start() < next_pos:
                next_pos = match.start()
                next_closer = VISIBLE_XML_INLINE_CLOSE_TAGS[match.group(1)]
            break

        stray_match = VISIBLE_XML_STRAY_TAG_RE.search(text, index)
        if stray_match and stray_match.start() < next_pos:
            output.append(text[index:stray_match.start()])
            index = stray_match.end()
            continue

        if next_closer is None:
            tail_start = find_partial_visible_xml_start(text[index:])
            if tail_start is None:
                output.append(text[index:])
            else:
                output.append(text[index : index + tail_start])
                session.visible_xml_buffer = text[index + tail_start :]
            break

        output.append(text[index:next_pos])
        close_pos = text.find(next_closer, next_pos)
        if close_pos == -1:
            session.hidden_xml_closer = next_closer
            session.visible_xml_buffer = text[max(next_pos, len(text) - len(next_closer) + 1) :]
            break

        index = close_pos + len(next_closer)

    return "".join(output)


def find_partial_visible_xml_start(text: str) -> Optional[int]:
    for start in range(max(0, len(text) - 32), len(text)):
        suffix = text[start:]
        if any(tag.startswith(suffix) for tag in VISIBLE_XML_TAG_PREFIXES):
            return start
    return None


def salvage_visible_text_after_orphan_tool_tag(text: str) -> str:
    markers = ("</parameter>", "</function>", "</tool_call>", "</command>", "</tool_response>")
    last_pos = -1
    last_marker = ""
    for marker in markers:
        pos = text.rfind(marker)
        if pos > last_pos:
            last_pos = pos
            last_marker = marker
    if last_pos == -1:
        return ""
    visible = text[last_pos + len(last_marker) :]
    return scrub_visible_tool_xml(visible).lstrip()
