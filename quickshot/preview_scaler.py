"""异步图片缩放 helper。

主线程把 QImage 提交到全局 QThreadPool 缩放，回调时把 QImage 转成 QPixmap
emit 出去给调用方显示。每次提交自增 token，回调用 token 校验，
旧任务在新选中条目到来时被自然丢弃，不会覆盖最新结果。
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QObject, QRunnable, Qt, QThreadPool, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap


class _ScaleSignals(QObject):
    finished = pyqtSignal(int, QImage)


class _ScaleRunnable(QRunnable):
    def __init__(
        self,
        token: int,
        source: QImage,
        target_w: int,
        target_h: int,
        aspect_mode: Qt.AspectRatioMode,
        signals: _ScaleSignals,
    ) -> None:
        super().__init__()
        self.token = token
        self.source = source
        self.target_w = target_w
        self.target_h = target_h
        self.aspect_mode = aspect_mode
        self.signals = signals

    def run(self) -> None:
        if self.source.isNull() or self.target_w <= 0 or self.target_h <= 0:
            self.signals.finished.emit(self.token, QImage())
            return
        scaled = self.source.scaled(
            self.target_w,
            self.target_h,
            self.aspect_mode,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.signals.finished.emit(self.token, scaled)


class AsyncPreviewScaler(QObject):
    """提交 QImage → 全局线程池 SmoothTransformation 缩放 → ready(QPixmap)。"""

    ready = pyqtSignal(QPixmap)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._token = 0
        self._signals = _ScaleSignals(self)
        self._signals.finished.connect(self._on_finished)

    def request(
        self,
        source: QImage,
        target_w: int,
        target_h: int,
        aspect_mode: Qt.AspectRatioMode = Qt.AspectRatioMode.KeepAspectRatio,
    ) -> int:
        self._token += 1
        token = self._token
        task = _ScaleRunnable(token, source, target_w, target_h, aspect_mode, self._signals)
        QThreadPool.globalInstance().start(task)
        return token

    def cancel(self) -> None:
        """递增 token 丢弃所有未完成任务的回调。"""
        self._token += 1

    def _on_finished(self, token: int, image: QImage) -> None:
        if token != self._token:
            return
        if image.isNull():
            self.ready.emit(QPixmap())
        else:
            self.ready.emit(QPixmap.fromImage(image))
