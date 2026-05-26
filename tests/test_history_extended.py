"""CaptureHistoryStore 扩展测试。

覆盖 history.py 中未被 test_history_index.py 覆盖的分支：
- search: 关键词搜索、来源筛选
- usage_bytes: 磁盘占用计算
- clear_all: 清空全部
- prune_items: 超限裁剪
- add_capture: 空 pixmap 拒绝
- image_path: 路径拼接
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QColor, QPixmap  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from quickshot.config import Config  # noqa: E402
from quickshot.history import CaptureHistoryStore  # noqa: E402


_app: QApplication | None = None


def _ensure_app() -> QApplication:
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication(sys.argv)
    return _app


def _make_store(tmp_root: Path, history_limit: int = 200) -> CaptureHistoryStore:
    _ensure_app()
    cfg = Config()
    cfg.history_limit = history_limit
    cfg.data_dir = lambda: tmp_root  # type: ignore[method-assign]
    cfg.history_dir = lambda: tmp_root / "history"  # type: ignore[method-assign]
    cfg.history_index_path = lambda: tmp_root / "history" / "index.json"  # type: ignore[method-assign]
    cfg.ensure_history_dir = lambda: (tmp_root / "history").mkdir(parents=True, exist_ok=True) or (tmp_root / "history")  # type: ignore[method-assign]
    return CaptureHistoryStore(cfg)


def _pixmap(w: int = 20, h: int = 20, color: int = 80) -> QPixmap:
    pm = QPixmap(w, h)
    pm.fill(QColor(color, color, color))
    return pm


class HistorySearchTest(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_root = Path(self._tmp.name)
        self.store = _make_store(self.tmp_root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_search_empty_returns_all(self) -> None:
        self.store.add_capture(_pixmap(), source="capture")
        self.store.add_capture(_pixmap(), source="ocr", ocr_text="hello")
        results = self.store.search()
        self.assertEqual(len(results), 2)

    def test_search_by_keyword(self) -> None:
        self.store.add_capture(_pixmap(), source="capture")
        self.store.add_capture(_pixmap(), source="ocr", ocr_text="hello world")
        results = self.store.search(query="hello")
        self.assertEqual(len(results), 1)

    def test_search_by_source(self) -> None:
        self.store.add_capture(_pixmap(), source="capture")
        self.store.add_capture(_pixmap(), source="ocr")
        results = self.store.search(source="ocr")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["source"], "ocr")

    def test_search_source_all(self) -> None:
        self.store.add_capture(_pixmap(), source="capture")
        self.store.add_capture(_pixmap(), source="ocr")
        results = self.store.search(source="all")
        self.assertEqual(len(results), 2)

    def test_search_keyword_and_source(self) -> None:
        self.store.add_capture(_pixmap(), source="capture", ocr_text="foo")
        self.store.add_capture(_pixmap(), source="ocr", ocr_text="foo")
        self.store.add_capture(_pixmap(), source="capture", ocr_text="bar")
        results = self.store.search(query="foo", source="ocr")
        self.assertEqual(len(results), 1)


class HistoryUsageTest(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_root = Path(self._tmp.name)
        self.store = _make_store(self.tmp_root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_usage_bytes_nonzero(self) -> None:
        self.store.add_capture(_pixmap())
        usage = self.store.usage_bytes()
        self.assertGreater(usage, 0)

    def test_usage_bytes_empty(self) -> None:
        usage = self.store.usage_bytes()
        self.assertEqual(usage, 0)


class HistoryClearAllTest(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_root = Path(self._tmp.name)
        self.store = _make_store(self.tmp_root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_clear_all_removes_everything(self) -> None:
        self.store.add_capture(_pixmap())
        self.store.add_capture(_pixmap())
        removed = self.store.clear_all()
        self.assertEqual(removed, 2)
        items = self.store.load_items()
        self.assertEqual(len(items), 0)


class HistoryPruneTest(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_prune_respects_limit(self) -> None:
        # prune_items 内部有 max(20, limit) 保护，所以测试用 25
        store = _make_store(self.tmp_root, history_limit=25)
        for i in range(30):
            store.add_capture(_pixmap(color=i * 5))
        items = store.load_items()
        self.assertLessEqual(len(items), 25)


class HistoryAddEdgeCasesTest(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_root = Path(self._tmp.name)
        self.store = _make_store(self.tmp_root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_add_null_pixmap_returns_none(self) -> None:
        result = self.store.add_capture(QPixmap())
        self.assertIsNone(result)

    def test_image_path_construction(self) -> None:
        self.store.add_capture(_pixmap())
        items = self.store.load_items()
        self.assertEqual(len(items), 1)
        path = self.store.image_path(items[0])
        self.assertTrue(str(path).endswith(".png"))


if __name__ == "__main__":
    unittest.main()
