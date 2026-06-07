"""QuickShot 通用工具函数与常量。"""

import datetime
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from PyQt6.QtCore import (
    QByteArray,
    QBuffer,
    QIODevice,
    QMimeData,
    QRect,
)
from PyQt6.QtGui import (
    QColor,
    QIcon,
    QImage,
    QPainter,
    QPixmap,
)
from PyQt6.QtWidgets import QApplication

APP_NAME = "QuickShot"
REG_NAME = "QuickShot"
REG_RUN_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_VERSION = "5.3.0"


def get_resource_path(*parts: str) -> Path:
    """兼容源码运行和 PyInstaller 打包后的资源路径。"""
    base_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base_dir.joinpath(*parts)


def create_fallback_icon() -> QIcon:
    """当 assets/icon.ico 不存在时，绘制一个默认图标。"""
    pixmap = QPixmap(64, 64)
    pixmap.fill()
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    painter.setBrush(QColor(0, 120, 212))
    painter.setPen(QColor(0, 120, 212))
    painter.drawEllipse(QRect(12, 12, 40, 40))
    painter.setBrush(QColor(255, 255, 255))
    painter.setPen(QColor(255, 255, 255))
    painter.drawEllipse(QRect(20, 20, 24, 24))
    painter.setBrush(QColor(0, 120, 212))
    painter.setPen(QColor(0, 120, 212))
    painter.drawEllipse(QRect(26, 26, 12, 12))
    painter.end()
    return QIcon(pixmap)


def load_app_icon() -> QIcon:
    icon_path = get_resource_path("assets", "icon.ico")
    if icon_path.exists():
        return QIcon(str(icon_path))
    return create_fallback_icon()


def safe_print(*args) -> None:
    try:
        if getattr(sys, "stdout", None) is not None:
            print(*args)
    except Exception:
        # 本函数就是 stdout 的最后兜底，不能再向 debug_log 抛回（可能引入死循环）
        pass


_DEBUG_LOG_ENABLED: bool | None = None
_DEBUG_LOG_PATH: Path | None = None


def debug_log(message: str) -> None:
    global _DEBUG_LOG_ENABLED, _DEBUG_LOG_PATH
    if _DEBUG_LOG_ENABLED is None:
        _DEBUG_LOG_ENABLED = os.environ.get("QUICKSHOT_DEBUG_LOG") == "1"
        if _DEBUG_LOG_ENABLED:
            _DEBUG_LOG_PATH = Path(os.environ.get("APPDATA") or tempfile.gettempdir()) / APP_NAME / "debug.log"
    if not _DEBUG_LOG_ENABLED:
        return
    try:
        _DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with _DEBUG_LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(f"[{stamp}] {message}\n")
    except OSError:
        # debug_log 自身 IO 失败时绝不可递归调用 debug_log
        pass


def _build_hdr_tone_fix_lut(strength: int = 75) -> bytes:
    strength = max(20, min(100, int(strength)))
    amount = strength / 100.0
    gamma = 1.0 + 0.9 * amount
    exposure = 1.0 - 0.42 * amount
    shoulder = 0.95 + 0.45 * amount
    values = []
    for value in range(256):
        x = value / 255.0
        x = min(1.0, (x ** gamma) * exposure)
        x = x / (x + shoulder * (1.0 - x)) if x > 0.0 else 0.0
        values.append(max(0, min(255, int(round(x * 255.0)))))
    return bytes(values)


_HDR_TONE_FIX_LUTS = {}


def _hdr_tone_fix_lut(strength: int) -> bytes:
    strength = max(20, min(100, int(strength)))
    lut = _HDR_TONE_FIX_LUTS.get(strength)
    if lut is None:
        lut = _build_hdr_tone_fix_lut(strength)
        _HDR_TONE_FIX_LUTS[strength] = lut
    return lut


def apply_hdr_tone_fix(image: QImage, strength: int = 75) -> QImage:
    """Compress over-bright SDR captures produced from HDR content."""
    if image.isNull():
        return image
    try:
        from PIL import Image
    except Exception as exc:
        debug_log(f"HDR tone fix unavailable: {exc}")
        return image

    source = image.convertToFormat(QImage.Format.Format_RGB888)
    width = source.width()
    height = source.height()
    stride = source.bytesPerLine()
    ptr = source.constBits()
    ptr.setsize(stride * height)
    pil_image = Image.frombytes("RGB", (width, height), bytes(ptr), "raw", "RGB", stride, 1)
    fixed = pil_image.point(_hdr_tone_fix_lut(strength) * 3)
    data = fixed.tobytes()
    result = QImage(data, width, height, width * 3, QImage.Format.Format_RGB888).copy()
    result.setDevicePixelRatio(image.devicePixelRatio())
    return result


def _hdr_strength_for_scale(sdr_white_scale: float) -> int:
    """根据系统报告的 SDR 白点系数计算 LUT 修复强度。
    1.0 倍（普通 SDR）→ 0 不修复；1.5 倍 → 30；2.0 倍 → 45；3.0+ 倍 → 60 上限。"""
    if sdr_white_scale <= 1.05:
        return 0
    return max(30, min(60, int((sdr_white_scale - 1.0) * 20)))


def pixmap_from_rgb_array(frame, sdr_white_scale: float = 0.0) -> QPixmap:
    height, width = frame.shape[:2]
    stride = int(frame.strides[0])
    qimage = QImage(
        frame.data,
        int(width),
        int(height),
        stride,
        QImage.Format.Format_RGB888,
    ).copy()
    strength = _hdr_strength_for_scale(sdr_white_scale)
    if strength > 0:
        qimage = apply_hdr_tone_fix(qimage, strength)
    pixmap = QPixmap.fromImage(qimage)
    pixmap.setDevicePixelRatio(1.0)
    return pixmap


def pixmap_from_sc_rgb_frame(frame, sdr_white_scale: float = 0.0) -> QPixmap:
    """Convert a linear scRGB float capture to an SDR sRGB pixmap."""
    try:
        import numpy as np
    except Exception as exc:
        debug_log(f"HDR float frame conversion unavailable: {exc}")
        return QPixmap()

    if frame is None or getattr(frame, "size", 0) == 0:
        return QPixmap()

    rgb = np.asarray(frame[..., :3], dtype=np.float32)
    rgb = np.nan_to_num(rgb, nan=0.0, posinf=16.0, neginf=0.0)
    rgb = np.maximum(rgb, 0.0)

    # WGC exposes HDR output as linear scRGB. On HDR desktops, ordinary SDR
    # white is above 1.0 because Windows maps it to the user's SDR white level.
    # Prefer the OS value and estimate from the image only as a fallback.
    if sdr_white_scale > 0.0:
        sdr_white = float(sdr_white_scale)
    else:
        luminance = rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722
        bright = luminance[luminance > 0.02]
        sdr_white = float(np.percentile(bright, 90)) if bright.size else 1.0
    sdr_white = max(1.0, min(4.0, sdr_white))
    normalized = rgb / sdr_white

    # Keep SDR content stable after paper-white normalization, then add a soft
    # shoulder only above SDR white instead of a blanket brightness reduction.
    mapped = normalized / (1.0 + np.maximum(normalized - 1.0, 0.0) * 0.85)
    mapped = np.clip(mapped, 0.0, 1.0)
    debug_log(f"HDR SDR white estimate: {sdr_white:.3f}")

    threshold = 0.0031308
    srgb = np.where(
        mapped <= threshold,
        mapped * 12.92,
        1.055 * np.power(mapped, 1.0 / 2.4) - 0.055,
    )
    data = np.clip(srgb * 255.0 + 0.5, 0, 255).astype(np.uint8)
    data = np.ascontiguousarray(data)
    height, width = data.shape[:2]
    qimage = QImage(
        data.data,
        int(width),
        int(height),
        int(data.strides[0]),
        QImage.Format.Format_RGB888,
    ).copy()
    pixmap = QPixmap.fromImage(qimage)
    pixmap.setDevicePixelRatio(1.0)
    return pixmap


def pixmap_from_mss(shot) -> QPixmap:
    qimage = QImage(
        shot.rgb,
        shot.width,
        shot.height,
        shot.width * 3,
        QImage.Format.Format_RGB888,
    ).copy()
    pixmap = QPixmap.fromImage(qimage)
    pixmap.setDevicePixelRatio(1.0)
    return pixmap


def copy_pixmap_to_clipboard(pixmap: QPixmap) -> None:
    """高清复制到剪贴板，同时写入 image/png 和 imageData。"""
    if pixmap.isNull():
        return
    image = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
    image.setDevicePixelRatio(1.0)
    png_bytes = QByteArray()
    buffer = QBuffer(png_bytes)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    buffer.close()
    mime = QMimeData()
    mime.setImageData(image)
    mime.setData("image/png", png_bytes)
    QApplication.clipboard().setMimeData(mime)


def copy_text_to_clipboard(text: str) -> None:
    """复制纯文本到剪贴板（用于 Markdown 链接等）。"""
    if not text:
        return
    QApplication.clipboard().setText(text)


def hidden_process_startupinfo():
    if not sys.platform.startswith("win"):
        return None
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0
    return startupinfo
