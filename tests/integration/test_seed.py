"""初期シードの統合テスト: 直近N本のみ要約し、新着全IDを既読化する。"""

import pytest

from app.adapters.config_store import ConfigStore
from app.adapters.mail_builder import MailBuilder
from app.models import Channel, Video
from app.pipeline import pick_recent_per_channel, seed_pipeline


class FakeFetcher:
    def __init__(self, videos: list[Video]) -> None:
        self._videos = videos

    def fetch(self, channels: list[Channel]) -> list[Video]:
        return list(self._videos)


class FakeClassifier:
    """指定 ID を Shorts / 終了済みライブ扱いで除外する(既定は除外なし)。"""

    def __init__(self, exclude_ids: tuple[str, ...] = ()) -> None:
        self._exclude = set(exclude_ids)

    def is_excluded(self, video: Video) -> bool:
        return video.video_id in self._exclude


class FakeSummarizer:
    def __init__(self) -> None:
        self.calls = 0

    def summarize(self, video: Video) -> Video:
        self.calls += 1
        video.summary = "要約"
        video.summary_ok = True
        return video


class FakeSender:
    def __init__(self, fail: bool = False) -> None:
        self.sent: list[tuple[str, str]] = []
        self._fail = fail

    def send(self, subject: str, html_body: str) -> None:
        if self._fail:
            raise RuntimeError("smtp error")
        self.sent.append((subject, html_body))


def make_store(tmp_path) -> ConfigStore:
    return ConfigStore(
        channels_path=tmp_path / "channels.json",
        seen_path=tmp_path / "seen.json",
    )


def make_video(video_id: str, channel: str) -> Video:
    return Video(
        video_id=video_id,
        title=f"動画{video_id}",
        channel_title=channel,
        url=f"https://www.youtube.com/watch?v={video_id}",
        published_at="2026-07-08T05:00:00+00:00",
    )


def seed_two_channels(store):
    added = "2026-07-08T22:00:00+09:00"
    for cid, handle, title in [("UC1", "@a", "chA"), ("UC2", "@b", "chB")]:
        store.add_channel(Channel(channel_id=cid, handle=handle, title=title, added_at=added))


def test_pick_recent_per_channel_limits_each_channel():
    videos = [
        make_video("a1", "chA"),
        make_video("a2", "chA"),
        make_video("a3", "chA"),
        make_video("b1", "chB"),
        make_video("b2", "chB"),
    ]
    picked = pick_recent_per_channel(videos, recent=2)
    assert [v.video_id for v in picked] == ["a1", "a2", "b1", "b2"]


def test_seed_summarizes_only_recent_and_marks_all_seen(tmp_path):
    store = make_store(tmp_path)
    seed_two_channels(store)
    videos = [make_video(f"a{i}", "chA") for i in range(1, 6)] + [
        make_video(f"b{i}", "chB") for i in range(1, 6)
    ]
    summarizer = FakeSummarizer()
    sender = FakeSender()

    count = seed_pipeline(
        recent_per_channel=2,
        store=store,
        fetcher=FakeFetcher(videos),
        classifier=FakeClassifier(),
        summarizer=summarizer,
        builder=MailBuilder(),
        sender=sender,
    )

    # 各チャンネル直近2本 = 4本のみ要約・送信
    assert count == 4
    assert summarizer.calls == 4
    assert len(sender.sent) == 1
    # 新着10本すべてが既読化される(残り6本は再通知されない)
    assert len(store.load_seen()) == 10


def test_seed_send_failure_does_not_update_seen(tmp_path):
    store = make_store(tmp_path)
    seed_two_channels(store)
    videos = [make_video("a1", "chA"), make_video("b1", "chB")]

    with pytest.raises(RuntimeError):
        seed_pipeline(
            recent_per_channel=2,
            store=store,
            fetcher=FakeFetcher(videos),
            classifier=FakeClassifier(),
            summarizer=FakeSummarizer(),
            builder=MailBuilder(),
            sender=FakeSender(fail=True),
        )

    assert store.load_seen() == set()


def test_seed_excludes_shorts_and_lives_but_marks_all_seen(tmp_path):
    store = make_store(tmp_path)
    seed_two_channels(store)
    videos = [make_video(f"a{i}", "chA") for i in range(1, 4)] + [
        make_video(f"b{i}", "chB") for i in range(1, 4)
    ]
    summarizer = FakeSummarizer()
    sender = FakeSender()

    # 各チャンネルの1本目を除外。直近2本は除外後の残りから選ばれる
    count = seed_pipeline(
        recent_per_channel=2,
        store=store,
        fetcher=FakeFetcher(videos),
        classifier=FakeClassifier(exclude_ids=("a1", "b1")),
        summarizer=summarizer,
        builder=MailBuilder(),
        sender=sender,
    )

    assert count == 4  # a2,a3,b2,b3 の各チャンネル2本
    assert summarizer.calls == 4
    assert len(sender.sent) == 1
    # 除外分含む新着6本すべてが既読化される
    assert len(store.load_seen()) == 6
