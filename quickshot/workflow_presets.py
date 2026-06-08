"""Screenshot workflow preset definitions."""

from __future__ import annotations

from typing import Any


WORKFLOW_PRESET_CUSTOM = "custom"
WORKFLOW_PRESET_DEFAULT = WORKFLOW_PRESET_CUSTOM

WORKFLOW_PRESET_LABELS: tuple[tuple[str, str], ...] = (
    (WORKFLOW_PRESET_CUSTOM, "自定义"),
    ("quick_copy", "快速复制"),
    ("auto_save", "自动保存"),
    ("ocr", "识文模式"),
    ("publish", "发布模式"),
    ("privacy", "隐私模式"),
)

WORKFLOW_PRESET_HINTS: dict[str, str] = {
    WORKFLOW_PRESET_CUSTOM: "按当前开关执行",
    "quick_copy": "Enter 后复制图片",
    "auto_save": "Enter 后自动保存到默认目录",
    "ocr": "Enter 后 OCR 并复制文字",
    "publish": "Enter 后保存、上传并复制 Markdown",
    "privacy": "截图后先进入智能隐私打码预览",
}

_PRESET_VALUES: dict[str, dict[str, bool]] = {
    "quick_copy": {
        "auto_copy": True,
        "workflow_auto_save": False,
        "workflow_auto_ocr": False,
        "workflow_auto_upload": False,
        "workflow_copy_markdown": False,
        "workflow_privacy_first": False,
    },
    "auto_save": {
        "auto_copy": False,
        "workflow_auto_save": True,
        "workflow_auto_ocr": False,
        "workflow_auto_upload": False,
        "workflow_copy_markdown": False,
        "workflow_privacy_first": False,
    },
    "ocr": {
        "auto_copy": False,
        "workflow_auto_save": False,
        "workflow_auto_ocr": True,
        "workflow_auto_upload": False,
        "workflow_copy_markdown": False,
        "workflow_privacy_first": False,
    },
    "publish": {
        "auto_copy": False,
        "workflow_auto_save": True,
        "workflow_auto_ocr": False,
        "workflow_auto_upload": True,
        "workflow_copy_markdown": True,
        "workflow_privacy_first": False,
    },
    "privacy": {
        "auto_copy": False,
        "workflow_auto_save": False,
        "workflow_auto_ocr": False,
        "workflow_auto_upload": False,
        "workflow_copy_markdown": False,
        "workflow_privacy_first": True,
    },
}

WORKFLOW_PRESET_KEYS = frozenset(preset for preset, _label in WORKFLOW_PRESET_LABELS)


def normalize_workflow_preset(value: Any) -> str:
    preset = str(value or "").strip().lower()
    if preset in WORKFLOW_PRESET_KEYS:
        return preset
    return WORKFLOW_PRESET_DEFAULT


def workflow_preset_values(preset: Any) -> dict[str, bool]:
    normalized = normalize_workflow_preset(preset)
    return dict(_PRESET_VALUES.get(normalized, {}))


def reset_workflow_defaults(config: object) -> bool:
    defaults = {
        "workflow_preset": WORKFLOW_PRESET_DEFAULT,
        "auto_copy": True,
        "workflow_auto_save": False,
        "workflow_auto_ocr": False,
        "workflow_auto_upload": False,
        "workflow_copy_markdown": False,
        "workflow_privacy_first": False,
        "workflow_uploader": "local",
    }
    changed = any(getattr(config, key, None) != value for key, value in defaults.items())
    for key, value in defaults.items():
        setattr(config, key, value)
    return changed


def workflow_preset_label(preset: Any) -> str:
    normalized = normalize_workflow_preset(preset)
    for key, label in WORKFLOW_PRESET_LABELS:
        if key == normalized:
            return label
    return "自定义"


def workflow_preset_hint(preset: Any) -> str:
    return WORKFLOW_PRESET_HINTS.get(normalize_workflow_preset(preset), WORKFLOW_PRESET_HINTS[WORKFLOW_PRESET_CUSTOM])


def workflow_capture_hint(config: object) -> str:
    preset = normalize_workflow_preset(getattr(config, "workflow_preset", WORKFLOW_PRESET_DEFAULT))
    if preset != WORKFLOW_PRESET_CUSTOM:
        return f"{workflow_preset_label(preset)}：{workflow_preset_hint(preset)}"

    actions: list[str] = []
    if getattr(config, "workflow_privacy_first", False):
        actions.append("先智能隐私打码预览")
    if getattr(config, "workflow_auto_save", False):
        actions.append("自动保存")
    if getattr(config, "workflow_auto_ocr", False):
        actions.append("OCR 并复制文字")
    if getattr(config, "workflow_auto_upload", False):
        actions.append("自动上传")
    if getattr(config, "workflow_copy_markdown", False):
        actions.append("复制 Markdown")
    if getattr(config, "auto_copy", False) and not getattr(config, "workflow_privacy_first", False):
        actions.append("自动复制图片")
    if not actions:
        actions.append("手动处理")
    return f"自定义：{'、'.join(actions)}"


def apply_workflow_preset(config: object, preset: Any | None = None) -> bool:
    normalized = normalize_workflow_preset(
        getattr(config, "workflow_preset", WORKFLOW_PRESET_DEFAULT)
        if preset is None
        else preset
    )
    setattr(config, "workflow_preset", normalized)
    values = workflow_preset_values(normalized)
    if not values:
        return False
    for key, value in values.items():
        setattr(config, key, value)
    return True
