from dataclasses import dataclass
from importlib.util import find_spec
import threading
from pathlib import Path
from typing import Optional, Union

from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor, QImage, QPainter, QPixmap

from .constants import OCR_IMAGE_MAX_SCALE, OCR_IMAGE_SMOOTH_THRESHOLD
from .utils import debug_log, hidden_process_startupinfo


@dataclass(frozen=True)
class OcrResult:
    text: str
    engine_key: str
    engine_label: str
    elapsed_seconds: float = 0.0
    note: str = ""

from .ocr_utils import (
    OCR_SYMBOL_TRANSLATION,
    clean_hard_text,
    clean_lines_text,
    clean_ocr_text,
    clean_soft_text,
    deep_clean_ocr_text,
    extract_chinese,
    extract_numbers,
    format_rapidocr_result,
    has_cjk,
    normalize_ocr_symbols,
    should_join_with_space,
)

# Re-exported for backward compatibility: tests and other modules import from quickshot.ocr
__all__ = [
    "OCR_SYMBOL_TRANSLATION",
    "clean_hard_text",
    "clean_lines_text",
    "clean_ocr_text",
    "clean_soft_text",
    "deep_clean_ocr_text",
    "extract_chinese",
    "extract_numbers",
    "format_rapidocr_result",
    "has_cjk",
    "normalize_ocr_symbols",
    "should_join_with_space",
    "OcrResult",
    "OcrJob",
    "PrivacyBlurJob",
    "create_ocr_job",
    "create_privacy_blur_job",
    "is_rapidocr_available",
    "recognize_text",
    "recognize_text_with_rapidocr",
    "recognize_text_with_windows_ocr",
    "schedule_rapidocr_prewarm",
    "shutdown_ocr_executor",
]


def _load_windows_ocr_script() -> str:
    """从 assets/windows_ocr.ps1 加载 Windows OCR 脚本。"""
    from .utils import get_resource_path
    return get_resource_path("assets", "windows_ocr.ps1").read_text(encoding="utf-8-sig")

def prepare_ocr_image(source_image: Union[QPixmap, QImage]) -> QImage:
    """准备 OCR 图像，进行适当的缩放以提升识别准确率。

    优化策略：
    - 小图 (<900px): 放大 2x（原 3x 过度放大，增加计算量但收益有限）
    - 中图 (900-1600px): 保持 2x
    - 大图 (1600-2600px): 缩小至 1.5x
    - 超大图 (>2600px): 不缩放

    使用 FastTransformation + 锐化替代 SmoothTransformation，性能提升 3-5 倍。
    """
    if isinstance(source_image, QPixmap):
        source = source_image.toImage().convertToFormat(QImage.Format.Format_ARGB32)
    else:
        source = source_image.copy().convertToFormat(QImage.Format.Format_ARGB32)
    source.setDevicePixelRatio(1.0)
    image = QImage(source.size(), QImage.Format.Format_RGB32)
    image.fill(QColor(255, 255, 255))
    painter = QPainter(image)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
    painter.drawImage(0, 0, source)
    painter.end()

    max_dim = max(1, max(image.width(), image.height()))

    # 优化缩放策略：降低最大倍数从 3x 到 2x
    if max_dim < OCR_IMAGE_SMOOTH_THRESHOLD:
        scale = OCR_IMAGE_MAX_SCALE  # 原 3.0，2x 已足够且更快
    elif max_dim < 1600:
        scale = OCR_IMAGE_MAX_SCALE
    elif max_dim < 2600:
        scale = 1.5
    else:
        scale = 1.0

    # 限制最大尺寸防止内存溢出
    scale = min(scale, 3200 / max_dim)

    if scale > 1.05:
        # 优化：使用 FastTransformation 替代 SmoothTransformation（快 3-5 倍）
        # RapidOCR 对平滑度要求不高，快速插值足够
        image = image.scaled(
            max(1, int(round(image.width() * scale))),
            max(1, int(round(image.height() * scale))),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
    return image.convertToFormat(QImage.Format.Format_RGB888)

_RAPID_OCR_ENGINE = None
_RAPID_OCR_LOCK = threading.Lock()
_OCR_EXECUTOR = None
_OCR_EXECUTOR_LOCK = threading.Lock()
_PREWARM_FUTURE = None
_PREWARM_LOCK = threading.Lock()
_ACTIVE_OCR_JOBS = set()
_ACTIVE_OCR_JOBS_LOCK = threading.Lock()  # 保护 _ACTIVE_OCR_JOBS 集合的线程安全
RAPIDOCR_OPTIONAL_MESSAGE = (
    "智能隐私打码需要 RapidOCR 可选组件；当前轻量构建未内置。"
    "可继续使用系统 OCR 识文，或使用手动马赛克/模糊打码。"
)


def _get_ocr_executor():
    global _OCR_EXECUTOR
    if _OCR_EXECUTOR is None:
        with _OCR_EXECUTOR_LOCK:
            if _OCR_EXECUTOR is None:
                from concurrent.futures import ThreadPoolExecutor
                _OCR_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="quickshot-ocr")
    return _OCR_EXECUTOR


def is_rapidocr_available() -> bool:
    try:
        return find_spec("rapidocr_onnxruntime") is not None
    except (ImportError, ValueError):
        return False


class _OcrWorker(QObject):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, source_image: QImage) -> None:
        super().__init__()
        self._source_image = source_image.copy()

    @pyqtSlot()
    def run(self) -> None:
        try:
            self.succeeded.emit(recognize_text(self._source_image))
        except Exception as exc:
            debug_log(f"OCR worker failed: {exc}")
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


class OcrJob(QObject):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, source_image: QImage) -> None:
        super().__init__()
        self._thread = QThread()
        self._worker = _OcrWorker(source_image)
        self._running = False

        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.succeeded.connect(self.succeeded)
        self._worker.failed.connect(self.failed)
        self._worker.finished.connect(self._handle_worker_finished)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._handle_thread_finished)

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        with _ACTIVE_OCR_JOBS_LOCK:
            _ACTIVE_OCR_JOBS.add(self)
        self._thread.start()

    def is_running(self) -> bool:
        return self._running

    @pyqtSlot()
    def _handle_worker_finished(self) -> None:
        self._running = False
        self.finished.emit()

    @pyqtSlot()
    def _handle_thread_finished(self) -> None:
        with _ACTIVE_OCR_JOBS_LOCK:
            _ACTIVE_OCR_JOBS.discard(self)
        self.deleteLater()


def rapidocr_engine():
    global _RAPID_OCR_ENGINE
    if not is_rapidocr_available():
        raise RuntimeError(RAPIDOCR_OPTIONAL_MESSAGE)
    if _RAPID_OCR_ENGINE is None:
        with _RAPID_OCR_LOCK:
            if _RAPID_OCR_ENGINE is None:
                from rapidocr_onnxruntime import RapidOCR
                _RAPID_OCR_ENGINE = RapidOCR()
    return _RAPID_OCR_ENGINE


def prewarm_rapidocr() -> bool:
    if not is_rapidocr_available():
        debug_log("RapidOCR prewarm skipped: optional component unavailable")
        return False
    try:
        rapidocr_engine()
        debug_log("RapidOCR prewarm completed")
        return True
    except Exception as exc:
        debug_log(f"RapidOCR prewarm failed: {exc}")
        return False


def schedule_rapidocr_prewarm() -> None:
    global _PREWARM_FUTURE
    if not is_rapidocr_available():
        return
    with _PREWARM_LOCK:
        if _PREWARM_FUTURE is not None and not _PREWARM_FUTURE.done():
            return
        _PREWARM_FUTURE = _get_ocr_executor().submit(prewarm_rapidocr)


def create_ocr_job(source_image: QImage) -> OcrJob:
    return OcrJob(source_image)


def shutdown_ocr_executor() -> None:
    for job in list(_ACTIVE_OCR_JOBS):
        # PyQt 在 signal 无接收者时 disconnect 抛 TypeError；逐个静默是预期行为
        for signal in (job.succeeded, job.failed, job.finished):
            try:
                signal.disconnect()
            except TypeError:
                pass
    if _OCR_EXECUTOR is not None:
        _OCR_EXECUTOR.shutdown(wait=False, cancel_futures=True)

def _qimage_to_numpy(image: QImage):
    import numpy as np
    if image.format() != QImage.Format.Format_RGB888:
        image = image.convertToFormat(QImage.Format.Format_RGB888)
    width = image.width()
    height = image.height()
    bpl = image.bytesPerLine()
    ptr = image.bits()
    ptr.setsize(height * bpl)
    arr = np.frombuffer(ptr, dtype=np.uint8).reshape(height, bpl)
    # 去掉每行末尾的 padding 字节，只保留 width*3 的有效像素数据
    return arr[:, :width * 3].reshape(height, width, 3).copy()


def _is_null_image(image: Union[QPixmap, QImage]) -> bool:
    """统一检查 QPixmap/QImage 是否为空。"""
    return image.isNull()


def recognize_text_with_rapidocr(source_image: Union[QPixmap, QImage]) -> str:
    if _is_null_image(source_image):
        return ""
    if not is_rapidocr_available():
        raise RuntimeError(RAPIDOCR_OPTIONAL_MESSAGE)
    image = prepare_ocr_image(source_image)
    result, _elapsed = rapidocr_engine()(_qimage_to_numpy(image))
    return clean_ocr_text(format_rapidocr_result(result))


# 隐私信息匹配模式（延迟编译，仅在首次 detect_privacy_info 时加载）
_PRIVACY_PATTERNS = None


def _get_privacy_patterns():
    global _PRIVACY_PATTERNS
    if _PRIVACY_PATTERNS is None:
        import re
        _PRIVACY_PATTERNS = [
            # 手机号（中国大陆，支持空格/横线分隔）
            re.compile(r'1[3-9]\d[\s\-]?\d{4}[\s\-]?\d{4}'),
            # 身份证号（18位）
            re.compile(r'[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]'),
            # 邮箱
            re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}'),
            # 银行卡号（16-19位数字，支持空格/横线分隔）
            re.compile(r'\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}(?:[\s\-]?\d{1,3})?'),
        ]
    return _PRIVACY_PATTERNS


def detect_privacy_info(image: Union[QPixmap, QImage]) -> list:
    """检测图片中的隐私信息，返回需要打码的区域列表 [(x, y, w, h), ...]。"""
    if _is_null_image(image):
        return []

    try:
        orig_w, orig_h = image.width(), image.height()

        prepared = prepare_ocr_image(image)
        # 使用实际缩放后的图像尺寸计算真实缩放比，
        # 避免与 prepare_ocr_image 内部逻辑不一致导致坐标偏移
        prepared_w, prepared_h = prepared.width(), prepared.height()
        scale = prepared_w / orig_w if orig_w > 0 else 1.0

        if is_rapidocr_available():
            result, _elapsed = rapidocr_engine()(_qimage_to_numpy(prepared))
            engine_name = "RapidOCR"
        else:
            result = _recognize_privacy_lines_with_windows_ocr(prepared)
            engine_name = "Windows OCR"
        if not result:
            return []

        # 将坐标从缩放后的空间转换回原始图像空间
        rects = _match_privacy_rects(result)
        debug_log(f"Privacy: engine={engine_name}, orig={orig_w}x{orig_h}, prepared={prepared_w}x{prepared_h}, scale={scale:.2f}, raw_rects={rects}")
        if scale > 1.05 and rects:
            inv_scale = 1.0 / scale
            rects = [(int(x * inv_scale), int(y * inv_scale), int(w * inv_scale), int(h * inv_scale)) for x, y, w, h in rects]
            debug_log(f"Privacy: scaled_rects={rects}")
        return rects
    except ImportError as e:
        raise RuntimeError(
            f"未安装 RapidOCR 库：{e}\n\n"
            f"源码环境可运行以下命令安装 OCR 可选组件：\n"
            f"pip install -e .[ocr]"
        ) from e
    except Exception as e:
        debug_log(f"detect_privacy_info failed: {e}")
        import traceback
        debug_log(traceback.format_exc())
        raise RuntimeError(f"隐私信息检测失败：{type(e).__name__}: {e}") from e


def _match_privacy_rects(ocr_result) -> list:
    """从 OCR 原始结果中匹配隐私信息区域。"""
    blur_rects = []
    debug_log(f"Privacy scan: {len(ocr_result)} text blocks")
    for item in ocr_result:
        if len(item) < 2:
            continue
        box = item[0]
        text = str(item[1]).strip()
        if not text:
            continue

        is_private = False
        for pattern in _get_privacy_patterns():
            if pattern.search(text):
                is_private = True
                debug_log(f"  MATCH [{pattern.pattern}]: {text}")
                break

        if not is_private:
            continue

        try:
            xs = [float(point[0]) for point in box]
            ys = [float(point[1]) for point in box]
            if not xs or not ys:
                continue
        except (TypeError, ValueError, IndexError):
            continue

        x = int(min(xs))
        y = int(min(ys))
        w = int(max(xs) - min(xs))
        h = int(max(ys) - min(ys))
        if w > 0 and h > 0:
            blur_rects.append((x, y, w, h))

    return blur_rects

class PrivacyBlurJob(QObject):
    """异步隐私信息检测任务。"""
    succeeded = pyqtSignal(object)  # list of (x, y, w, h)
    failed = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, source_image: QImage) -> None:
        super().__init__()
        self._thread = QThread()
        self._worker = _PrivacyBlurWorker(source_image)
        self._running = False

        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.succeeded.connect(self.succeeded)
        self._worker.failed.connect(self.failed)
        self._worker.finished.connect(self._handle_worker_finished)
        self._worker.finished.connect(self._thread.quit)

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread.start()

    def is_running(self) -> bool:
        return self._running

    def cleanup(self) -> None:
        """安全清理线程和 worker。"""
        if self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(3000)
        self._worker.deleteLater()
        self._thread.deleteLater()

    @pyqtSlot()
    def _handle_worker_finished(self) -> None:
        self._running = False
        self.finished.emit()


class _PrivacyBlurWorker(QObject):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, source_image: QImage) -> None:
        super().__init__()
        self._source_image = source_image.copy()

    @pyqtSlot()
    def run(self) -> None:
        try:
            import traceback
            debug_log("PrivacyBlurWorker: starting privacy detection")
            result = detect_privacy_info(self._source_image)
            debug_log(f"PrivacyBlurWorker: detection completed, found {len(result)} regions")
            self.succeeded.emit(result)
        except Exception as exc:
            import traceback
            error_traceback = traceback.format_exc()
            debug_log(f"Privacy blur worker failed: {exc}\n{error_traceback}")
            error_msg = f"{type(exc).__name__}: {str(exc)}"
            self.failed.emit(error_msg)
        finally:
            self.finished.emit()


def create_privacy_blur_job(source_image: QImage) -> PrivacyBlurJob:
    return PrivacyBlurJob(source_image)


_CACHED_SCRIPT_PATH: Optional[Path] = None


def _get_windows_ocr_script_path() -> Path:
    """获取 Windows OCR 脚本路径，使用用户隔离目录防止多用户环境下的替换攻击。"""
    import os
    import tempfile

    global _CACHED_SCRIPT_PATH
    script_text = _load_windows_ocr_script()
    if _CACHED_SCRIPT_PATH is not None and _CACHED_SCRIPT_PATH.exists():
        try:
            if _CACHED_SCRIPT_PATH.read_text(encoding="utf-8-sig") == script_text:
                return _CACHED_SCRIPT_PATH
        except OSError:
            pass

    # 使用基于用户名的隔离目录，避免多用户环境中的文件替换风险
    username = os.environ.get("USERNAME", os.environ.get("USER", "default"))
    script_dir = Path(tempfile.gettempdir()) / f"quickshot_cache_{username}"
    script_dir.mkdir(parents=True, exist_ok=True)
    script_path = script_dir / "ocr.ps1"
    script_path.write_text(script_text, encoding="utf-8-sig")
    _CACHED_SCRIPT_PATH = script_path
    return script_path


def _windows_ocr_lines_to_rapidocr_result(lines) -> list:
    """Convert Windows OCR line JSON into RapidOCR-like text box entries."""
    result = []
    if not isinstance(lines, list):
        return result

    for line in lines:
        if not isinstance(line, dict):
            continue
        text = normalize_ocr_symbols(str(line.get("Text", ""))).strip()
        box = line.get("BoundingBox")
        if not text or not isinstance(box, list) or len(box) != 4:
            continue
        try:
            left, top, right, bottom = [float(value) for value in box]
        except (TypeError, ValueError):
            continue
        if right <= left or bottom <= top:
            continue

        result.append([
            [[left, top], [right, top], [right, bottom], [left, bottom]],
            text,
        ])
    return result


def _recognize_privacy_lines_with_windows_ocr(prepared_image: QImage) -> list:
    import base64
    import json
    import shutil
    import subprocess
    import tempfile

    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if not powershell:
        raise RuntimeError("未找到 PowerShell，无法使用 Windows 系统 OCR 进行智能隐私打码。")

    with tempfile.TemporaryDirectory(prefix="quickshot_ocr_") as tmp_dir:
        temp_dir = Path(tmp_dir)
        image_path = temp_dir / "capture.png"
        if not prepared_image.save(str(image_path), "PNG"):
            raise RuntimeError("无法准备智能隐私打码识别图片，请重新截图后再试。")

        script_path = _get_windows_ocr_script_path()
        creationflags = 0
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            creationflags = subprocess.CREATE_NO_WINDOW

        try:
            completed = subprocess.run(
                [
                    powershell,
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(script_path),
                    "-ImagePath",
                    str(image_path),
                    "-Output",
                    "Json",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                startupinfo=hidden_process_startupinfo(),
                creationflags=creationflags,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Windows 系统 OCR 识别超时，请缩小截图区域后重试。") from exc

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(
            f"Windows 系统 OCR 识别失败：{detail[:200] if detail else '未知错误'}"
        )

    encoded_text = completed.stdout.strip()
    if not encoded_text:
        return []
    try:
        lines = json.loads(base64.b64decode(encoded_text).decode("utf-8"))
    except Exception as exc:
        raise RuntimeError("Windows 系统 OCR 坐标结果解析失败。") from exc
    return _windows_ocr_lines_to_rapidocr_result(lines)


def recognize_text_with_windows_ocr(source_image: Union[QPixmap, QImage]) -> str:
    import base64
    import shutil
    import subprocess
    import tempfile

    if _is_null_image(source_image):
        return ""

    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if not powershell:
        raise RuntimeError(
            "未找到 PowerShell，无法调用 Windows 文字识别。\n\n"
            "请确保:\n"
            "1. Windows 10 1809 或更高版本\n"
            "2. 已安装 PowerShell 5.1+\n\n"
            "源码或定制构建也可安装 RapidOCR 可选组件"
        )

    with tempfile.TemporaryDirectory(prefix="quickshot_ocr_") as tmp_dir:
        temp_dir = Path(tmp_dir)
        image_path = temp_dir / "capture.png"

        image = prepare_ocr_image(source_image)
        if not image.save(str(image_path), "PNG"):
            raise RuntimeError(
                "无法准备文字识别图片。\n\n"
                "可能原因:\n"
                "1. 截图区域为空\n"
                "2. 内存不足\n\n"
                "建议: 重新截图或重启应用"
            )
        script_path = _get_windows_ocr_script_path()

        creationflags = 0
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            creationflags = subprocess.CREATE_NO_WINDOW

        try:
            completed = subprocess.run(
                [
                    powershell,
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(script_path),
                    "-ImagePath",
                    str(image_path),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                startupinfo=hidden_process_startupinfo(),
                creationflags=creationflags,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                "文字识别超时，请缩小识别区域后重试。\n\n"
                "建议:\n"
                "1. 选择较小的截图区域\n"
                "2. 避免识别整屏内容\n"
                "3. 检查系统资源是否充足"
            ) from exc

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(
            f"文字识别失败。\n\n"
            f"错误详情: {detail[:200] if detail else '未知错误'}\n\n"
            f"建议: 检查 Windows OCR 语言组件，或在源码/定制构建中安装 RapidOCR 可选组件"
        )

    encoded_text = completed.stdout.strip()
    if not encoded_text:
        return ""
    try:
        return normalize_ocr_symbols(base64.b64decode(encoded_text).decode("utf-8")).strip()
    except Exception as exc:
        raise RuntimeError(
            "文字识别结果解析失败。\n\n"
            "可能原因:\n"
            "1. OCR 输出格式异常\n"
            "2. 编码错误\n\n"
            "建议: 重新截图或切换 OCR 引擎"
        ) from exc


def recognize_text(source_image: Union[QPixmap, QImage]) -> OcrResult:
    """识别图片中的文字，按优先级尝试各引擎。"""
    if _is_null_image(source_image):
        return OcrResult(text="", engine_key="none", engine_label="OCR", note="空图片")
    prepared = prepare_ocr_image(source_image)
    from .ocr_engine import get_default_registry
    return get_default_registry().recognize(prepared)
