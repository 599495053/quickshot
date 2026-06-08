"""User-facing feedback message helpers."""

from __future__ import annotations

import re

from .diagnostics import redact_diagnostic_text


DIAGNOSTIC_HINT = "可从托盘菜单或设置页复制诊断信息后反馈。"
SHORT_DIAGNOSTIC_HINT = "可复制诊断信息后反馈"


def _normalize_detail(detail: object) -> str:
    text = redact_diagnostic_text(str(detail or "")).strip()
    return re.sub(r"\s+", " ", text)


def compact_error_message(summary: str, detail: object = "", *, include_hint: bool = True, max_length: int = 120) -> str:
    """Build a short one-line message for overlay text or tray notifications."""
    summary = str(summary).strip()
    detail_text = _normalize_detail(detail)
    message = summary
    if detail_text:
        message = f"{summary}：{detail_text}"
    if include_hint:
        message = f"{message}；{SHORT_DIAGNOSTIC_HINT}"
    if max_length > 0 and len(message) > max_length:
        suffix = f"；{SHORT_DIAGNOSTIC_HINT}" if include_hint else ""
        room = max(16, max_length - len(suffix) - 1)
        message = f"{message[:room].rstrip()}…{suffix}"
    return message


def detailed_error_message(summary: str, detail: object = "", *, include_hint: bool = True) -> str:
    """Build a multi-line message for modal dialogs."""
    lines = [str(summary).strip()]
    detail_text = _normalize_detail(detail)
    if detail_text:
        lines.extend(["", f"原因：{detail_text}"])
    if include_hint:
        lines.extend(["", DIAGNOSTIC_HINT])
    return "\n".join(lines)
