"""CaptureHistoryStore id 索引正确性测试。

验证 update_ocr_text / update_capture / delete_item 在内存索引下行为正确：
- 索引能命中正确的 item（不只是首项或尾项）
- 增删改后内存缓存与磁盘保持一致
- 索引随 save_items 重建
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


def _make_store(tmp_root: Path) -> CaptureHistoryStore:
    _ensure_app()
    cfg = Config()
    # 重定向数据目录到临时目录，避免污染用户实际历史
    cfg.data_dir = lambda: tmp_root  # type: ignore[method-assign]
    cfg.history_dir = lambda: tmp_root / "history"  # type: ignore[method-assign]
    cfg.history_index_path = lambda: tmp_root / "history" / "index.json"  # type: ignore[method-assign]
    cfg.ensure_history_dir = lambda: (tmp_root / "history").mkdir(parents=True, exist_ok=True) or (tmp_root / "history")  # type: ignore[method-assign]
    return CaptureHistoryStore(cfg)


def _pixmap(color: int = 80) -> QPixmap:
    pm = QPixmap(20, 20)
    pm.fill(QColor(color, color, color))
    return pm


class HistoryIndexTest(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_root = Path(self._tmp.name)
        self.store = _make_store(self.tmp_root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_update_ocr_text_hits_correct_item(self) -> None:
        items = [self.store.add_capture(_pixmap(i * 10)) for i in (1, 2, 3, 4, 5)]
        target = items[2]
        assert target is not None
        self.store.update_ocr_text(str(target["id"]), "找到我了")
        reloaded = self.store.load_items()
        match = next(i for i in reloaded if i.get("id") == target["id"])
        self.assertEqual(match["ocr_text"], "找到我了")
        # 其他项未受影响
        for other in reloaded:
            if other["id"] != target["id"]:
                self.assertEqual(other.get("ocr_text", ""), "")

    def test_delete_item_removes_and_reindexes(self) -> None:
        items = [self.store.add_capture(_pixmap(i * 10)) for i in (1, 2, 3, 4)]
        victim = items[1]
        assert victim is not None
        victim_id = str(victim["id"])
        self.store.delete_item(victim_id)
        reloaded = self.store.load_items()
        self.assertEqual(len(reloaded), 3)
        self.assertNotIn(victim_id, [i["id"] for i in reloaded])
        # 删除后再操作另一个 id，索引仍能命中
        another = items[2]
        assert another is not None
        self.store.update_ocr_text(str(another["id"]), "yo")
        post = self.store.load_items()
        match = next(i for i in post if i["id"] == another["id"])
        self.assertEqual(match["ocr_text"], "yo")

    def test_update_capture_moves_to_front(self) -> None:
        items = [self.store.add_capture(_pixmap(i * 10)) for i in (1, 2, 3)]
        target = items[2]  # 最早添加 → 在末尾
        assert target is not None
        ok = self.store.update_capture(str(target["id"]), _pixmap(200), source="ocr")
        self.assertTrue(ok)
        reloaded = self.store.load_items()
        self.assertEqual(reloaded[0]["id"], target["id"])
        self.assertEqual(reloaded[0]["source"], "ocr")

    def test_unknown_id_is_noop(self) -> None:
        self.store.add_capture(_pixmap(50))
        before = self.store.load_items()
        self.store.update_ocr_text("not_a_real_id", "ignored")
        self.store.delete_item("not_a_real_id")
        ok = self.store.update_capture("not_a_real_id", _pixmap(60))
        self.assertFalse(ok)
        after = self.store.load_items()
        self.assertEqual(before, after)

    def test_cache_invalidated_on_save(self) -> None:
        a = self.store.add_capture(_pixmap(10))
        b = self.store.add_capture(_pixmap(20))
        assert a and b
        # 先触发 existing_items 缓存
        first = self.store.existing_items()
        self.assertEqual(len(first), 2)
        self.store.delete_item(str(a["id"]))
        # existing_cache 应被 save_items 清掉，重读为 1 条
        second = self.store.existing_items()
        self.assertEqual(len(second), 1)
        self.assertEqual(second[0]["id"], b["id"])


if __name__ == "__main__":
    unittest.main()
