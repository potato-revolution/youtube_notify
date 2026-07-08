from app.adapters.mail_builder import MailBuilder
from app.models import Video


def make_video(**overrides) -> Video:
    defaults = dict(
        video_id="vid1",
        title="テスト動画",
        channel_title="サンプルチャンネル",
        url="https://www.youtube.com/watch?v=vid1",
        published_at="2026-07-08T05:00:00+00:00",
        rss_summary="概要欄テキスト",
    )
    defaults.update(overrides)
    return Video(**defaults)


def test_build_subject_contains_count():
    subject, _ = MailBuilder().build([make_video(), make_video(video_id="vid2")])
    assert "新着 2 本" in subject
    assert "【YouTube新着】" in subject


def test_build_success_summary_rendered_with_br():
    video = make_video(summary="【概要】\n本文テキスト", summary_ok=True)
    _, body = MailBuilder().build([video])
    assert "【概要】<br>本文テキスト" in body
    assert "⚠️" not in body


def test_build_failed_summary_shows_warning_and_rss_fallback():
    video = make_video(summary=None, summary_ok=False)
    _, body = MailBuilder().build([video])
    assert "⚠️ 要約できませんでした" in body
    assert "概要欄テキスト" in body


def test_build_contains_title_channel_link_and_jst_time():
    _, body = MailBuilder().build([make_video(summary="要約", summary_ok=True)])
    assert "テスト動画" in body
    assert "サンプルチャンネル" in body
    assert 'href="https://www.youtube.com/watch?v=vid1"' in body
    # 05:00 UTC → 14:00 JST
    assert "2026-07-08 14:00 (JST)" in body


def test_build_escapes_html_in_title_and_summary():
    video = make_video(
        title="<script>alert(1)</script>",
        summary="要約 <b>タグ</b>",
        summary_ok=True,
    )
    _, body = MailBuilder().build([video])
    assert "<script>" not in body
    assert "&lt;script&gt;" in body
    assert "&lt;b&gt;タグ&lt;/b&gt;" in body
