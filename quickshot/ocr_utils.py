"""OCR 文本清洗与格式化工具函数。

从 ocr.py 中拆出，供 OCR 模块、编辑器、历史窗口等共用。
"""

from __future__ import annotations

import re
from typing import List


OCR_TEXT_CONTENT_RE = re.compile(r"[A-Za-z0-9\u4e00-\u9fff]")
OCR_COMMON_PUNCTUATION = set(".,;:!?)]}([{'\"<>%-+/#@&\\$¥€=~")
OCR_CLEANUP_LEVELS = {"standard", "conservative", "off"}


OCR_SYMBOL_TRANSLATION = str.maketrans({
    "，": ",", "。": ".", "：": ":", "；": ";",
    "（": "(", "）": ")", "［": "[", "］": "]",
    "【": "[", "】": "]", "｛": "{", "｝": "}",
    "《": "<", "》": ">", "〈": "<", "〉": ">",
    "“": '"', "”": '"', "„": '"', "＂": '"',
    "‘": "'", "’": "'", "‚": "'", "＇": "'",
    "－": "-", "–": "-", "—": "-", "―": "-",
    "〜": "~", "～": "~", "＋": "+", "＝": "=",
    "／": "/", "＼": "\\", "｜": "|", "＊": "*",
    "＆": "&", "％": "%", "＃": "#", "＠": "@",
    "！": "!", "？": "?",
})

def normalize_ocr_symbols(text: str) -> str:
    return text.translate(OCR_SYMBOL_TRANSLATION).replace(" ", " ")

def normalize_ocr_cleanup_level(value: object) -> str:
    level = str(value) if value is not None else "standard"
    return level if level in OCR_CLEANUP_LEVELS else "standard"

def has_meaningful_ocr_text(text: str) -> bool:
    return OCR_TEXT_CONTENT_RE.search(text) is not None

def _compact_ocr_text(text: str) -> str:
    return re.sub(r"\s+", "", normalize_ocr_symbols(text or ""))

def is_likely_icon_symbol_artifact(text: str) -> bool:
    compact = _compact_ocr_text(text)
    if not compact or has_meaningful_ocr_text(compact):
        return False
    if len(compact) <= 3:
        return True
    return len(compact) <= 8 and len(set(compact)) <= 2

def filter_icon_symbol_artifacts(text: str, *, cleanup_level: str = "standard") -> str:
    if not text:
        return ""
    cleanup_level = normalize_ocr_cleanup_level(cleanup_level)
    if cleanup_level == "off":
        return normalize_ocr_symbols(text).strip()
    lines = []
    for raw_line in normalize_ocr_symbols(text).splitlines():
        line = " ".join(raw_line.split())
        if not line:
            lines.append("")
            continue
        if is_likely_icon_symbol_artifact(line):
            continue
        lines.append(line)
    return "\n".join(lines).strip()

def has_cjk(text: str) -> bool:
    return any("一" <= ch <= "鿿" for ch in text)

def should_join_with_space(previous: str, current: str, gap: float, avg_height: float) -> bool:
    if not previous or not current:
        return False
    if gap <= max(3.0, avg_height * 0.18):
        return False
    if has_cjk(previous[-1]) and has_cjk(current[0]):
        return False
    if current[0] in ",.;:!?)]}>" or previous[-1] in "([{<":
        return False
    return True

def _nearest_meaningful_block_gap(blocks: list[dict], index: int) -> float | None:
    block = blocks[index]
    gaps = []
    for previous in reversed(blocks[:index]):
        if has_meaningful_ocr_text(previous["text"]):
            gaps.append(max(0.0, block["left"] - previous["right"]))
            break
    for following in blocks[index + 1:]:
        if has_meaningful_ocr_text(following["text"]):
            gaps.append(max(0.0, following["left"] - block["right"]))
            break
    return min(gaps) if gaps else None

def _should_drop_icon_symbol_block(
    blocks: list[dict],
    index: int,
    line_height: float,
    cleanup_level: str,
) -> bool:
    if cleanup_level == "off":
        return False
    text = str(blocks[index]["text"]).strip()
    if not is_likely_icon_symbol_artifact(text):
        return False
    meaningful_count = sum(1 for block in blocks if has_meaningful_ocr_text(block["text"]))
    if meaningful_count == 0:
        return True

    gap = _nearest_meaningful_block_gap(blocks, index)
    if gap is None:
        return True
    compact = _compact_ocr_text(text)
    if cleanup_level == "conservative":
        return len(compact) <= 3 and gap > max(24.0, line_height * 1.6)
    if set(text).issubset(OCR_COMMON_PUNCTUATION) and gap <= max(3.0, line_height * 0.35):
        return False
    return True

def _filter_icon_symbol_blocks(
    blocks: list[dict],
    line_height: float,
    cleanup_level: str,
) -> list[dict]:
    return [
        block for index, block in enumerate(blocks)
        if not _should_drop_icon_symbol_block(blocks, index, line_height, cleanup_level)
    ]

def format_rapidocr_result(
    result,
    *,
    filter_symbols: bool = True,
    cleanup_level: str = "standard",
) -> str:
    if not result:
        return ""
    cleanup_level = normalize_ocr_cleanup_level(cleanup_level)
    if not filter_symbols:
        cleanup_level = "off"

    blocks = []
    for item in result:
        if len(item) < 2:
            continue
        box = item[0]
        text = str(item[1]).strip()
        if not text:
            continue
        try:
            xs = [float(point[0]) for point in box]
            ys = [float(point[1]) for point in box]
            if not xs or not ys:
                continue
        except (TypeError, ValueError, IndexError):
            # 上游 OCR 偶发返回畸形 box，跳过单条即可
            continue
        top = min(ys)
        bottom = max(ys)
        blocks.append({
            "text": text,
            "left": min(xs),
            "right": max(xs),
            "center_y": (top + bottom) / 2.0,
            "height": max(1.0, bottom - top),
        })

    if not blocks:
        return ""

    blocks.sort(key=lambda item: (item["center_y"], item["left"]))
    avg_height = sum(item["height"] for item in blocks) / max(1, len(blocks))
    line_threshold = max(10.0, avg_height * 0.65)

    lines = []
    for block in blocks:
        if not lines or abs(block["center_y"] - lines[-1]["center_y"]) > line_threshold:
            lines.append({
                "center_y": block["center_y"],
                "height": block["height"],
                "blocks": [block],
            })
            continue
        line = lines[-1]
        line["blocks"].append(block)
        count = len(line["blocks"])
        line["center_y"] = (line["center_y"] * (count - 1) + block["center_y"]) / count
        line["height"] = max(line["height"], block["height"])

    text_lines = []
    for line in lines:
        line_blocks = sorted(line["blocks"], key=lambda item: item["left"])
        if cleanup_level != "off":
            line_blocks = _filter_icon_symbol_blocks(line_blocks, line["height"], cleanup_level)
        if not line_blocks:
            continue
        parts: List[str] = []
        previous = None
        for block in line_blocks:
            text = block["text"]
            if previous is not None and should_join_with_space(
                parts[-1], text, block["left"] - previous["right"], line["height"],
            ):
                parts.append(" ")
            parts.append(text)
            previous = block
        text_lines.append("".join(parts).strip())

    text = normalize_ocr_symbols("\n".join(line for line in text_lines if line)).strip()
    return filter_icon_symbol_artifacts(text, cleanup_level=cleanup_level)

def clean_ocr_text(text: str) -> str:
    """对 OCR 结果做轻量自动清洗：去首尾空格、合并连续空行、规范内部空格。"""
    if not text:
        return ""
    lines = []
    prev_empty = False
    for raw_line in text.splitlines():
        line = " ".join(raw_line.split())
        if not line:
            if prev_empty:
                continue
            prev_empty = True
            lines.append("")
        else:
            prev_empty = False
            lines.append(line)
    return "\n".join(lines).strip()

def deep_clean_ocr_text(text: str) -> str:
    """深度清洗 OCR 文本：移除多余空行、规范标点、修复常见 OCR 错误。"""
    if not text:
        return ""
    # 先做基础清洗
    text = clean_ocr_text(text)
    # 移除所有空行，合并为单行
    text = re.sub(r'\n+', '\n', text)
    # 修复常见 OCR 错误
    replacements = {
        '，，': '，',
        '。。': '。',
        '：：': '：',
        '；；': '；',
        '（（': '（',
        '））': '）',
        '  ': ' ',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    # 规范中英文混合的空格（循环应用直到没有变化）
    prev = None
    while prev != text:
        prev = text
        text = re.sub(r'([\u4e00-\u9fff])\s+([\u4e00-\u9fff])', r'\1\2', text)
    return text.strip()

def extract_numbers(text: str) -> list:
    """从文本中提取所有数字。"""
    return re.findall(r'\d+\.?\d*', text)

def extract_chinese(text: str) -> str:
    """提取中文文本。"""
    return ''.join(re.findall(r'[\u4e00-\u9fff]+', text))

def clean_lines_text(text: str) -> str:
    """整理空行和首尾空格。"""
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)

def clean_soft_text(text: str) -> str:
    """轻清洗：整理空行 + 合并行内多余空格。"""
    lines = [line.strip() for line in text.splitlines()]
    normalized = []
    for line in lines:
        if not line:
            continue
        normalized.append(" ".join(line.split()))
    return "\n".join(normalized)

def clean_hard_text(text: str) -> str:
    """强清洗：制表符替换 + 合并行内空格 + 所有行合并为一行。"""
    text = text.replace("\t", " ")
    lines = []
    for line in text.splitlines():
        compact = " ".join(line.split())
        if compact:
            lines.append(compact)
    return " ".join(lines)
