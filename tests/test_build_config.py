from __future__ import annotations

from build_config import filter_binaries


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
