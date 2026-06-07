from __future__ import annotations

import ast
from pathlib import Path

from build_config import EXCLUDED_MODULES, filter_binaries


OPTIONAL_HEAVY_IMPORT_ROOTS = {"dxcam", "numpy", "winrt"}


def test_filter_binaries_removes_qt_translation_files():
    entries = [
        ("PyQt6/Qt6/translations/qtbase_zh_CN.qm", "src/qtbase_zh_CN.qm", "BINARY"),
        ("PyQt6\\Qt6\\translations\\qt_help_fr.qm", "src/qt_help_fr.qm", "BINARY"),
        ("PyQt6/Qt6/plugins/platforms/qwindows.dll", "src/qwindows.dll", "BINARY"),
    ]

    filtered = filter_binaries(entries)

    assert filtered == [
        ("PyQt6/Qt6/plugins/platforms/qwindows.dll", "src/qwindows.dll", "BINARY"),
    ]


def test_filter_binaries_keeps_non_qm_translation_assets():
    entries = [
        ("assets/toolbar/ocr.svg", "assets/toolbar/ocr.svg", "DATA"),
        ("PyQt6/Qt6/translations/readme.txt", "src/readme.txt", "DATA"),
    ]

    assert filter_binaries(entries) == entries


def test_default_build_excludes_optional_heavy_capture_modules():
    for module_name in OPTIONAL_HEAVY_IMPORT_ROOTS:
        assert module_name in EXCLUDED_MODULES


def test_quickshot_uses_dynamic_imports_for_optional_heavy_modules():
    root = Path(__file__).resolve().parents[1] / "quickshot"
    offenders = []

    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".", 1)[0] in OPTIONAL_HEAVY_IMPORT_ROOTS:
                        offenders.append((path.relative_to(root), alias.name, node.lineno))
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.split(".", 1)[0] in OPTIONAL_HEAVY_IMPORT_ROOTS:
                    offenders.append((path.relative_to(root), node.module, node.lineno))

    assert offenders == []
