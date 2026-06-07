"""Shared PyInstaller build settings."""

from fnmatch import fnmatch


EXCLUDED_MODULES = [
    "matplotlib",
    "pandas",
    "scipy",
    "skimage",
    "sklearn",
    "tensorflow",
    "torch",
    "tkinter",
    "IPython",
    "jupyter",
    "notebook",
    "pytest",
    "unittest",
    "unittest.mock",
    "doctest",
    "pydoc",
    "pdb",
    "http.server",
    "xmlrpc",
    "lib2to3",
    "setuptools",
    "pip",
    # 注意：不能排除 distutils。keyring/pywin32-ctypes 的 PyInstaller hook
    # 会尝试 alias distutils，若被 ExcludedModule 拦截会导致打包失败。
    "numpy.testing",
    "numpy.tests",
    "numpy._core.tests",
    "numpy.lib.tests",
    "numpy.ma.tests",
    "numpy.random.tests",
    "numpy.f2py",
    "numpy.distutils",
    "onnxruntime.backend",
    "onnxruntime.datasets",
    "onnxruntime.quantization",
    "onnxruntime.tools",
    "onnxruntime.training",
    "onnxruntime.transformers",
    "cv2.data",
    "cv2.samples",
]

EXCLUDED_BINARY_PATTERNS = [
    "cv2/opencv_videoio_ffmpeg*.dll",
    "numpy/_core/_multiarray_tests*.pyd",
    "PIL/_avif*.pyd",
    "PyQt6/Qt6/bin/Qt6Pdf.dll",
    "PyQt6/Qt6/bin/opengl32sw.dll",
]


def filter_binaries(entries):
    filtered = []
    for entry in entries:
        dest = str(entry[0]).replace("\\", "/")
        if any(fnmatch(dest, pattern.replace("\\", "/")) for pattern in EXCLUDED_BINARY_PATTERNS):
            continue
        filtered.append(entry)
    return filtered
