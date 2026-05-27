"""共享测试 fixtures —— 为新 pytest 风格测试提供 QApplication、Overlay 等。"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Generator

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QRect  # noqa: E402
from PyQt6.QtGui import QColor, QPixmap  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from quickshot.config import Config  # noqa: E402
from quickshot.history import CaptureHistoryStore  # noqa: E402
from quickshot.overlay.widget import FloatingSnipOverlay  # noqa: E402


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app  # type: ignore[return-value]


@pytest.fixture()
def isolated_config(qapp: QApplication, tmp_path: Path) -> Generator[Config, None, None]:
    prev = os.environ.get("APPDATA")
    os.environ["APPDATA"] = str(tmp_path)
    try:
        yield Config()
    finally:
        if prev is None:
            os.environ.pop("APPDATA", None)
        else:
            os.environ["APPDATA"] = prev


@pytest.fixture()
def history_store(qapp: QApplication, tmp_path: Path) -> CaptureHistoryStore:
    cfg = Config()
    cfg.data_dir = lambda: tmp_path  # type: ignore[method-assign]
    cfg.history_dir = lambda: tmp_path / "history"  # type: ignore[method-assign]
    cfg.history_index_path = lambda: tmp_path / "history" / "index.json"  # type: ignore[method-assign]
    cfg.ensure_history_dir = (  # type: ignore[method-assign]
        lambda: (tmp_path / "history").mkdir(parents=True, exist_ok=True)
        or (tmp_path / "history")
    )
    return CaptureHistoryStore(cfg)


def make_overlay(**cfg_overrides) -> FloatingSnipOverlay:
    """工厂函数，供 unittest.TestCase 的 setUp 调用。"""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    cfg = Config()
    for k, v in cfg_overrides.items():
        setattr(cfg, k, v)
    store = CaptureHistoryStore(cfg)
    raw = QPixmap(800, 600)
    raw.fill(QColor(60, 60, 60))
    disp = QPixmap(800, 600)
    disp.fill(QColor(60, 60, 60))
    ov = FloatingSnipOverlay(
        raw, disp, QRect(0, 0, 800, 600), 1.0, 1.0, 0, 0, cfg, store
    )
    ov.selection_rect = QRect(100, 100, 400, 300)
    ov.selection_physical_rect = QRect(100, 100, 400, 300)
    ov.base_edit_pixmap = raw.copy(QRect(100, 100, 400, 300))
    ov.edit_pixmap = ov.base_edit_pixmap.copy()
    ov.mode = "edit"
    ov.resize(800, 600)
    return ov


@pytest.fixture()
def overlay(qapp: QApplication) -> FloatingSnipOverlay:
    return make_overlay()
