from app.models import Video
from app.pipeline import filter_new


def make_video(video_id: str) -> Video:
    return Video(
        video_id=video_id,
        title=f"title-{video_id}",
        channel_title="ch",
        url=f"https://www.youtube.com/watch?v={video_id}",
        published_at="2026-07-08T05:00:00+00:00",
    )


def test_filter_new_unseen_only_returns_diff():
    videos = [make_video("a"), make_video("b")]
    result = filter_new(videos, seen={"a"})
    assert [v.video_id for v in result] == ["b"]


def test_filter_new_all_seen_returns_empty():
    videos = [make_video("a"), make_video("b")]
    assert filter_new(videos, seen={"a", "b"}) == []


def test_filter_new_empty_input_returns_empty():
    assert filter_new([], seen={"a"}) == []


def test_filter_new_duplicate_in_run_is_deduped():
    videos = [make_video("a"), make_video("a"), make_video("b")]
    result = filter_new(videos, seen=set())
    assert [v.video_id for v in result] == ["a", "b"]
