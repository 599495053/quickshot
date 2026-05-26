"""Top-level launcher for QuickShot."""

from __future__ import annotations

import atexit
import ctypes
import sys


_MUTEX_HANDLE = None
_MUTEX_NAME = "Local\\QuickShotLauncherSingleton"
_ERROR_ALREADY_EXISTS = 183


def release_single_instance() -> None:
    global _MUTEX_HANDLE
    if _MUTEX_HANDLE is None or not sys.platform.startswith("win"):
        return
    try:
        ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(_MUTEX_HANDLE)
    except Exception:
        pass
    _MUTEX_HANDLE = None


def acquire_single_instance() -> bool:
    global _MUTEX_HANDLE
    if not sys.platform.startswith("win"):
        return True
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    mutex = kernel32.CreateMutexW(None, False, _MUTEX_NAME)
    if not mutex:
        return True
    if ctypes.get_last_error() == _ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(mutex)
        return False
    _MUTEX_HANDLE = mutex
    atexit.register(release_single_instance)
    return True


def run() -> None:
    if not acquire_single_instance():
        raise SystemExit(0)
    from quickshot.main import main

    main()


if __name__ == "__main__":
    run()
