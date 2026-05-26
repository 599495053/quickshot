"""上传器接口测试。

覆盖 uploader.py：
- Uploader 抽象基类约束
- LocalArchiveUploader 上传到本地目录
- UploaderRegistry 注册/查询
- Markdown / HTML 链接格式化
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quickshot.uploader import (  # noqa: E402
    LocalArchiveUploader,
    UploadError,
    UploaderRegistry,
    UploadResult,
    build_default_registry,
    format_html_link,
    format_markdown_link,
)


class LocalArchiveUploaderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.archive_dir = Path(self.tmp.name) / "uploads"
        # 准备一个临时源文件
        self.src = Path(self.tmp.name) / "source.png"
        self.src.write_bytes(b"fake-png-bytes")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_identifier_and_name(self) -> None:
        self.assertEqual(LocalArchiveUploader.identifier(), "local")
        self.assertEqual(LocalArchiveUploader.display_name(), "本地存档")

    def test_is_configured_default(self) -> None:
        uploader = LocalArchiveUploader(archive_dir=str(self.archive_dir))
        self.assertTrue(uploader.is_configured())

    def test_upload_copies_file(self) -> None:
        uploader = LocalArchiveUploader(archive_dir=str(self.archive_dir))
        result = uploader.upload(str(self.src))
        self.assertIsInstance(result, UploadResult)
        self.assertTrue(result.url.startswith("file:"))
        # 目标目录里应有一个 .png 文件
        files = list(self.archive_dir.glob("*.png"))
        self.assertEqual(len(files), 1)

    def test_upload_missing_source_raises(self) -> None:
        uploader = LocalArchiveUploader(archive_dir=str(self.archive_dir))
        with self.assertRaises(UploadError):
            uploader.upload(str(Path(self.tmp.name) / "missing.png"))


class UploaderRegistryTest(unittest.TestCase):
    def test_register_and_get(self) -> None:
        registry = UploaderRegistry()
        uploader = LocalArchiveUploader(archive_dir=tempfile.gettempdir())
        registry.register(uploader)
        self.assertIs(registry.get("local"), uploader)

    def test_unregister(self) -> None:
        registry = UploaderRegistry()
        registry.register(LocalArchiveUploader(archive_dir=tempfile.gettempdir()))
        registry.unregister("local")
        self.assertIsNone(registry.get("local"))

    def test_identifiers_list(self) -> None:
        registry = UploaderRegistry()
        registry.register(LocalArchiveUploader(archive_dir=tempfile.gettempdir()))
        self.assertIn("local", registry.identifiers())

    def test_build_default_registry(self) -> None:
        registry = build_default_registry(archive_dir=tempfile.gettempdir())
        self.assertIsNotNone(registry.get("local"))


class LinkFormatTest(unittest.TestCase):
    def test_markdown_link(self) -> None:
        result = UploadResult(url="https://example.com/a.png", name="a.png")
        self.assertEqual(
            format_markdown_link(result),
            "![a.png](https://example.com/a.png)",
        )

    def test_markdown_link_custom_alt(self) -> None:
        result = UploadResult(url="https://example.com/a.png", name="a.png")
        self.assertEqual(
            format_markdown_link(result, alt_text="截图"),
            "![截图](https://example.com/a.png)",
        )

    def test_html_link(self) -> None:
        result = UploadResult(url="https://example.com/a.png", name="a.png")
        self.assertEqual(
            format_html_link(result),
            '<img src="https://example.com/a.png" alt="a.png" />',
        )


if __name__ == "__main__":
    unittest.main()
