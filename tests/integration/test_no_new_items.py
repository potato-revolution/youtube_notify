"""新着0本の日は送信しないことの統合テスト。"""

from app.adapters.config_store import ConfigStore
from app.models import Channel, Video
from app.pipeline import run_pipeline


class FakeFetcher:
    def __init__(self, videos: list[Video]) -> None:
        self._videos = videos

    def fetch(self, channels: list[Channel]) -> list[Video]:
        return list(self._videos)


class FakeSender:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def send(self, subject: str, html_body: str) -> None:
        self.sent.append((subject, html_body))


def make_store(tmp_path) -> ConfigStore:
    store = ConfigStore(
        channels_path=tmp_path / "channels.json",
        seen_path=tmp_path / "seen.json",
    )
    store.add_channel(
        Channel(
            channel_id="UC1",
            handle="@sample",
            title="サンプル",
            added_at="2026-07-08T22:00:00+09:00",
        )
    )
    return store


def make_video(video_id: str) -> Video:
    return Video(
        video_id=video_id,
        title=f"動画{video_id}",
        channel_title="サンプル",
        url=f"https://www.youtube.com/watch?v={video_id}",
        published_at="2026-07-08T05:00:00+00:00",
    )


def test_all_seen_does_not_send_and_seen_unchanged(tmp_path):
    store = make_store(tmp_path)
    store.save_seen(["a", "b"])
    sender = FakeSender()

    count = run_pipeline(
        store=store,
        fetcher=FakeFetcher([make_video("a"), make_video("b")]),
        sender=sender,
    )

    assert count == 0
    assert sender.sent == []  # 新着0本の日は送信しない
    assert store.load_seen() == {"a", "b"}


def test_empty_feed_does_not_send(tmp_path):
    store = make_store(tmp_path)
    sender = FakeSender()

    count = run_pipeline(store=store, fetcher=FakeFetcher([]), sender=sender)

    assert count == 0
    assert sender.sent == []
    assert store.load_seen() == set()
