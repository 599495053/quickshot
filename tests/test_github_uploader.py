"""GitHubUploader 测试（mock requests）。

覆盖：
- identifier / display_name
- is_configured 在不同配置组合下的判断
- 构造 remote 路径符合 prefix/year/month-day/{uuid}_{name}
- upload 成功生成正确 raw.githubusercontent.com URL
- 401 / 403 / 404 / 422 错误的友好提示
- 网络异常映射为 UploadError
- 缺 token / 缺 owner / 源文件不存在 的早期校验
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quickshot.uploader import (  # noqa: E402
    GitHubUploader,
    UploadError,
)


def _make_response(status_code: int, json_body=None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body or {}
    return resp


class GitHubUploaderMetaTest(unittest.TestCase):
    def test_identifier(self) -> None:
        self.assertEqual(GitHubUploader.identifier(), "github")

    def test_display_name(self) -> None:
        self.assertEqual(GitHubUploader.display_name(), "GitHub 仓库")


class GitHubUploaderConfigTest(unittest.TestCase):
    def test_is_configured_false_when_no_owner(self) -> None:
        u = GitHubUploader(owner="", repo="r", token_provider=lambda: "t")
        self.assertFalse(u.is_configured())

    def test_is_configured_false_when_no_repo(self) -> None:
        u = GitHubUploader(owner="o", repo="", token_provider=lambda: "t")
        self.assertFalse(u.is_configured())

    def test_is_configured_false_when_no_token(self) -> None:
        u = GitHubUploader(owner="o", repo="r", token_provider=lambda: "")
        self.assertFalse(u.is_configured())

    def test_is_configured_true(self) -> None:
        u = GitHubUploader(owner="o", repo="r", token_provider=lambda: "t")
        self.assertTrue(u.is_configured())

    def test_default_branch_is_main(self) -> None:
        u = GitHubUploader(owner="o", repo="r", branch="", token_provider=lambda: "t")
        self.assertEqual(u.branch, "main")

    def test_path_prefix_strips_slashes(self) -> None:
        u = GitHubUploader(owner="o", repo="r", path_prefix="/shots/", token_provider=lambda: "t")
        self.assertEqual(u.path_prefix, "shots")

    def test_token_provider_exception_returns_empty(self) -> None:
        def boom() -> str:
            raise RuntimeError("keyring down")
        u = GitHubUploader(owner="o", repo="r", token_provider=boom)
        self.assertFalse(u.is_configured())


class GitHubUploaderPathTest(unittest.TestCase):
    def test_build_remote_path_format(self) -> None:
        u = GitHubUploader(owner="o", repo="r", path_prefix="shots", token_provider=lambda: "t")
        path = u.build_remote_path("shot.png")
        parts = path.split("/")
        # shots/YYYY/MM-DD/{8hex}_shot.png
        self.assertEqual(parts[0], "shots")
        self.assertEqual(len(parts[1]), 4)  # 年份
        self.assertEqual(len(parts[2]), 5)  # MM-DD
        self.assertTrue(parts[3].endswith("_shot.png"))


class GitHubUploaderUploadTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.src = Path(self.tmp.name) / "shot.png"
        self.src.write_bytes(b"\x89PNG\r\n\x1a\n" + b"fake-data")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _uploader(self) -> GitHubUploader:
        return GitHubUploader(
            owner="alice",
            repo="screenshots",
            branch="main",
            path_prefix="shots",
            token_provider=lambda: "ghp_test",
        )

    def test_missing_source_file(self) -> None:
        u = self._uploader()
        with self.assertRaises(UploadError):
            u.upload(str(Path(self.tmp.name) / "missing.png"))

    def test_unconfigured_owner_raises(self) -> None:
        u = GitHubUploader(owner="", repo="r", token_provider=lambda: "t")
        with self.assertRaises(UploadError) as ctx:
            u.upload(str(self.src))
        self.assertIn("owner", str(ctx.exception))

    def test_unconfigured_token_raises(self) -> None:
        u = GitHubUploader(owner="o", repo="r", token_provider=lambda: "")
        with self.assertRaises(UploadError) as ctx:
            u.upload(str(self.src))
        self.assertIn("Token", str(ctx.exception))

    def test_success_returns_raw_url(self) -> None:
        u = self._uploader()
        with patch("requests.put", return_value=_make_response(201, {"content": {}})) as mock_put:
            result = u.upload(str(self.src))
        self.assertTrue(result.url.startswith("https://raw.githubusercontent.com/alice/screenshots/main/shots/"))
        self.assertTrue(result.url.endswith("_shot.png"))
        # 校验请求参数
        mock_put.assert_called_once()
        args, kwargs = mock_put.call_args
        self.assertIn("/repos/alice/screenshots/contents/shots/", args[0])
        body = kwargs["json"]
        self.assertEqual(body["branch"], "main")
        self.assertIn("content", body)  # base64 内容
        headers = kwargs["headers"]
        self.assertEqual(headers["Authorization"], "token ghp_test")

    def test_status_200_also_success(self) -> None:
        u = self._uploader()
        with patch("requests.put", return_value=_make_response(200, {})):
            result = u.upload(str(self.src))
        self.assertTrue(result.url.startswith("https://raw.githubusercontent.com/"))

    def test_401_unauthorized(self) -> None:
        u = self._uploader()
        with patch("requests.put", return_value=_make_response(401, {"message": "Bad credentials"})):
            with self.assertRaises(UploadError) as ctx:
                u.upload(str(self.src))
        self.assertIn("401", str(ctx.exception))

    def test_403_forbidden(self) -> None:
        u = self._uploader()
        with patch("requests.put", return_value=_make_response(403, {"message": "rate limited"})):
            with self.assertRaises(UploadError) as ctx:
                u.upload(str(self.src))
        self.assertIn("403", str(ctx.exception))

    def test_404_not_found(self) -> None:
        u = self._uploader()
        with patch("requests.put", return_value=_make_response(404, {"message": "Not Found"})):
            with self.assertRaises(UploadError) as ctx:
                u.upload(str(self.src))
        self.assertIn("404", str(ctx.exception))

    def test_422_conflict(self) -> None:
        u = self._uploader()
        with patch("requests.put", return_value=_make_response(422, {"message": "file exists"})):
            with self.assertRaises(UploadError) as ctx:
                u.upload(str(self.src))
        self.assertIn("422", str(ctx.exception))

    def test_network_exception_maps_to_upload_error(self) -> None:
        u = self._uploader()
        with patch("requests.put", side_effect=Exception("ConnectionResetError")):
            with self.assertRaises(UploadError) as ctx:
                u.upload(str(self.src))
        self.assertIn("网络", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
