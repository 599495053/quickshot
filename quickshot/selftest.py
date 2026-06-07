"""Packaged-app self-tests used by release verification."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from PyQt6.QtGui import QImage

from . import ocr


SELF_TEST_ARG = "--quickshot-self-test"
PRIVACY_OCR_FALLBACK_TEST = "privacy-ocr-fallback"


def _write_line(stream_name: str, text: str) -> None:
    stream = getattr(sys, stream_name, None)
    if stream is None:
        return
    try:
        stream.write(text + "\n")
        stream.flush()
    except Exception:
        pass


def _load_sample_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/calibri.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError as exc:
        raise RuntimeError("No usable TrueType font found for privacy OCR self-test.") from exc


def _make_privacy_sample_qimage() -> QImage:
    image = Image.new("RGB", (1600, 420), "white")
    draw = ImageDraw.Draw(image)
    font = _load_sample_font(96)
    draw.text((80, 50), "Phone 13812345678", fill="black", font=font)
    draw.text((80, 220), "test@example.com", fill="black", font=font)

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix="quickshot_privacy_selftest_", suffix=".png", delete=False) as handle:
            temp_path = Path(handle.name)
        image.save(temp_path)
        qimage = QImage(str(temp_path))
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink()
            except OSError:
                pass

    if qimage.isNull():
        raise RuntimeError("Failed to create privacy OCR self-test image.")
    return qimage


def run_privacy_ocr_fallback_self_test() -> None:
    if ocr.is_rapidocr_available():
        raise RuntimeError("RapidOCR is available; lightweight fallback path was not exercised.")

    rects = ocr.detect_privacy_info(_make_privacy_sample_qimage())
    if not rects:
        raise RuntimeError("Windows OCR fallback did not detect privacy text.")

    if not any(width > 0 and height > 0 for _x, _y, width, height in rects):
        raise RuntimeError(f"Windows OCR fallback returned invalid privacy rectangles: {rects!r}")


def run_self_test(name: str) -> int:
    try:
        if name == PRIVACY_OCR_FALLBACK_TEST:
            run_privacy_ocr_fallback_self_test()
        else:
            raise RuntimeError(f"Unknown self-test: {name}")
    except Exception as exc:
        _write_line("stderr", f"QuickShot self-test failed ({name}): {exc}")
        return 1

    _write_line("stdout", f"QuickShot self-test passed: {name}")
    return 0
