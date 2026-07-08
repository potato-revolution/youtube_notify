"""@handle / URL を一度だけ channel_id に解決する(実行時は解決済み ID のみ使用)。"""

import re
from datetime import UTC, datetime

import feedparser
import httpx

from app.config import HTTP_TIMEOUT, RSS_URL_TEMPLATE
from app.models import Channel

_CHANNEL_URL_RE = re.compile(r"youtube\.com/channel/(UC[\w-]{22})")
_CHANNEL_ID_IN_PAGE_RE = re.compile(r'"channelId"\s*:\s*"(UC[\w-]{22})"')
_HANDLE_RE = re.compile(r"^@[\w.\-]+$")
_HANDLE_URL_RE = re.compile(r"youtube\.com/(@[\w.\-]+)")


class ChannelResolveError(Exception):
    """channel_id に解決できない入力。設定ファイルは変更しない。"""


def extract_channel_id_from_url(raw: str) -> str | None:
    """`/channel/UC…` 形式の URL から channel_id を直接抽出する(ネットワーク不要)。"""
    m = _CHANNEL_URL_RE.search(raw)
    return m.group(1) if m else None


def extract_handle(raw: str) -> str | None:
    """入力から @handle を取り出す。@handle 単体・handle URL の両形式に対応。"""
    if _HANDLE_RE.match(raw):
        return raw
    m = _HANDLE_URL_RE.search(raw)
    return m.group(1) if m else None


class ChannelResolver:
    def resolve(self, handle_or_url: str) -> Channel:
        raw = handle_or_url.strip()
        if not raw:
            raise ChannelResolveError("入力が空です")

        channel_id = extract_channel_id_from_url(raw)
        handle = ""
        if channel_id is None:
            handle = extract_handle(raw) or ""
            if not handle:
                raise ChannelResolveError(f"@handle / URL として解釈できません: {raw}")
            channel_id = self._resolve_handle(handle)

        title = self._fetch_channel_title(channel_id)
        return Channel(
            channel_id=channel_id,
            handle=handle,
            title=title,
            added_at=datetime.now(UTC).astimezone().isoformat(),
        )

    def _resolve_handle(self, handle: str) -> str:
        """チャンネルページを取得して channel_id を抽出する。"""
        url = f"https://www.youtube.com/{handle}"
        try:
            resp = httpx.get(url, timeout=HTTP_TIMEOUT, follow_redirects=True)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise ChannelResolveError(
                f"チャンネルページを取得できません: {handle} ({type(e).__name__})"
            ) from e
        m = _CHANNEL_ID_IN_PAGE_RE.search(resp.text)
        if not m:
            raise ChannelResolveError(f"channel_id を特定できません: {handle}")
        return m.group(1)

    def _fetch_channel_title(self, channel_id: str) -> str:
        """RSS からチャンネル名を取得する。失敗しても解決自体は成功とする。"""
        try:
            resp = httpx.get(RSS_URL_TEMPLATE.format(channel_id=channel_id), timeout=HTTP_TIMEOUT)
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)
            return feed.feed.get("title", "")
        except httpx.HTTPError:
            return ""
