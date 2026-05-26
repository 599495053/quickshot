import datetime
import json
import os
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from PyQt6.QtGui import QPixmap

from .config import Config
from .utils import debug_log


class CaptureHistoryStore:
    def __init__(self, config: Config) -> None:
        self.config = config
        self._existing_cache: Optional[List[Dict[str, object]]] = None
        # 全量 items 内存模型 + id → index 索引（懒加载，save_items 后重建）
        self._items_cache: Optional[List[Dict[str, object]]] = None
        self._id_index: Dict[str, int] = {}

    def _invalidate_cache(self) -> None:
        self._existing_cache = None

    def _invalidate_all(self) -> None:
        self._existing_cache = None
        self._items_cache = None
        self._id_index = {}

    def _rebuild_index(self, items: List[Dict[str, object]]) -> None:
        self._id_index = {
            str(item.get("id", "")): idx
            for idx, item in enumerate(items)
            if item.get("id")
        }

    def existing_items(self) -> List[Dict[str, object]]:
        if self._existing_cache is not None:
            return self._existing_cache
        self._existing_cache = [item for item in self.load_items() if self.image_path(item).exists()]
        return self._existing_cache

    def load_items(self) -> List[Dict[str, object]]:
        if self._items_cache is not None:
            # 返回浅拷贝 list（dict 引用共享）：外部可重排序/删除，但对 dict 字段的修改
            # 会同步反映到 cache，update_* 方法依赖这一约定
            return list(self._items_cache)
        path = self.config.history_index_path()
        items: List[Dict[str, object]] = []
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    items = [item for item in data if isinstance(item, dict)]
        except Exception as exc:
            debug_log(f"load history failed: {exc}")
        self._items_cache = items
        self._rebuild_index(items)
        return list(items)

    def save_items(self, items: List[Dict[str, object]]) -> None:
        try:
            history_dir = self.config.ensure_history_dir()
            index_path = history_dir / "index.json"
            tmp_path = history_dir / "index.json.tmp"
            data = json.dumps(items, ensure_ascii=False, indent=2)
            tmp_path.write_text(data, encoding="utf-8")
            os.replace(str(tmp_path), str(index_path))
            # 用写入的列表作为新的 cache 真相
            self._items_cache = list(items)
            self._rebuild_index(self._items_cache)
            self._invalidate_cache()
        except OSError as exc:
            debug_log(f"save history failed: {exc}")

    def add_capture(self, pixmap: QPixmap, source: str = "capture", ocr_text: str = "") -> Optional[Dict[str, object]]:
        if pixmap.isNull():
            return None
        history_dir = self.config.ensure_history_dir()
        now = datetime.datetime.now()
        item_id = uuid.uuid4().hex[:12]
        filename = f"{now.strftime('%Y%m%d_%H%M%S')}_{item_id}.png"
        image_path = history_dir / filename
        if not pixmap.save(str(image_path), "PNG"):
            return None

        item = {
            "id": item_id,
            "created_at": now.isoformat(timespec="seconds"),
            "filename": filename,
            "width": pixmap.width(),
            "height": pixmap.height(),
            "source": source,
            "ocr_text": ocr_text or "",
            "tags": [],
            "favorite": False,
        }
        items = self.load_items()
        items.insert(0, item)
        self.prune_items(items)
        self.save_items(items)
        return item

    def update_ocr_text(self, item_id: str, text: str) -> None:
        if not item_id:
            return
        items = self.load_items()
        idx = self._id_index.get(item_id)
        if idx is None or idx >= len(items) or items[idx].get("id") != item_id:
            return
        items[idx]["ocr_text"] = text
        self.save_items(items)

    def toggle_favorite(self, item_id: str) -> bool:
        """切换收藏状态，返回新状态。"""
        if not item_id:
            return False
        items = self.load_items()
        idx = self._id_index.get(item_id)
        if idx is None or idx >= len(items) or items[idx].get("id") != item_id:
            return False
        items[idx]["favorite"] = not items[idx].get("favorite", False)
        self.save_items(items)
        return items[idx]["favorite"]

    def add_tag(self, item_id: str, tag: str) -> None:
        """添加标签。"""
        if not item_id or not tag:
            return
        items = self.load_items()
        idx = self._id_index.get(item_id)
        if idx is None or idx >= len(items) or items[idx].get("id") != item_id:
            return
        tags = items[idx].get("tags", [])
        if tag not in tags:
            tags.append(tag)
            items[idx]["tags"] = tags
            self.save_items(items)

    def remove_tag(self, item_id: str, tag: str) -> None:
        """移除标签。"""
        if not item_id or not tag:
            return
        items = self.load_items()
        idx = self._id_index.get(item_id)
        if idx is None or idx >= len(items) or items[idx].get("id") != item_id:
            return
        tags = items[idx].get("tags", [])
        if tag in tags:
            tags.remove(tag)
            items[idx]["tags"] = tags
            self.save_items(items)

    def search(self, query: str = "", source: str = "", tag: str = "", favorite_only: bool = False) -> List[Dict[str, object]]:
        """搜索历史项，支持关键词、来源、标签、收藏筛选。"""
        items = self.existing_items()
        matched = []
        for item in items:
            if source and source != "all" and item.get("source") != source:
                continue
            if favorite_only and not item.get("favorite", False):
                continue
            if tag and tag not in item.get("tags", []):
                continue
            if query:
                keyword = query.lower()
                haystack = " ".join([
                    str(item.get("created_at", "")),
                    str(item.get("filename", "")),
                    str(item.get("ocr_text", "")),
                    " ".join(item.get("tags", [])),
                ]).lower()
                if keyword not in haystack:
                    continue
            matched.append(item)
        return matched

    def update_capture(
        self,
        item_id: str,
        pixmap: QPixmap,
        source: str = "",
        ocr_text: str = "",
    ) -> bool:
        if not item_id or pixmap.isNull():
            return False
        items = self.load_items()
        idx = self._id_index.get(item_id)
        if idx is None or idx >= len(items) or items[idx].get("id") != item_id:
            return False
        item = items[idx]
        image_path = self.image_path(item)
        if not pixmap.save(str(image_path), "PNG"):
            return False
        item["width"] = pixmap.width()
        item["height"] = pixmap.height()
        if source:
            item["source"] = source
        if ocr_text:
            item["ocr_text"] = ocr_text
        item["updated_at"] = datetime.datetime.now().isoformat(timespec="seconds")
        items.insert(0, items.pop(idx))
        self.save_items(items)
        return True

    def image_path(self, item: Dict[str, object]) -> Path:
        return self.config.history_dir() / str(item.get("filename", ""))

    def usage_bytes(self, items: Optional[List[Dict[str, object]]] = None) -> int:
        total = 0
        for item in items if items is not None else self.existing_items():
            try:
                total += self.image_path(item).stat().st_size
            except Exception as exc:
                debug_log(f"history usage stat failed: {exc}")
        return total

    def delete_item(self, item_id: str) -> None:
        if not item_id:
            return
        items = self.load_items()
        idx = self._id_index.get(item_id)
        if idx is None or idx >= len(items) or items[idx].get("id") != item_id:
            return
        target = items[idx]
        try:
            self.image_path(target).unlink(missing_ok=True)
        except Exception as exc:
            debug_log(f"delete history image failed: {exc}")
        items.pop(idx)
        self.save_items(items)

    def apply_history_limit(self) -> int:
        items = self.load_items()
        before = len(items)
        self.prune_items(items)
        if len(items) != before:
            self.save_items(items)
        return max(0, before - len(items))

    def clear_all(self) -> int:
        items = self.existing_items()
        removed = 0
        for item in items:
            try:
                self.image_path(item).unlink(missing_ok=True)
                removed += 1
            except Exception as exc:
                debug_log(f"clear history image failed: {exc}")
        self.save_items([])
        return removed

    def prune_items(self, items: List[Dict[str, object]]) -> None:
        limit = max(20, int(getattr(self.config, "history_limit", 200)))
        overflow = items[limit:]
        del items[limit:]
        for item in overflow:
            try:
                self.image_path(item).unlink(missing_ok=True)
            except Exception as exc:
                debug_log(f"prune history image failed: {exc}")
