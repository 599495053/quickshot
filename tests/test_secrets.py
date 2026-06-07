"""secrets.py 单元测试。

覆盖：
- get_secret / set_secret / delete_secret 基本流程
- get_github_token / set_github_token / delete_github_token 便捷函数
- keyring 异常时的优雅降级
- SERVICE_GITHUB 常量
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quickshot import secrets  # noqa: E402
from quickshot.secrets import (  # noqa: E402
    SERVICE_GITHUB,
    delete_github_token,
    delete_secret,
    get_github_token,
    get_secret,
    set_github_token,
    set_secret,
)


class ServiceConstantTest(unittest.TestCase):
    def test_service_github_contains_app_name(self) -> None:
        self.assertIn("QuickShot", SERVICE_GITHUB)
        self.assertTrue(SERVICE_GITHUB.endswith(".github"))


class GetSecretTest(unittest.TestCase):
    @patch("keyring.get_password", return_value="my-token")
    def test_returns_value(self, mock_get) -> None:
        result = get_secret("svc", "acct")
        self.assertEqual(result, "my-token")
        mock_get.assert_called_once_with("svc", "acct")

    @patch("keyring.get_password", return_value=None)
    def test_returns_empty_on_none(self, mock_get) -> None:
        self.assertEqual(get_secret("svc", "acct"), "")

    @patch("keyring.get_password", side_effect=RuntimeError("no backend"))
    def test_returns_empty_on_exception(self, mock_get) -> None:
        self.assertEqual(get_secret("svc", "acct"), "")


class SetSecretTest(unittest.TestCase):
    @patch("keyring.set_password")
    def test_returns_true_on_success(self, mock_set) -> None:
        self.assertTrue(set_secret("svc", "acct", "val"))
        mock_set.assert_called_once_with("svc", "acct", "val")

    @patch("keyring.set_password", side_effect=PermissionError("denied"))
    def test_returns_false_on_exception(self, mock_set) -> None:
        self.assertFalse(set_secret("svc", "acct", "val"))


class DeleteSecretTest(unittest.TestCase):
    @patch("keyring.delete_password")
    def test_returns_true_on_success(self, mock_del) -> None:
        self.assertTrue(delete_secret("svc", "acct"))
        mock_del.assert_called_once_with("svc", "acct")

    @patch("keyring.delete_password", side_effect=Exception("fail"))
    def test_returns_false_on_exception(self, mock_del) -> None:
        self.assertFalse(delete_secret("svc", "acct"))


class GithubTokenTest(unittest.TestCase):
    @patch("keyring.get_password", return_value="ghp_abc")
    def test_get_default_account(self, mock_get) -> None:
        self.assertEqual(get_github_token(), "ghp_abc")
        mock_get.assert_called_once_with(SERVICE_GITHUB, "default")

    @patch("keyring.get_password", return_value="ghp_xyz")
    def test_get_custom_account(self, mock_get) -> None:
        self.assertEqual(get_github_token("owner/repo"), "ghp_xyz")
        mock_get.assert_called_once_with(SERVICE_GITHUB, "owner/repo")

    @patch("keyring.set_password")
    def test_set_default_account(self, mock_set) -> None:
        self.assertTrue(set_github_token("ghp_new"))
        mock_set.assert_called_once_with(SERVICE_GITHUB, "default", "ghp_new")

    @patch("keyring.set_password")
    def test_set_custom_account(self, mock_set) -> None:
        self.assertTrue(set_github_token("ghp_new", "owner/repo"))
        mock_set.assert_called_once_with(SERVICE_GITHUB, "owner/repo", "ghp_new")

    @patch("keyring.delete_password")
    def test_delete_default_account(self, mock_del) -> None:
        self.assertTrue(delete_github_token())
        mock_del.assert_called_once_with(SERVICE_GITHUB, "default")

    @patch("keyring.delete_password")
    def test_delete_custom_account(self, mock_del) -> None:
        self.assertTrue(delete_github_token("owner/repo"))
        mock_del.assert_called_once_with(SERVICE_GITHUB, "owner/repo")


if __name__ == "__main__":
    unittest.main()
