"""Diagnostic report helpers for user feedback."""

from __future__ import annotations

import datetime as _datetime
import importlib.util
import os
import platform
import re
import sys
import tempfile
from pathlib import Path

from .utils import APP_NAME, APP_VERSION


_SECRET_PATTERNS = (
    re.compile(r"github_pat_[A-Za-z0-9_]+", re.IGNORECASE),
    re.compile(r"gh[opsu]_[A-Za-z0-9_]+", re.IGNORECASE),
    re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+"),
    re.compile(r"(?i)((?:token|password|secret|api[_-]?key)\s*[:=]\s*)[^\s,;]+"),
)
_WINDOWS_PATH_PATTERN = re.compile(r"(?i)\b[A-Z]:[\\/][^\r\n]*")
_UNC_PATH_PATTERN = re.compile(r"\\\\[^\\\r\n]+\\[^\\\r\n]+[^\r\n]*")


def debug_log_path() -> Path:
    return Path(os.environ.get("APPDATA") or tempfile.gettempdir()) / APP_NAME / "debug.log"


def is_debug_log_enabled() -> bool:
    return os.environ.get("QUICKSHOT_DEBUG_LOG") == "1"


def _redaction_roots() -> list[tuple[str, str]]:
    roots = [
        ("USERPROFILE", str(Path.home())),
        ("APPDATA", os.environ.get("APPDATA", "")),
        ("LOCALAPPDATA", os.environ.get("LOCALAPPDATA", "")),
        ("TEMP", tempfile.gettempdir()),
    ]
    result = []
    seen = set()
    for label, raw_path in roots:
        if not raw_path:
            continue
        normalized = str(Path(raw_path))
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append((normalized, f"%{label}%"))
    result.sort(key=lambda item: len(item[0]), reverse=True)
    return result


def redact_diagnostic_text(text: str) -> str:
    redacted = str(text)
    for actual, placeholder in _redaction_roots():
        redacted = redacted.replace(actual, placeholder)
        redacted = redacted.replace(actual.replace("\\", "/"), placeholder.replace("\\", "/"))
    for pattern in _SECRET_PATTERNS:
        if pattern.groups:
            redacted = pattern.sub(lambda match: f"{match.group(1)}<redacted>", redacted)
        else:
            redacted = pattern.sub("<redacted>", redacted)
    redacted = _WINDOWS_PATH_PATTERN.sub("<path>", redacted)
    redacted = _UNC_PATH_PATTERN.sub("<path>", redacted)
    return redacted


def _bool(value: object) -> str:
    return "true" if bool(value) else "false"


def _module_status(module_name: str) -> str:
    try:
        return "available" if importlib.util.find_spec(module_name) is not None else "missing"
    except (ImportError, ValueError, AttributeError):
        return "missing"


def _qt_versions() -> tuple[str, str]:
    try:
        from PyQt6.QtCore import PYQT_VERSION_STR, qVersion

        return qVersion(), PYQT_VERSION_STR
    except Exception:
        return "unknown", "unknown"


def _safe_path(path: object) -> str:
    return redact_diagnostic_text(str(path))


def _append_config_summary(lines: list[str], config) -> None:
    lines.extend(
        [
            "",
            "Config:",
            f"  ConfigPath={_safe_path(getattr(config, 'config_path', ''))}",
            f"  AppDataDir={_safe_path(getattr(config, 'app_dir', ''))}",
            f"  SaveDir={_safe_path(getattr(config, 'save_dir', ''))}",
            f"  SaveDirMode={getattr(config, 'save_dir_mode', '')}",
            f"  SaveFormat={getattr(config, 'save_format', '')}",
            f"  AutoCopy={_bool(getattr(config, 'auto_copy', False))}",
            f"  ShowNotifications={_bool(getattr(config, 'show_notifications', False))}",
            f"  HdrColorAccurate={_bool(getattr(config, 'hdr_color_accurate', False))}",
            f"  AutoHistory={_bool(getattr(config, 'auto_history', False))}",
            f"  HistoryLimit={getattr(config, 'history_limit', '')}",
            f"  SnapToWindows={_bool(getattr(config, 'snap_to_windows', False))}",
            f"  RegionHotkey={getattr(config, 'region_hotkey', '')}",
            f"  WindowHotkey={getattr(config, 'window_hotkey', '')}",
            f"  HistoryHotkey={getattr(config, 'history_hotkey', '')}",
            f"  PinHotkey={getattr(config, 'pin_hotkey', '')}",
            f"  OcrHotkey={getattr(config, 'ocr_hotkey', '')}",
            f"  WorkflowPreset={getattr(config, 'workflow_preset', '')}",
            f"  WorkflowAutoSave={_bool(getattr(config, 'workflow_auto_save', False))}",
            f"  WorkflowAutoOcr={_bool(getattr(config, 'workflow_auto_ocr', False))}",
            f"  WorkflowAutoUpload={_bool(getattr(config, 'workflow_auto_upload', False))}",
            f"  WorkflowCopyMarkdown={_bool(getattr(config, 'workflow_copy_markdown', False))}",
            f"  WorkflowPrivacyFirst={_bool(getattr(config, 'workflow_privacy_first', False))}",
            f"  WorkflowUploader={getattr(config, 'workflow_uploader', '')}",
            f"  GithubOwnerConfigured={_bool(bool(getattr(config, 'github_owner', '')))}",
            f"  GithubRepoConfigured={_bool(bool(getattr(config, 'github_repo', '')))}",
            f"  GithubBranch={getattr(config, 'github_branch', '')}",
            f"  GithubPathPrefix={getattr(config, 'github_path_prefix', '')}",
        ]
    )


def _append_optional_module_summary(lines: list[str]) -> None:
    modules = (
        "mss",
        "PIL",
        "rapidocr_onnxruntime",
        "onnxruntime",
        "numpy",
        "dxcam",
        "winrt.windows.graphics.capture",
    )
    lines.append("")
    lines.append("OptionalModules:")
    for module_name in modules:
        lines.append(f"  {module_name}={_module_status(module_name)}")


def _read_log_tail(path: Path, line_count: int) -> list[str]:
    if line_count <= 0 or not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ["<unable to read debug log>"]
    return [redact_diagnostic_text(line) for line in lines[-line_count:]]


def build_diagnostic_report(config=None, log_tail_lines: int = 80, now: _datetime.datetime | None = None) -> str:
    if now is None:
        now = _datetime.datetime.now().astimezone()
    qt_version, pyqt_version = _qt_versions()
    log_path = debug_log_path()
    lines = [
        "QuickShot Diagnostic Report",
        f"GeneratedAt={now.isoformat(timespec='seconds')}",
        f"AppName={APP_NAME}",
        f"AppVersion={APP_VERSION}",
        f"Python={platform.python_version()}",
        f"Platform={platform.platform()}",
        f"Machine={platform.machine()}",
        f"Executable={_safe_path(sys.executable)}",
        f"Frozen={_bool(getattr(sys, 'frozen', False))}",
        f"Qt={qt_version}",
        f"PyQt={pyqt_version}",
        f"DebugLogEnabled={_bool(is_debug_log_enabled())}",
        f"DebugLogPath={_safe_path(log_path)}",
        f"DebugLogExists={_bool(log_path.exists())}",
    ]
    if config is not None:
        _append_config_summary(lines, config)
    _append_optional_module_summary(lines)
    log_tail = _read_log_tail(log_path, log_tail_lines)
    lines.append("")
    lines.append(f"DebugLogTailLastLines={len(log_tail)}")
    if log_tail:
        lines.extend(log_tail)
    return redact_diagnostic_text("\n".join(lines).strip() + "\n")
