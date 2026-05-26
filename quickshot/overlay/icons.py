"""工具栏 SVG 图标缓存：按 (key, color) 缓存渲染器，避免重复解析 SVG。"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from PyQt6.QtCore import QByteArray, QRect, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtSvg import QSvgRenderer

from ..utils import get_resource_path


class IconCache:
    def __init__(self) -> None:
        self._templates: Dict[str, str] = {}
        self._renderers: Dict[Tuple[str, str], QSvgRenderer] = {}

    def template(self, key: str) -> str:
        template = self._templates.get(key)
        if template is not None:
            return template
        path = get_resource_path("assets", "toolbar", f"{key}.svg")
        try:
            template = path.read_text(encoding="utf-8")
        except OSError:
            template = ""
        self._templates[key] = template
        return template

    def renderer(self, key: str, color: QColor) -> Optional[QSvgRenderer]:
        cache_key = (key, color.name())
        renderer = self._renderers.get(cache_key)
        if renderer is not None:
            return renderer
        template = self.template(key)
        if not template:
            return None
        svg = template.replace("currentColor", color.name())
        renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
        if not renderer.isValid():
            return None
        self._renderers[cache_key] = renderer
        return renderer

    def draw(self, painter: QPainter, key: str, rect: QRect, color: QColor) -> None:
        renderer = self.renderer(key, color)
        if renderer is not None:
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            renderer.render(painter, QRectF(rect))
            painter.restore()
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(color, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QRectF(rect).adjusted(5, 5, -5, -5))
        painter.restore()
