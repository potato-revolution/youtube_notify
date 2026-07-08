"""パイプライン結線の統合テスト(RSS/Gemini/SMTP はフェイクに置換)。"""

import pytest

from app.adapters.config_store import ConfigStore
from app.adapters.mail_builder import MailBuilder
from app.models import Channel, Video
from app.pipeline import run_pipeline


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
    def summarize(self, video: Video) -> Video:
        video.summary = f"【概要】{video.title} の要約"
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
        rss_summary="概要欄",
    )


def test_pipeline_sends_one_mail_and_updates_seen(tmp_path):
    store = make_store(tmp_path)
    sender = FakeSender()

    count = run_pipeline(
        store=store,
        fetcher=FakeFetcher([make_video("a"), make_video("b")]),
        classifier=FakeClassifier(),
        summarizer=FakeSummarizer(),
        builder=MailBuilder(),
        sender=sender,
    )

    assert count == 2
    assert len(sender.sent) == 1  # 1通に集約
    subject, body = sender.sent[0]
    assert "新着 2 本" in subject
    assert "動画a" in body and "動画b" in body
    # 送信成功後に seen が更新される
    assert store.load_seen() == {"a", "b"}


def test_pipeline_seen_videos_are_not_resent(tmp_path):
    store = make_store(tmp_path)
    store.save_seen(["a"])
    sender = FakeSender()

    count = run_pipeline(
        store=store,
        fetcher=FakeFetcher([make_video("a"), make_video("b")]),
        classifier=FakeClassifier(),
        summarizer=FakeSummarizer(),
        builder=MailBuilder(),
        sender=sender,
    )

    assert count == 1  # 既読 "a" は再通知されない(二重通知ゼロ)
    assert "動画b" in sender.sent[0][1]
    assert "動画a" not in sender.sent[0][1]


def test_pipeline_send_failure_does_not_update_seen(tmp_path):
    store = make_store(tmp_path)
    sender = FakeSender(fail=True)

    with pytest.raises(RuntimeError):
        run_pipeline(
            store=store,
            fetcher=FakeFetcher([make_video("a")]),
            classifier=FakeClassifier(),
            summarizer=FakeSummarizer(),
            builder=MailBuilder(),
            sender=sender,
        )

    # 送信失敗時は seen 未更新 → 翌日以降に再通知できる
    assert store.load_seen() == set()


def test_pipeline_excludes_shorts_and_lives(tmp_path):
    store = make_store(tmp_path)
    sender = FakeSender()

    # "b" を Shorts/ライブ扱いで除外。要約・送信されず、既読化のみされる
    count = run_pipeline(
        store=store,
        fetcher=FakeFetcher([make_video("a"), make_video("b")]),
        classifier=FakeClassifier(exclude_ids=("b",)),
        summarizer=FakeSummarizer(),
        builder=MailBuilder(),
        sender=sender,
    )

    assert count == 1
    body = sender.sent[0][1]
    assert "動画a" in body and "動画b" not in body
    # 除外分も既読化され、翌日以降に再プローブされない
    assert store.load_seen() == {"a", "b"}


def test_pipeline_all_excluded_does_not_send_but_marks_seen(tmp_path):
    store = make_store(tmp_path)
    sender = FakeSender()

    count = run_pipeline(
        store=store,
        fetcher=FakeFetcher([make_video("a"), make_video("b")]),
        classifier=FakeClassifier(exclude_ids=("a", "b")),
        summarizer=FakeSummarizer(),
        builder=MailBuilder(),
        sender=sender,
    )

    assert count == 0
    assert sender.sent == []  # 全て除外の日は送信しない
    assert store.load_seen() == {"a", "b"}  # 再プローブ防止のため既読化する
