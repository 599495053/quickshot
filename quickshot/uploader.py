"""上传器抽象接口与内置实现。

提供统一的截图上传抽象，支持图床、对象存储、本地存档等多种后端。
所有上传器实现 Uploader 接口，由 UploaderRegistry 统一管理。
"""

from __future__ import annotations

import base64
import time
import datetime
import os
import shutil
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, Dict, List, Optional

from .utils import APP_NAME, debug_log


class UploadResult:
    """上传结果对象。url 为可访问链接（http(s) 或 file://），name 为展示名。"""

    def __init__(self, url: str, name: str = "", thumb_url: str = "") -> None:
        self.url = url
        self.name = name or url
        self.thumb_url = thumb_url or url

    def __repr__(self) -> str:
        return f"UploadResult(url={self.url!r}, name={self.name!r})"


class UploadError(Exception):
    """上传失败异常。message 应可直接展示给用户。"""


class Uploader(ABC):
    """上传器抽象基类。

    子类必须实现 upload(image_path) → UploadResult。
    name() 返回展示名称，identifier() 返回唯一 key（配置存储用）。
    is_configured() 用于在 UI 中提示需要先填写配置。
    """

    @classmethod
    @abstractmethod
    def identifier(cls) -> str:
        """唯一标识，例如 'local'、'github'、'picgo'。"""

    @classmethod
    @abstractmethod
    def display_name(cls) -> str:
        """界面展示名称，例如 '本地存档'、'GitHub'。"""

    def is_configured(self) -> bool:
        """返回 True 表示该上传器已具备工作所需的配置。"""
        return True

    @abstractmethod
    def upload(self, image_path: str) -> UploadResult:
        """上传一张图片并返回结果。失败请抛 UploadError。"""


class LocalArchiveUploader(Uploader):
    """本地存档：把图片复制到指定目录，返回 file:// 链接。

    无需任何外部网络，作为默认上传器开箱即用。
    """

    def __init__(self, archive_dir: Optional[str] = None) -> None:
        if archive_dir:
            self.archive_dir = Path(archive_dir)
        else:
            base = os.environ.get("APPDATA") or str(Path.home())
            self.archive_dir = Path(base) / APP_NAME / "uploads"

    @classmethod
    def identifier(cls) -> str:
        return "local"

    @classmethod
    def display_name(cls) -> str:
        return "本地存档"

    def upload(self, image_path: str) -> UploadResult:
        src = Path(image_path)
        if not src.exists():
            raise UploadError(f"源文件不存在：{image_path}")
        try:
            self.archive_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            # 截断过长文件名，避免 Windows 路径限制（MAX_PATH=260）
            name = src.name
            if len(name) > 200:
                suffix = Path(name).suffix
                name = name[:200 - len(suffix)] + suffix
            dest = self.archive_dir / f"{stamp}_{name}"
            shutil.copy2(src, dest)
            url = dest.resolve().as_uri()  # file:///...
            return UploadResult(url=url, name=dest.name)
        except OSError as exc:
            debug_log(f"LocalArchiveUploader failed: {exc}")
            raise UploadError(f"复制到存档目录失败：{exc}") from exc


class GitHubUploader(Uploader):
    """GitHub Contents API 上传器。

    把图片提交到指定仓库（owner/repo）的指定分支（branch）下，
    路径形如 {path_prefix}/{YYYY}/{MM-DD}/{uuid}_{filename}。
    返回的 URL 走 raw.githubusercontent.com，可直接在 Markdown 中显示。

    Token 通过 token_provider 注入（默认从 keyring 读取），不持久化到 config。

    依赖：requests
    """

    API_BASE = "https://api.github.com"
    RAW_BASE = "https://raw.githubusercontent.com"

    def __init__(
        self,
        owner: str = "",
        repo: str = "",
        branch: str = "main",
        path_prefix: str = "screenshots",
        token_provider: Optional[Callable[[], str]] = None,
        request_timeout: float = 30.0,
    ) -> None:
        self.owner = owner.strip()
        self.repo = repo.strip()
        self.branch = (branch or "main").strip() or "main"
        self.path_prefix = path_prefix.strip().strip("/") or "screenshots"
        self._token_provider = token_provider
        self.request_timeout = request_timeout

    @classmethod
    def identifier(cls) -> str:
        return "github"

    @classmethod
    def display_name(cls) -> str:
        return "GitHub 仓库"

    def _token(self) -> str:
        if self._token_provider is None:
            return ""
        try:
            return (self._token_provider() or "").strip()
        except Exception as exc:  # noqa: BLE001
            debug_log(f"GitHubUploader token_provider failed: {exc}")
            return ""

    def is_configured(self) -> bool:
        return bool(self.owner and self.repo and self._token())

    def build_remote_path(self, source_name: str) -> str:
        """生成仓库内的目标路径。按日期分目录，文件名加 uuid 前缀避免冲突。"""
        now = datetime.datetime.now()
        year = now.strftime("%Y")
        day = now.strftime("%m-%d")
        safe_name = Path(source_name).name or "image.png"
        token = uuid.uuid4().hex[:8]
        return f"{self.path_prefix}/{year}/{day}/{token}_{safe_name}"

    def upload(self, image_path: str) -> UploadResult:
        if not self.owner or not self.repo:
            raise UploadError("GitHub 上传器未配置：缺少 owner 或 repo")
        token = self._token()
        if not token:
            raise UploadError("GitHub 上传器未配置：缺少 Personal Access Token")
        src = Path(image_path)
        if not src.exists():
            raise UploadError(f"源文件不存在：{image_path}")

        try:
            file_bytes = src.read_bytes()
        except OSError as exc:
            raise UploadError(f"读取源文件失败：{exc}") from exc

        # GitHub Contents API 单文件上限 100MB，但 base64 膨胀 ~33%，
        # 且大文件上传极慢，限制 10MB 以保证用户体验。
        max_size = 10 * 1024 * 1024
        if len(file_bytes) > max_size:
            size_mb = len(file_bytes) / (1024 * 1024)
            raise UploadError(f"文件过大（{size_mb:.1f}MB），GitHub 上传限制 10MB")

        payload = base64.b64encode(file_bytes).decode("ascii")

        remote_path = self.build_remote_path(src.name)
        api_url = f"{self.API_BASE}/repos/{self.owner}/{self.repo}/contents/{remote_path}"
        body = {
            "message": f"chore: upload {src.name} via QuickShot",
            "content": payload,
            "branch": self.branch,
        }
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": f"{APP_NAME}-uploader",
        }

        try:
            import requests
        except ImportError as exc:
            raise UploadError("缺少依赖 requests，请先安装") from exc

        max_retries = 2
        resp = None
        for attempt in range(max_retries):
            try:
                resp = requests.put(api_url, json=body, headers=headers, timeout=self.request_timeout)
            except Exception as exc:  # noqa: BLE001
                raise UploadError(f"网络请求失败：{exc}") from exc

            if resp.status_code in (200, 201):
                raw_url = f"{self.RAW_BASE}/{self.owner}/{self.repo}/{self.branch}/{remote_path}"
                return UploadResult(url=raw_url, name=src.name)

            # 5xx 服务端错误：重试一次
            if resp.status_code >= 500 and attempt < max_retries - 1:
                debug_log(f"GitHub upload got {resp.status_code}, retrying in 2s...")
                time.sleep(2)
                continue

            break

        # 友好错误映射
        message = self._format_error(resp)
        raise UploadError(message)

    def _format_error(self, resp) -> str:
        code = getattr(resp, "status_code", 0)
        try:
            data = resp.json()
            detail = data.get("message", "")
        except Exception:  # noqa: BLE001
            detail = ""
        if code == 401:
            return "GitHub 上传失败：Token 无效或已过期（401）"
        if code == 403:
            return f"GitHub 上传失败：权限不足或被限流（403）{(' ' + detail) if detail else ''}"
        if code == 404:
            return "GitHub 上传失败：仓库不存在或 Token 无权访问（404）"
        if code == 422:
            return f"GitHub 上传失败：文件已存在或参数错误（422）{(' ' + detail) if detail else ''}"
        if 500 <= code < 600:
            return f"GitHub 服务暂时不可用（{code}），请稍后重试{('：' + detail) if detail else ''}"
        return f"GitHub 上传失败：HTTP {code} {detail}".rstrip()


class UploaderRegistry:
    """上传器注册表。维护可用上传器列表，按 identifier 查询。"""

    def __init__(self) -> None:
        self._uploaders: Dict[str, Uploader] = {}

    def register(self, uploader: Uploader) -> None:
        self._uploaders[uploader.identifier()] = uploader

    def unregister(self, identifier: str) -> None:
        self._uploaders.pop(identifier, None)

    def get(self, identifier: str) -> Optional[Uploader]:
        return self._uploaders.get(identifier)

    def list_uploaders(self) -> List[Uploader]:
        return list(self._uploaders.values())

    def identifiers(self) -> List[str]:
        return list(self._uploaders.keys())


def build_default_registry(
    archive_dir: Optional[str] = None,
    config: Optional[object] = None,
    github_token_provider: Optional[Callable[[], str]] = None,
) -> UploaderRegistry:
    """构建默认注册表，包含本地存档与 GitHub 上传器。

    - 不传 config 时，GitHub 上传器以空配置注册，is_configured() 为 False
    - 传 config 时从 config.github_* 读取仓库参数，token_provider 提供 PAT
    """
    registry = UploaderRegistry()
    registry.register(LocalArchiveUploader(archive_dir=archive_dir))

    owner = getattr(config, "github_owner", "") if config is not None else ""
    repo = getattr(config, "github_repo", "") if config is not None else ""
    branch = getattr(config, "github_branch", "main") if config is not None else "main"
    prefix = getattr(config, "github_path_prefix", "screenshots") if config is not None else "screenshots"
    if github_token_provider is None and config is not None:
        # 延迟导入避免循环依赖与 keyring 模块加载开销
        from .secrets import get_github_token
        github_token_provider = lambda: get_github_token(f"{owner}/{repo}") if owner and repo else get_github_token()
    registry.register(GitHubUploader(
        owner=owner,
        repo=repo,
        branch=branch,
        path_prefix=prefix,
        token_provider=github_token_provider,
    ))
    return registry


def format_markdown_link(result: UploadResult, alt_text: str = "") -> str:
    """生成 Markdown 图片链接 ![alt](url)。"""
    alt = alt_text or result.name or "image"
    return f"![{alt}]({result.url})"
