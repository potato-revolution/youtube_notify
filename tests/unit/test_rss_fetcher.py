from pathlib import Path

import httpx
import pytest

import app.adapters.rss_fetcher as rss_fetcher_module
from app.adapters.rss_fetcher import RssFetcher
from app.models import Channel

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_feed.xml"


class FakeResponse:
    def __init__(self, content: bytes, fail: bool = False) -> None:
        self.content = content
        self._fail = fail

    def raise_for_status(self) -> None:
        if self._fail:
            raise httpx.HTTPError("boom")


def make_channel(channel_id: str) -> Channel:
    return Channel(
        channel_id=channel_id,
        handle="@sample",
        title="フォールバック名",
        added_at="2026-07-08T22:00:00+09:00",
    )


@pytest.fixture
def feed_bytes() -> bytes:
    return FIXTURE.read_bytes()


def test_fetch_parses_valid_entries_and_skips_missing_fields(monkeypatch, feed_bytes):
    monkeypatch.setattr(
        rss_fetcher_module.httpx, "get", lambda url, timeout: FakeResponse(feed_bytes)
    )
    videos = RssFetcher().fetch([make_channel("UC1")])

    # フィクスチャは3エントリ中、タイトル欠損の1件をスキップして2件
    assert [v.video_id for v in videos] == ["vid00000001", "vid00000002"]
    first = videos[0]
    assert first.title == "テスト動画1"
    assert first.channel_title == "サンプルチャンネル"
    assert first.url == "https://www.youtube.com/watch?v=vid00000001"
    assert first.published_at.startswith("2026-07-08")
    assert "動画1の概要欄テキスト" in first.rss_summary


def test_fetch_channel_failure_continues_with_others(monkeypatch, feed_bytes):
    def fake_get(url: str, timeout: float) -> FakeResponse:
        if "UCbad" in url:
            return FakeResponse(b"", fail=True)
        return FakeResponse(feed_bytes)

    monkeypatch.setattr(rss_fetcher_module.httpx, "get", fake_get)
    videos = RssFetcher().fetch([make_channel("UCbad"), make_channel("UCgood")])

    # 失敗チャンネルはスキップされ、正常チャンネルの2件が取得される
    assert len(videos) == 2
