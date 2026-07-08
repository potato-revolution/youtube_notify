import httpx

import app.adapters.video_classifier as vc_module
from app.adapters.video_classifier import VideoClassifier
from app.models import Video


class FakeResponse:
    def __init__(self, status_code: int = 200, text: str = "") -> None:
        self.status_code = status_code
        self.text = text

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPError("boom")


def make_video(video_id: str = "vid1") -> Video:
    return Video(
        video_id=video_id,
        title="タイトル",
        channel_title="ch",
        url=f"https://www.youtube.com/watch?v={video_id}",
        published_at="2026-07-08T05:00:00+00:00",
    )


def patch_probes(monkeypatch, *, shorts_status: int, watch_text: str) -> None:
    monkeypatch.setattr(
        vc_module.httpx, "head", lambda url, **kw: FakeResponse(status_code=shorts_status)
    )
    monkeypatch.setattr(
        vc_module.httpx, "get", lambda url, **kw: FakeResponse(text=watch_text)
    )


def test_short_is_excluded(monkeypatch):
    # /shorts/{id} が 200 → Short
    patch_probes(monkeypatch, shorts_status=200, watch_text="")
    assert VideoClassifier().is_excluded(make_video()) is True


def test_finished_live_is_excluded(monkeypatch):
    # 通常 URL は 303、watch に isLiveContent:true → 終了済みライブ
    patch_probes(monkeypatch, shorts_status=303, watch_text='{"isLiveContent":true}')
    assert VideoClassifier().is_excluded(make_video()) is True


def test_normal_video_is_kept(monkeypatch):
    patch_probes(monkeypatch, shorts_status=303, watch_text='{"isLiveContent":false}')
    assert VideoClassifier().is_excluded(make_video()) is False


def test_probe_failure_keeps_video(monkeypatch):
    # ネットワークエラー時は除外しない(取りこぼしゼロ優先)
    def boom(url, **kw):
        raise httpx.ConnectError("network down")

    monkeypatch.setattr(vc_module.httpx, "head", boom)
    monkeypatch.setattr(vc_module.httpx, "get", boom)
    assert VideoClassifier().is_excluded(make_video()) is False
