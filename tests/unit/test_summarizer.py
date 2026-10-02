"""Summarizer のリトライ・エラー整形の単体テスト(Gemini クライアントはモック)。"""

import httpx
import pytest
from google.genai import errors

import app.adapters.summarizer as summarizer_module
from app.adapters.summarizer import Summarizer, _describe_error
from app.models import Video


def make_video() -> Video:
    return Video(
        video_id="vid1",
        title="動画",
        channel_title="ch",
        url="https://www.youtube.com/watch?v=vid1",
        published_at="2026-07-08T05:00:00+00:00",
    )


class FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text


class FakeModels:
    def __init__(self, results: list) -> None:
        self._results = list(results)
        self.calls = 0
        self.models_used: list[str] = []

    def generate_content(self, model, contents, config=None):
        self.calls += 1
        self.models_used.append(model)
        self.last_contents = contents
        self.last_config = config
        result = self._results.pop(0)
        if isinstance(result, Exception):
            raise result
        return FakeResponse(result)


def make_summarizer(monkeypatch, results: list) -> tuple[Summarizer, FakeModels]:
    # 実クライアントを作らずに Summarizer を組み立てる
    monkeypatch.setattr(summarizer_module.config, "GEMINI_RETRY", 2, raising=True)
    monkeypatch.setattr(summarizer_module.config, "GEMINI_RETRY_WAIT_SEC", 0, raising=True)
    monkeypatch.setattr(summarizer_module.config, "GEMINI_RATE_LIMIT_RETRY", 1, raising=True)
    monkeypatch.setattr(summarizer_module.config, "GEMINI_RATE_LIMIT_WAIT_SEC", 0, raising=True)
    monkeypatch.setattr(summarizer_module.config, "GEMINI_REQUEST_SPACING_SEC", 0, raising=True)
    monkeypatch.setattr(summarizer_module.time, "sleep", lambda *_: None)
    s = Summarizer.__new__(Summarizer)
    fake_models = FakeModels(results)

    class FakeClient:
        models = fake_models

    s._client = FakeClient()
    s._model = "gemini-test"
    s._fallback_model = ""  # 既定はフォールバック無効(個別テストで設定)
    s._made_call = False
    return s, fake_models


def make_server_error() -> errors.ServerError:
    return errors.ServerError(503, {"error": {"status": "UNAVAILABLE", "message": "overloaded"}})


def make_client_error() -> errors.ClientError:
    return errors.ClientError(
        429, {"error": {"status": "RESOURCE_EXHAUSTED", "message": "quota exceeded"}}
    )


def make_permanent_client_error() -> errors.ClientError:
    return errors.ClientError(
        403, {"error": {"status": "PERMISSION_DENIED", "message": "members only"}}
    )


def test_summarize_success(monkeypatch):
    s, models = make_summarizer(monkeypatch, ["【概要】要約本文"])
    result = s.summarize(make_video())
    assert result.summary_ok is True
    assert result.summary == "【概要】要約本文"
    assert models.calls == 1


def test_summarize_retries_server_error_then_succeeds(monkeypatch):
    s, models = make_summarizer(monkeypatch, [make_server_error(), "要約"])
    result = s.summarize(make_video())
    assert result.summary_ok is True
    assert models.calls == 2  # 1回失敗 → リトライで成功


def test_summarize_server_error_exhausts_retries(monkeypatch):
    s, models = make_summarizer(
        monkeypatch, [make_server_error(), make_server_error(), make_server_error()]
    )
    result = s.summarize(make_video())
    assert result.summary_ok is False
    assert result.summary_retryable is True  # 5xx は一時的失敗
    assert models.calls == 3  # 初回 + リトライ2回


def test_summarize_server_error_backoff_doubles_wait(monkeypatch):
    s, _ = make_summarizer(monkeypatch, [make_server_error(), make_server_error(), "要約"])
    monkeypatch.setattr(summarizer_module.config, "GEMINI_RETRY_WAIT_SEC", 60, raising=True)
    waits: list[int] = []
    monkeypatch.setattr(summarizer_module.time, "sleep", waits.append)
    result = s.summarize(make_video())
    assert result.summary_ok is True
    assert waits == [60, 120]  # 指数バックオフ


def test_summarize_falls_back_to_secondary_model_after_server_errors(monkeypatch):
    # 主モデルで 初回+2回 すべて 5xx → 代替モデルで成功
    s, models = make_summarizer(
        monkeypatch, [make_server_error(), make_server_error(), make_server_error(), "要約"]
    )
    s._fallback_model = "gemini-fallback"
    result = s.summarize(make_video())
    assert result.summary_ok is True
    assert models.models_used == ["gemini-test"] * 3 + ["gemini-fallback"]


def test_summarize_fallback_also_failing_is_retryable(monkeypatch):
    s, models = make_summarizer(monkeypatch, [make_server_error()] * 6)
    s._fallback_model = "gemini-fallback"
    result = s.summarize(make_video())
    assert result.summary_ok is False
    assert result.summary_retryable is True
    assert models.calls == 6  # 主 3回 + 代替 3回


def test_summarize_no_fallback_on_permanent_client_error(monkeypatch):
    s, models = make_summarizer(monkeypatch, [make_permanent_client_error(), "使われない"])
    s._fallback_model = "gemini-fallback"
    result = s.summarize(make_video())
    assert result.summary_ok is False
    assert models.models_used == ["gemini-test"]  # 4xx では代替モデルに切り替えない


def test_summarize_retries_rate_limit_then_succeeds(monkeypatch):
    s, models = make_summarizer(monkeypatch, [make_client_error(), "要約"])
    result = s.summarize(make_video())
    assert result.summary_ok is True
    assert models.calls == 2  # 429 は1回リトライで成功


def test_summarize_rate_limit_exhausts_retries_is_retryable(monkeypatch):
    s, models = make_summarizer(monkeypatch, [make_client_error(), make_client_error()])
    result = s.summarize(make_video())
    assert result.summary_ok is False
    assert result.summary_retryable is True  # 429 は一時的失敗 → 次回リトライ対象
    assert models.calls == 2  # 初回 + レート制限リトライ1回


def test_summarize_permanent_client_error_not_retried(monkeypatch):
    s, models = make_summarizer(monkeypatch, [make_permanent_client_error(), "使われない"])
    result = s.summarize(make_video())
    assert result.summary_ok is False
    assert result.summary_retryable is False  # 429 以外の 4xx は恒久的失敗 → 既読化
    assert models.calls == 1  # 429 以外の 4xx はリトライしない


def test_summarize_empty_text_is_failure(monkeypatch):
    s, _ = make_summarizer(monkeypatch, ["   "])
    result = s.summarize(make_video())
    assert result.summary_ok is False
    assert result.summary_retryable is False  # 空要約は既読化(無限リトライを防ぐ)


def test_summarize_applies_low_fps_and_media_resolution(monkeypatch):
    s, models = make_summarizer(monkeypatch, ["要約"])
    s.summarize(make_video())
    video_part = models.last_contents[0]
    assert video_part.video_metadata.fps == 0.2
    assert models.last_config.media_resolution == "MEDIA_RESOLUTION_LOW"


def test_describe_error_api_error_includes_code_and_status():
    desc = _describe_error(make_client_error())
    assert "code=429" in desc
    assert "RESOURCE_EXHAUSTED" in desc


def test_describe_error_generic_exception_uses_type_name():
    assert _describe_error(httpx.TimeoutException("boom")) == "reason=TimeoutException"


@pytest.mark.parametrize("err", [make_server_error(), make_client_error()])
def test_describe_error_does_not_raise(err):
    assert isinstance(_describe_error(err), str)
