import ctypes
import sys
from typing import Optional, Tuple

from PyQt6.QtCore import QRect
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QApplication

from .utils import debug_log, pixmap_from_mss, pixmap_from_rgb_array, pixmap_from_sc_rgb_frame


_CAPTURE_PREWARMED = False

# ── ctypes 结构体定义（模块级，避免每次调用重复定义）──
if sys.platform.startswith("win"):
    from ctypes import wintypes as _wintypes

    class _LUID(ctypes.Structure):
        _fields_ = [("LowPart", _wintypes.DWORD), ("HighPart", _wintypes.LONG)]

    class _DISPLAYCONFIG_RATIONAL(ctypes.Structure):
        _fields_ = [("Numerator", _wintypes.UINT), ("Denominator", _wintypes.UINT)]

    class _DISPLAYCONFIG_PATH_SOURCE_INFO(ctypes.Structure):
        _fields_ = [
            ("adapterId", _LUID),
            ("id", _wintypes.UINT),
            ("modeInfoIdx", _wintypes.UINT),
            ("statusFlags", _wintypes.UINT),
        ]

    class _DISPLAYCONFIG_PATH_TARGET_INFO(ctypes.Structure):
        _fields_ = [
            ("adapterId", _LUID),
            ("id", _wintypes.UINT),
            ("modeInfoIdx", _wintypes.UINT),
            ("outputTechnology", _wintypes.UINT),
            ("rotation", _wintypes.UINT),
            ("scaling", _wintypes.UINT),
            ("refreshRate", _DISPLAYCONFIG_RATIONAL),
            ("scanLineOrdering", _wintypes.UINT),
            ("targetAvailable", _wintypes.BOOL),
            ("statusFlags", _wintypes.UINT),
        ]

    class _DISPLAYCONFIG_PATH_INFO(ctypes.Structure):
        _fields_ = [
            ("sourceInfo", _DISPLAYCONFIG_PATH_SOURCE_INFO),
            ("targetInfo", _DISPLAYCONFIG_PATH_TARGET_INFO),
            ("flags", _wintypes.UINT),
        ]

    class _DISPLAYCONFIG_MODE_INFO(ctypes.Structure):
        _fields_ = [("data", ctypes.c_byte * 64)]

    class _DISPLAYCONFIG_DEVICE_INFO_HEADER(ctypes.Structure):
        _fields_ = [
            ("type", _wintypes.UINT),
            ("size", _wintypes.UINT),
            ("adapterId", _LUID),
            ("id", _wintypes.UINT),
        ]

    class _DISPLAYCONFIG_SDR_WHITE_LEVEL(ctypes.Structure):
        _fields_ = [
            ("header", _DISPLAYCONFIG_DEVICE_INFO_HEADER),
            ("SDRWhiteLevel", _wintypes.ULONG),
        ]

# ── SDR white scale 缓存（显示器配置不频繁变化）──
_SDR_WHITE_SCALE_CACHE: float = -1.0

# ── qt_virtual_geometry 缓存 ──
_VIRTUAL_GEOMETRY_CACHE: Optional[QRect] = None


def schedule_capture_prewarm() -> None:
    """主线程同步预热截图后端 import，消除首次截图 ~600ms 冷启动延迟。
    Why: winrt.windows.graphics.capture / dxcam 都依赖 WinRT COM apartment，
    必须在最终使用它们的主线程 import，子线程预热会污染 COM 状态导致 0xC0000005。"""
    global _CAPTURE_PREWARMED
    if _CAPTURE_PREWARMED:
        return
    _CAPTURE_PREWARMED = True
    try:
        import numpy  # noqa: F401
        import dxcam  # noqa: F401
        from dxcam._libs.d3d11 import (  # noqa: F401
            D3D11_CPU_ACCESS_READ,
            D3D11_TEXTURE2D_DESC,
            D3D11_USAGE_STAGING,
            ID3D11Texture2D,
        )
        from dxcam._libs.dxgi import DXGI_MAPPED_RECT, IDXGIDevice, IDXGISurface  # noqa: F401
        from winrt.windows.graphics.capture import Direct3D11CaptureFramePool  # noqa: F401
        from winrt.windows.graphics.capture import interop as capture_interop  # noqa: F401
        from winrt.windows.graphics.directx import DirectXPixelFormat  # noqa: F401
        from winrt.windows.graphics.directx.direct3d11 import interop as d3d11_interop  # noqa: F401
        debug_log("capture imports prewarmed (main thread)")
    except Exception as exc:
        debug_log(f"capture prewarm failed: {exc}")


def _invalidate_virtual_geometry_cache() -> None:
    global _VIRTUAL_GEOMETRY_CACHE
    _VIRTUAL_GEOMETRY_CACHE = None


def qt_virtual_geometry() -> QRect:
    global _VIRTUAL_GEOMETRY_CACHE
    if _VIRTUAL_GEOMETRY_CACHE is not None:
        return _VIRTUAL_GEOMETRY_CACHE
    app = QApplication.instance()
    screens = app.screens() if app else []
    if not screens:
        return QRect(0, 0, 1, 1)

    geometry = QRect(screens[0].geometry())
    for screen in screens[1:]:
        geometry = geometry.united(screen.geometry())
    if geometry.width() <= 0 or geometry.height() <= 0:
        return QRect(0, 0, 1, 1)
    _VIRTUAL_GEOMETRY_CACHE = geometry
    return geometry


def _setup_geometry_cache_invalidation() -> None:
    """监听屏幕变化信号，自动失效虚拟几何缓存。"""
    app = QApplication.instance()
    if app is not None:
        try:
            app.screenAdded.connect(lambda: _invalidate_virtual_geometry_cache())
            app.screenRemoved.connect(lambda: _invalidate_virtual_geometry_cache())
        except Exception:
            pass


def _get_primary_sdr_white_scale() -> float:
    global _SDR_WHITE_SCALE_CACHE
    if _SDR_WHITE_SCALE_CACHE >= 0.0:
        return _SDR_WHITE_SCALE_CACHE
    if not sys.platform.startswith("win"):
        _SDR_WHITE_SCALE_CACHE = 0.0
        return 0.0

    try:
        qdc_only_active_paths = 0x00000002
        get_sdr_white_level = 11
        user32 = ctypes.windll.user32
        path_count = _wintypes.UINT()
        mode_count = _wintypes.UINT()
        if user32.GetDisplayConfigBufferSizes(qdc_only_active_paths, ctypes.byref(path_count), ctypes.byref(mode_count)) != 0:
            _SDR_WHITE_SCALE_CACHE = 0.0
            return 0.0
        paths = (_DISPLAYCONFIG_PATH_INFO * max(1, path_count.value))()
        modes = (_DISPLAYCONFIG_MODE_INFO * max(1, mode_count.value))()
        if user32.QueryDisplayConfig(
            qdc_only_active_paths,
            ctypes.byref(path_count),
            paths,
            ctypes.byref(mode_count),
            modes,
            None,
        ) != 0:
            _SDR_WHITE_SCALE_CACHE = 0.0
            return 0.0
        if path_count.value <= 0:
            _SDR_WHITE_SCALE_CACHE = 0.0
            return 0.0

        white = _DISPLAYCONFIG_SDR_WHITE_LEVEL()
        white.header.type = get_sdr_white_level
        white.header.size = ctypes.sizeof(white)
        white.header.adapterId = paths[0].targetInfo.adapterId
        white.header.id = paths[0].targetInfo.id
        if user32.DisplayConfigGetDeviceInfo(ctypes.byref(white.header)) != 0:
            _SDR_WHITE_SCALE_CACHE = 0.0
            return 0.0
        scale = float(white.SDRWhiteLevel) / 1000.0
        if scale <= 0.0:
            _SDR_WHITE_SCALE_CACHE = 0.0
            return 0.0
        _SDR_WHITE_SCALE_CACHE = scale
        return scale
    except Exception as exc:
        debug_log(f"SDR white level unavailable: {exc}")
        _SDR_WHITE_SCALE_CACHE = 0.0
        return 0.0


def _grab_virtual_screen_with_wgc_hdr() -> Optional[Tuple[QPixmap, int, int]]:
    if not sys.platform.startswith("win"):
        return None

    try:
        import time

        import dxcam
        import numpy as np
        from dxcam._libs.d3d11 import (
            D3D11_CPU_ACCESS_READ,
            D3D11_TEXTURE2D_DESC,
            D3D11_USAGE_STAGING,
            ID3D11Texture2D,
        )
        from dxcam._libs.dxgi import DXGI_MAPPED_RECT, IDXGIDevice, IDXGISurface
        from winrt.windows.graphics.capture import Direct3D11CaptureFramePool
        from winrt.windows.graphics.capture import interop as capture_interop
        from winrt.windows.graphics.directx import DirectXPixelFormat
        from winrt.windows.graphics.directx.direct3d11 import interop as d3d11_interop
    except Exception as exc:
        debug_log(f"WGC HDR capture unavailable: {exc}")
        return None

    factory = getattr(dxcam, "__factory", None)
    if factory is None:
        debug_log("WGC HDR capture unavailable: dxcam factory missing")
        return None

    frame_pool = None
    session = None
    frame = None
    staging = None
    staging_surface = None
    mapped = False

    try:
        device = factory.devices[0]
        output = factory.outputs[0][0]
        output.update_desc()

        dxgi_device = device.device.QueryInterface(IDXGIDevice)
        dxgi_device_ptr = ctypes.cast(dxgi_device, ctypes.c_void_p).value
        if dxgi_device_ptr is None:
            return None
        winrt_device = d3d11_interop.create_direct3d11_device_from_dxgi_device(dxgi_device_ptr)

        monitor = int(getattr(output.hmonitor, "value", output.hmonitor))
        capture_item = capture_interop.create_for_monitor(monitor)
        frame_pool = Direct3D11CaptureFramePool.create_free_threaded(
            winrt_device,
            DirectXPixelFormat.R16_G16_B16_A16_FLOAT,
            2,
            capture_item.size,
        )
        session = frame_pool.create_capture_session(capture_item)
        session.start_capture()

        for _ in range(20):
            frame = frame_pool.try_get_next_frame()
            if frame is not None:
                break
            time.sleep(0.015)
        if frame is None:
            debug_log("WGC HDR capture returned no frame")
            return None

        surface_ptr = d3d11_interop.get_dxgi_surface_from_object(frame.surface)
        if not surface_ptr:
            return None
        surface = ctypes.cast(surface_ptr, ctypes.POINTER(IDXGISurface))
        texture = surface.QueryInterface(ID3D11Texture2D)

        desc = D3D11_TEXTURE2D_DESC()
        texture.GetDesc(ctypes.byref(desc))
        if int(desc.Format) != 10:
            debug_log(f"WGC HDR capture unexpected format: {int(desc.Format)}")
            return None

        staging_desc = D3D11_TEXTURE2D_DESC()
        staging_desc.Width = desc.Width
        staging_desc.Height = desc.Height
        staging_desc.MipLevels = 1
        staging_desc.ArraySize = 1
        staging_desc.Format = desc.Format
        staging_desc.SampleDesc.Count = 1
        staging_desc.SampleDesc.Quality = 0
        staging_desc.Usage = D3D11_USAGE_STAGING
        staging_desc.BindFlags = 0
        staging_desc.CPUAccessFlags = D3D11_CPU_ACCESS_READ
        staging_desc.MiscFlags = 0

        staging = ctypes.POINTER(ID3D11Texture2D)()
        device.device.CreateTexture2D(ctypes.byref(staging_desc), None, ctypes.byref(staging))
        device.im_context.CopyResource(staging, texture)

        staging_surface = staging.QueryInterface(IDXGISurface)
        rect = DXGI_MAPPED_RECT()
        staging_surface.Map(ctypes.byref(rect), 1)
        mapped = True
        pitch = int(rect.Pitch)
        width = int(desc.Width)
        height = int(desc.Height)
        row_bytes = width * 8
        if pitch < row_bytes:
            debug_log(f"WGC HDR capture invalid pitch: pitch={pitch} row={row_bytes}")
            return None

        ptr = ctypes.cast(rect.pBits, ctypes.POINTER(ctypes.c_ubyte))
        raw = np.ctypeslib.as_array(ptr, shape=(pitch * height,))
        rows = raw.reshape(height, pitch)[:, :row_bytes]
        sc_rgb = rows.reshape(height, width, 8).view(np.float16).astype(np.float32)
        pixmap = pixmap_from_sc_rgb_frame(sc_rgb, _get_primary_sdr_white_scale())
        if pixmap.isNull():
            return None
        debug_log(f"WGC HDR capture: raw={pixmap.width()}x{pixmap.height()}")
        return pixmap, 0, 0
    except Exception as exc:
        debug_log(f"WGC HDR capture failed: {exc}")
        return None
    finally:
        if mapped and staging_surface is not None:
            try:
                staging_surface.Unmap()
            except Exception as exc:
                debug_log(f"WGC HDR unmap failed: {exc}")
        if staging is not None:
            try:
                staging.Release()
            except Exception as exc:
                debug_log(f"WGC HDR staging release failed: {exc}")
        if frame is not None:
            try:
                frame.close()
            except Exception as exc:
                debug_log(f"WGC HDR frame close failed: {exc}")
        if session is not None:
            try:
                session.close()
            except Exception as exc:
                debug_log(f"WGC HDR session close failed: {exc}")
        if frame_pool is not None:
            try:
                frame_pool.close()
            except Exception as exc:
                debug_log(f"WGC HDR frame pool close failed: {exc}")


_DXCAM_CAMERA = None
_DXCAM_BACKEND = None


def _grab_virtual_screen_with_dxcam(prefer_dxgi: bool = False, hdr_desktop: bool = False, sdr_white_scale: float = 0.0) -> Optional[Tuple[QPixmap, int, int]]:
    global _DXCAM_CAMERA, _DXCAM_BACKEND
    try:
        import dxcam
    except Exception as exc:
        debug_log(f"dxcam unavailable: {exc}")
        return None

    # dxcam 的 winrt 后端走 Windows Graphics Capture，HDR 桌面下会触发金色录制边框；
    # dxgi 后端走 Desktop Duplication，无边框但 HDR 内容会被默认色调映射成 SDR 过亮帧
    backends = ("dxgi", "winrt") if prefer_dxgi else ("winrt", "dxgi")
    for backend in backends:
        camera = None
        try:
            # 复用已缓存的 camera 对象（避免每次 50-200ms 的 D3D11 初始化）
            if _DXCAM_CAMERA is not None and _DXCAM_BACKEND == backend:
                camera = _DXCAM_CAMERA
            else:
                # 释放旧 camera
                if _DXCAM_CAMERA is not None:
                    try:
                        _DXCAM_CAMERA.release()
                    except Exception:
                        pass
                    _DXCAM_CAMERA = None
                camera = dxcam.create(output_color="RGB", backend=backend)
                _DXCAM_CAMERA = camera
                _DXCAM_BACKEND = backend
            frame = camera.grab()
            if frame is None:
                debug_log(f"dxcam {backend} returned no frame")
                continue
            # 只有 dxgi 后端 + HDR 桌面才需要 LUT 兜底；winrt 后端帧已被 Windows 处理过
            scale = sdr_white_scale if (backend == "dxgi" and hdr_desktop) else 0.0
            pixmap = pixmap_from_rgb_array(frame, sdr_white_scale=scale)
            debug_log(f"dxcam {backend} capture: raw={pixmap.width()}x{pixmap.height()} hdr_fix={scale > 0}")
            return pixmap, 0, 0
        except Exception as exc:
            debug_log(f"dxcam {backend} capture failed: {exc}")
            # 出错时释放 camera，下次重建
            if camera is _DXCAM_CAMERA:
                _DXCAM_CAMERA = None
            if camera is not None:
                try:
                    camera.release()
                except Exception:
                    pass
    return None


_GEOMETRY_INVALIDATION_SETUP = False
_MSS_INSTANCE = None


def grab_virtual_screen(hdr_color_accurate: bool = False) -> Tuple[QPixmap, QPixmap, QRect, float, float, int, int]:
    """抓取虚拟桌面，并建立 Qt 逻辑像素与 mss 物理像素的映射。

    hdr_color_accurate=True 时优先 WGC HDR（色彩物理正确，但 Windows 会画金色录制边框）；
    False（默认）时走 mss（GDI 抓屏，不受 HDR 色调映射影响）。"""
    global _GEOMETRY_INVALIDATION_SETUP
    if not _GEOMETRY_INVALIDATION_SETUP:
        _GEOMETRY_INVALIDATION_SETUP = True
        _setup_geometry_cache_invalidation()
    dx_capture = None
    if hdr_color_accurate:
        dx_capture = _grab_virtual_screen_with_wgc_hdr() or _grab_virtual_screen_with_dxcam()
    # hdr_color_accurate=False 时直接走 mss（GDI 抓屏，无金色边框）
    if dx_capture is not None:
        raw_pixmap, physical_left, physical_top = dx_capture
    else:
        global _MSS_INSTANCE
        import mss
        if _MSS_INSTANCE is None:
            try:
                _MSS_INSTANCE = mss.mss()
            except Exception as exc:
                debug_log(f"mss init failed: {exc}")
                _MSS_INSTANCE = mss.mss()
        sct = _MSS_INSTANCE
        monitor = sct.monitors[0]
        shot = sct.grab(monitor)
        raw_pixmap = pixmap_from_mss(shot)
        physical_left = int(monitor.get("left", 0))
        physical_top = int(monitor.get("top", 0))

    logical_geometry = qt_virtual_geometry()
    if logical_geometry.width() <= 0 or logical_geometry.height() <= 0:
        logical_geometry = QRect(0, 0, raw_pixmap.width(), raw_pixmap.height())

    scale_x = raw_pixmap.width() / max(1, logical_geometry.width())
    scale_y = raw_pixmap.height() / max(1, logical_geometry.height())

    display_pixmap = QPixmap(raw_pixmap)
    if abs(scale_x - scale_y) <= 0.02 and scale_x > 0:
        display_pixmap.setDevicePixelRatio(scale_x)
    else:
        display_pixmap.setDevicePixelRatio(1.0)
        debug_log(f"Mixed DPI detected: scale_x={scale_x:.4f}, scale_y={scale_y:.4f}")

    debug_log(
        f"Screen capture: raw={raw_pixmap.width()}x{raw_pixmap.height()}, "
        f"logical={logical_geometry.width()}x{logical_geometry.height()}, "
        f"scale=({scale_x:.3f}, {scale_y:.3f})"
    )

    return raw_pixmap, display_pixmap, logical_geometry, scale_x, scale_y, physical_left, physical_top


def get_foreground_window_rect() -> Optional[Tuple[int, int, int, int]]:
    if not sys.platform.startswith("win"):
        return None

    from ctypes import wintypes

    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None

    try:
        if not user32.IsWindowVisible(hwnd):
            return None
    except Exception as exc:
        debug_log(f"IsWindowVisible check failed: {exc}")

    rect = wintypes.RECT()
    ok = False

    try:
        dwmapi = ctypes.windll.dwmapi
        result = dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(rect), ctypes.sizeof(rect))
        ok = result == 0
    except Exception as exc:
        debug_log(f"DwmGetWindowAttribute failed: {exc}")
        ok = False

    if not ok:
        try:
            if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                return None
        except Exception as exc:
            debug_log(f"GetWindowRect failed: {exc}")
            return None

    left, top, right, bottom = int(rect.left), int(rect.top), int(rect.right), int(rect.bottom)
    width = right - left
    height = bottom - top
    if width < 8 or height < 8:
        return None
    return left, top, width, height
