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
