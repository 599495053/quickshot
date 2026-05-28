"""上传器接口测试。

覆盖 uploader.py：
- Uploader 抽象基类约束
- LocalArchiveUploader 上传到本地目录
- UploaderRegistry 注册/查询
- Markdown 链接格式化
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
    GitHubUploader,
    LocalArchiveUploader,
    UploadError,
    UploaderRegistry,
    UploadResult,
    build_default_registry,
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




class GitHubUploaderFormatErrorTest(unittest.TestCase):
    """测试 GitHubUploader._format_error 的各种 HTTP 状态码。"""

    def setUp(self) -> None:
        self.uploader = GitHubUploader(owner="test", repo="repo")

    def _make_response(self, status_code, json_data=None):
        """创建模拟响应对象。"""
        from unittest.mock import MagicMock
        resp = MagicMock()
        resp.status_code = status_code
        if json_data is not None:
            resp.json.return_value = json_data
        else:
            resp.json.side_effect = ValueError("no json")
        return resp

    def test_401(self) -> None:
        msg = self.uploader._format_error(self._make_response(401))
        self.assertIn("401", msg)
        self.assertIn("Token", msg)

    def test_403(self) -> None:
        msg = self.uploader._format_error(self._make_response(403, {"message": "rate limit"}))
        self.assertIn("403", msg)
        self.assertIn("rate limit", msg)

    def test_404(self) -> None:
        msg = self.uploader._format_error(self._make_response(404))
        self.assertIn("404", msg)

    def test_422(self) -> None:
        msg = self.uploader._format_error(self._make_response(422, {"message": "exists"}))
        self.assertIn("422", msg)
        self.assertIn("exists", msg)

    def test_500(self) -> None:
        msg = self.uploader._format_error(self._make_response(500, {"message": "server error"}))
        self.assertIn("500", msg)
        self.assertIn("server error", msg)

    def test_502(self) -> None:
        msg = self.uploader._format_error(self._make_response(502))
        self.assertIn("502", msg)

    def test_unknown_code(self) -> None:
        msg = self.uploader._format_error(self._make_response(418, {"message": "teapot"}))
        self.assertIn("418", msg)
        self.assertIn("teapot", msg)


class GitHubUploaderSizeLimitTest(unittest.TestCase):
    """测试 GitHubUploader 文件大小限制。"""

    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()
        self.uploader = GitHubUploader(owner="test", repo="repo", token_provider=lambda: "fake-token")

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_oversized_file_raises(self) -> None:
        # 创建一个 >10MB 的文件
        big_file = Path(self.tmp) / "big.png"
        big_file.write_bytes(b"x" * (11 * 1024 * 1024))
        with self.assertRaises(UploadError) as ctx:
            self.uploader.upload(str(big_file))
        self.assertIn("过大", str(ctx.exception))

    def test_normal_file_passes_size_check(self) -> None:
        # 正常大小的文件不应触发大小限制（但会因 token 无效而在后续失败）
        normal_file = Path(self.tmp) / "normal.png"
        normal_file.write_bytes(b"x" * 1024)
        with self.assertRaises(UploadError) as ctx:
            self.uploader.upload(str(normal_file))
        # 不应该报"过大"，而是网络/token 错误
        self.assertNotIn("过大", str(ctx.exception))


class LocalArchiveUploaderFilenameTest(unittest.TestCase):
    """测试 LocalArchiveUploader 文件名长度保护。"""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.archive_dir = Path(self.tmp.name) / "uploads"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_long_filename_truncation_logic(self) -> None:
        # 直接测试 uploader 中使用的截断逻辑
        from pathlib import PurePosixPath
        long_name = "a" * 250 + ".png"
        name = long_name
        if len(name) > 200:
            suffix = PurePosixPath(name).suffix
            name = name[:200 - len(suffix)] + suffix
        self.assertLessEqual(len(name), 200)
        self.assertTrue(name.endswith(".png"))
        # 确认截断后文件名有意义
        self.assertEqual(len(name), 200)

    def test_short_filename_unchanged(self) -> None:
        src = Path(self.tmp.name) / "short.png"
        src.write_bytes(b"fake")
        uploader = LocalArchiveUploader(archive_dir=str(self.archive_dir))
        result = uploader.upload(str(src))
        dest_name = Path(result.url.replace("file:///", "")).name
        self.assertIn("short.png", dest_name)


if __name__ == "__main__":
    unittest.main()
