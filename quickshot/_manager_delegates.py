"""manager 子模块共享：header card 工厂 + 两个列表条目 delegate。"""

from PyQt6.QtCore import QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QFrame, QLabel, QStyle, QStyledItemDelegate, QVBoxLayout

from .ui import make_card


def build_header_card(title: str, subtitle: str) -> QFrame:
    card = make_card("heroCard")
    title_label = QLabel(title)
    title_label.setObjectName("heroTitle")
    subtitle_label = QLabel(subtitle)
    subtitle_label.setObjectName("heroSubtitle")
    subtitle_label.setWordWrap(True)

    layout = QVBoxLayout()
    layout.setContentsMargins(18, 16, 18, 16)
    layout.setSpacing(4)
    layout.addWidget(title_label)
    layout.addWidget(subtitle_label)
    card.setLayout(layout)
    return card


class HistoryItemDelegate(QStyledItemDelegate):
    """卡片式历史条目代理：左侧大缩略图 + 右侧详细信息。"""

    THUMB_W = 160
    THUMB_H = 100
    ITEM_H = 112
    MARGIN = 10
    GAP = 12
    RADIUS = 8

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._font_date = QFont("Microsoft YaHei", 9, QFont.Weight.DemiBold)
        self._font_meta = QFont("Microsoft YaHei", 8)
        self._font_ocr = QFont("Microsoft YaHei", 8, italic=True)
        self._fm_date = QFontMetrics(self._font_date)
        self._fm_meta = QFontMetrics(self._font_meta)
        self._fm_ocr = QFontMetrics(self._font_ocr)

        self._card_selected = (QColor(232, 240, 255, 230), QPen(QColor(160, 195, 255, 220), 1))
        self._card_hover = (QColor(245, 247, 250, 220), QPen(QColor(218, 222, 228, 180), 1))
        self._card_normal = (QColor(255, 255, 255, 200), QPen(QColor(228, 232, 238, 140), 1))

        self._thumb_shadow = QColor(0, 0, 0, 18)
        self._thumb_bg = QColor(240, 242, 245)
        self._thumb_placeholder_pen = QColor(180, 185, 195)
        self._pen_title_selected = QColor(30, 60, 120)
        self._pen_title_normal = QColor(55, 65, 81)
        self._pen_size = QColor(120, 130, 145)
        self._pen_ocr = QColor(140, 150, 165)

        self._tag_selected = (QColor(100, 150, 255, 60), QPen(QColor(100, 150, 255, 120), 1))
        self._tag_normal = (QColor(230, 235, 242, 180), QPen(QColor(200, 208, 218), 1))

    def sizeHint(self, option, index) -> QSize:
        return QSize(option.rect.width(), self.ITEM_H)

    def paint(self, painter: QPainter, option, index) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = option.rect.adjusted(self.MARGIN, 5, -self.MARGIN, -5)
        is_selected = bool(option.state & QStyle.StateFlag.State_Selected)
        is_hover = bool(option.state & QStyle.StateFlag.State_MouseOver)

        if is_selected:
            bg, border_pen = self._card_selected
        elif is_hover:
            bg, border_pen = self._card_hover
        else:
            bg, border_pen = self._card_normal

        card_rect = QRectF(rect)
        painter.setPen(border_pen)
        painter.setBrush(bg)
        painter.drawRoundedRect(card_rect, self.RADIUS, self.RADIUS)

        # 缩略图（_load_thumbnail_batch 中已预缩放到 THUMB_W×THUMB_H）
        thumb_pixmap = index.data(Qt.ItemDataRole.UserRole + 1)
        thumb_x = rect.left() + 8
        thumb_y = rect.top() + (rect.height() - self.THUMB_H) // 2
        thumb_rect = QRectF(thumb_x, thumb_y, self.THUMB_W, self.THUMB_H)
        if isinstance(thumb_pixmap, QPixmap) and not thumb_pixmap.isNull():
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._thumb_shadow)
            painter.drawRoundedRect(thumb_rect.adjusted(-1, -1, 1, 1), 6, 6)
            painter.setBrush(self._thumb_bg)
            painter.drawRoundedRect(thumb_rect, 5, 5)
            sx = thumb_x + (self.THUMB_W - thumb_pixmap.width()) / 2
            sy = thumb_y + (self.THUMB_H - thumb_pixmap.height()) / 2
            painter.drawPixmap(int(sx), int(sy), thumb_pixmap)
        else:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._thumb_bg)
            painter.drawRoundedRect(thumb_rect, 5, 5)
            painter.setPen(self._thumb_placeholder_pen)
            painter.setFont(self._font_meta)
            painter.drawText(thumb_rect, Qt.AlignmentFlag.AlignCenter, "加载中...")

        text_x = thumb_x + self.THUMB_W + self.GAP
        text_w = rect.right() - text_x - 8
        if text_w < 60:
            painter.restore()
            return

        date_text = str(index.data(Qt.ItemDataRole.UserRole + 2) or "")
        source_text = str(index.data(Qt.ItemDataRole.UserRole + 3) or "")

        painter.setFont(self._font_date)
        painter.setPen(self._pen_title_selected if is_selected else self._pen_title_normal)
        first_line_y = rect.top() + 18
        date_w = self._fm_date.horizontalAdvance(date_text)
        painter.drawText(int(text_x), int(first_line_y), date_text)

        if source_text:
            tag_x = text_x + date_w + 8
            tag_h = 18
            tag_w = self._fm_meta.horizontalAdvance(source_text) + 12
            tag_rect = QRectF(tag_x, first_line_y - tag_h + 4, tag_w, tag_h)
            tag_bg, tag_pen = self._tag_selected if is_selected else self._tag_normal
            painter.setBrush(tag_bg)
            painter.setPen(tag_pen)
            painter.drawRoundedRect(tag_rect, 4, 4)
            painter.setFont(self._font_meta)
            painter.drawText(tag_rect, Qt.AlignmentFlag.AlignCenter, source_text)

        size_text = str(index.data(Qt.ItemDataRole.UserRole + 4) or "")
        if size_text:
            painter.setFont(self._font_meta)
            painter.setPen(self._pen_size)
            painter.drawText(int(text_x), int(first_line_y + 22), size_text)

        ocr_text = str(index.data(Qt.ItemDataRole.UserRole + 5) or "")
        if ocr_text:
            painter.setFont(self._font_ocr)
            painter.setPen(self._pen_ocr)
            elided = self._fm_ocr.elidedText(ocr_text, Qt.TextElideMode.ElideRight, text_w)
            painter.drawText(int(text_x), int(first_line_y + 44), elided)

        painter.restore()


class PinItemDelegate(QStyledItemDelegate):
    """卡片式贴图条目代理：复用 HistoryItemDelegate 的尺寸规格。"""

    THUMB_W = HistoryItemDelegate.THUMB_W
    THUMB_H = HistoryItemDelegate.THUMB_H
    ITEM_H = HistoryItemDelegate.ITEM_H
    MARGIN = HistoryItemDelegate.MARGIN
    GAP = HistoryItemDelegate.GAP
    RADIUS = HistoryItemDelegate.RADIUS

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._font_name = QFont("Microsoft YaHei", 9, QFont.Weight.DemiBold)
        self._font_meta = QFont("Microsoft YaHei", 8)
        self._font_tag = QFont("Microsoft YaHei", 8)
        self._fm_name = QFontMetrics(self._font_name)
        self._fm_meta = QFontMetrics(self._font_meta)

        self._card_selected = (QColor(232, 240, 255, 230), QPen(QColor(160, 195, 255, 220), 1))
        self._card_hover = (QColor(245, 247, 250, 220), QPen(QColor(218, 222, 228, 180), 1))
        self._card_normal = (QColor(255, 255, 255, 200), QPen(QColor(228, 232, 238, 140), 1))

        self._thumb_shadow = QColor(0, 0, 0, 18)
        self._thumb_bg = QColor(240, 242, 245)
        self._thumb_placeholder_pen = QColor(180, 185, 195)
        self._pen_title_selected = QColor(30, 60, 120)
        self._pen_title_normal = QColor(55, 65, 81)
        self._pen_size = QColor(120, 130, 145)
        self._pen_status = QColor(140, 150, 165)
        self._pen_time = QColor(160, 170, 185)

    def sizeHint(self, option, index) -> QSize:
        return QSize(option.rect.width(), self.ITEM_H)

    def paint(self, painter: QPainter, option, index) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = option.rect.adjusted(self.MARGIN, 5, -self.MARGIN, -5)
        is_selected = bool(option.state & QStyle.StateFlag.State_Selected)
        is_hover = bool(option.state & QStyle.StateFlag.State_MouseOver)

        if is_selected:
            bg, border_pen = self._card_selected
        elif is_hover:
            bg, border_pen = self._card_hover
        else:
            bg, border_pen = self._card_normal

        card_rect = QRectF(rect)
        painter.setPen(border_pen)
        painter.setBrush(bg)
        painter.drawRoundedRect(card_rect, self.RADIUS, self.RADIUS)

        thumb_pixmap = index.data(Qt.ItemDataRole.UserRole + 1)
        thumb_x = rect.left() + 8
        thumb_y = rect.top() + (rect.height() - self.THUMB_H) // 2
        thumb_rect = QRectF(thumb_x, thumb_y, self.THUMB_W, self.THUMB_H)
        if isinstance(thumb_pixmap, QPixmap) and not thumb_pixmap.isNull():
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._thumb_shadow)
            painter.drawRoundedRect(thumb_rect.adjusted(-1, -1, 1, 1), 6, 6)
            painter.setBrush(self._thumb_bg)
            painter.drawRoundedRect(thumb_rect, 5, 5)
            sx = thumb_x + (self.THUMB_W - thumb_pixmap.width()) / 2
            sy = thumb_y + (self.THUMB_H - thumb_pixmap.height()) / 2
            painter.drawPixmap(int(sx), int(sy), thumb_pixmap)
        else:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._thumb_bg)
            painter.drawRoundedRect(thumb_rect, 5, 5)
            painter.setPen(self._thumb_placeholder_pen)
            painter.setFont(self._font_meta)
            painter.drawText(thumb_rect, Qt.AlignmentFlag.AlignCenter, "无预览")

        text_x = thumb_x + self.THUMB_W + self.GAP
        text_w = rect.right() - text_x - 8
        if text_w < 60:
            painter.restore()
            return

        name_text = str(index.data(Qt.ItemDataRole.UserRole + 2) or "")
        painter.setFont(self._font_name)
        painter.setPen(self._pen_title_selected if is_selected else self._pen_title_normal)
        first_line_y = rect.top() + 18
        painter.drawText(int(text_x), int(first_line_y), name_text)

        size_text = str(index.data(Qt.ItemDataRole.UserRole + 3) or "")
        if size_text:
            painter.setFont(self._font_meta)
            painter.setPen(self._pen_size)
            painter.drawText(int(text_x), int(first_line_y + 22), size_text)

        status_text = str(index.data(Qt.ItemDataRole.UserRole + 4) or "")
        if status_text:
            painter.setFont(self._font_tag)
            painter.setPen(self._pen_status)
            elided = self._fm_meta.elidedText(status_text, Qt.TextElideMode.ElideRight, text_w)
            painter.drawText(int(text_x), int(first_line_y + 44), elided)

        time_text = str(index.data(Qt.ItemDataRole.UserRole + 5) or "")
        if time_text:
            painter.setFont(self._font_meta)
            painter.setPen(self._pen_time)
            painter.drawText(int(text_x), int(first_line_y + 64), time_text)

        painter.restore()
