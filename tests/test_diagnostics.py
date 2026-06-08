from __future__ import annotations

import datetime as _datetime
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quickshot.config import Config  # noqa: E402
from quickshot.diagnostics import build_diagnostic_report, debug_log_path, redact_diagnostic_text  # noqa: E402


class _IsolatedAppDataMixin:
    def setUp(self) -> None:  # type: ignore[override]
        self._tmp = tempfile.TemporaryDirectory()
        self._prev_env = {
            "APPDATA": os.environ.get("APPDATA"),
            "LOCALAPPDATA": os.environ.get("LOCALAPPDATA"),
            "QUICKSHOT_DEBUG_LOG": os.environ.get("QUICKSHOT_DEBUG_LOG"),
        }
        os.environ["APPDATA"] = str(Path(self._tmp.name) / "Roaming")
        os.environ["LOCALAPPDATA"] = str(Path(self._tmp.name) / "Local")
        os.environ["QUICKSHOT_DEBUG_LOG"] = "1"

    def tearDown(self) -> None:  # type: ignore[override]
        for key, value in self._prev_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self._tmp.cleanup()


class DiagnosticReportTest(_IsolatedAppDataMixin, unittest.TestCase):
    def test_report_redacts_paths_and_secret_like_values(self) -> None:
        cfg = Config()
        cfg.github_owner = "private-owner"
        cfg.github_repo = "private-repo"
        cfg.save_dir = str(Path.home() / "Pictures" / "QuickShot")
        log_path = debug_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(
            "\n".join(
                [
                    f"home={Path.home()}",
                    "authorization: Bearer github_pat_1234567890abcdef",
                    "password=swordfish token=ghp_abcdef1234567890",
                ]
            ),
            encoding="utf-8",
        )

        report = build_diagnostic_report(
            cfg,
            log_tail_lines=5,
            now=_datetime.datetime(2026, 6, 8, 8, 0, tzinfo=_datetime.timezone.utc),
        )

        self.assertIn("QuickShot Diagnostic Report", report)
        self.assertIn("GeneratedAt=2026-06-08T08:00:00+00:00", report)
        self.assertIn("GithubOwnerConfigured=true", report)
        self.assertIn("GithubRepoConfigured=true", report)
        self.assertIn("DebugLogTailLastLines=3", report)
        self.assertIn("%USERPROFILE%", report)
        self.assertIn("%APPDATA%", report)
        self.assertNotIn(str(Path.home()), report)
        self.assertNotIn(os.environ["APPDATA"], report)
        self.assertNotIn("private-owner", report)
        self.assertNotIn("private-repo", report)
        self.assertNotIn("github_pat_", report)
        self.assertNotIn("ghp_", report)
        self.assertNotIn("swordfish", report)

    def test_redact_diagnostic_text_handles_empty_and_plain_text(self) -> None:
        self.assertEqual(redact_diagnostic_text(""), "")
        self.assertEqual(redact_diagnostic_text("plain text"), "plain text")

    def test_redact_diagnostic_text_redacts_unmapped_absolute_paths(self) -> None:
        text = r"save=D:\private\captures and backup=\\server\share\folder"
        redacted = redact_diagnostic_text(text)
        self.assertNotIn(r"D:\private", redacted)
        self.assertNotIn(r"\\server\share", redacted)
        self.assertIn("<path>", redacted)


if __name__ == "__main__":
    unittest.main()
