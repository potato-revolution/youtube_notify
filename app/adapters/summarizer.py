"""Gemini に YouTube URL を直接渡して日本語の構造化要約を生成する。"""

import logging
import time

from google import genai
from google.genai import errors, types

from app import config
from app.models import Video

logger = logging.getLogger(__name__)

# Markdown 記法を禁止しているのは、メール HTML への変換を単純に保つため
# (mail_builder は全文をエスケープし改行を <br> にするだけでよい)。
SUMMARY_PROMPT = """\
この YouTube 動画の内容を、動画を観なくても内容が分かるレベルで日本語で詳しく要約してください。

出力形式:
- 最初に2〜3文で全体の概要を書く
- 続いてトピックごとに【小見出し】で区切ったセクションで詳細を書く
- 箇条書きには「・」を使う
- Markdown 記法(#、*、** など)は使わない
- 全体で400〜800字程度
"""


class Summarizer:
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self._client = genai.Client(
            api_key=api_key or config.gemini_api_key(),
            http_options=types.HttpOptions(timeout=config.GEMINI_TIMEOUT_MS),
        )
        self._model = model or config.GEMINI_MODEL
        self._made_call = False  # 動画間スペーシング用(初回だけ待たない)

    def summarize(self, video: Video) -> Video:
        """summary / summary_ok を埋めて返す。失敗時は代替表示(呼び出し側)に委ねる。"""
        self._space_requests()
        try:
            text = self._generate_with_retry(video)
            if not text:
                raise ValueError("empty summary")
            video.summary = text
            video.summary_ok = True
        except Exception as e:
            # メンバー限定 / 非公開 / 年齢制限 / 長すぎ / レート制限 / API エラー等。
            # 原因を追えるよう、Gemini API エラーは status/code/message を記録する
            # (Gemini のエラー本文に当方の機密は含まれない)。
            logger.warning("要約失敗: video_id=%s %s", video.video_id, _describe_error(e))
            video.summary = None
            video.summary_ok = False
            # 一時的失敗(429/5xx)は次回実行で再試行できるよう印を付ける。
            video.summary_retryable = _is_retryable(e)
        return video

    def _generate_with_retry(self, video: Video) -> str:
        """一時的な ServerError(5xx)とレート制限(429)を数回リトライする。

        429 は RPM/TPM 窓のリセットを見込んで 5xx より長く待つ。それ以外の 4xx は
        即座に諦める。リトライを使い切ったら最後のエラーを送出する。
        """
        server_left = config.GEMINI_RETRY
        rate_left = config.GEMINI_RATE_LIMIT_RETRY
        while True:
            try:
                response = self._client.models.generate_content(
                    model=self._model,
                    contents=[
                        types.Part(
                            file_data=types.FileData(file_uri=video.url, mime_type="video/*"),
                            # fps を下げてフレーム数=トークン消費を削減する
                            video_metadata=types.VideoMetadata(fps=config.GEMINI_VIDEO_FPS),
                        ),
                        SUMMARY_PROMPT,
                    ],
                    config=types.GenerateContentConfig(
                        # フレームあたりのトークン解像度を下げる
                        media_resolution=config.GEMINI_MEDIA_RESOLUTION,
                    ),
                )
                return (response.text or "").strip()
            except errors.ServerError as e:
                if server_left <= 0:
                    raise
                server_left -= 1
                self._log_retry(video, e, config.GEMINI_RETRY_WAIT_SEC)
            except errors.ClientError as e:
                if e.code != 429 or rate_left <= 0:
                    raise
                rate_left -= 1
                self._log_retry(video, e, config.GEMINI_RATE_LIMIT_WAIT_SEC)

    def _log_retry(self, video: Video, e: Exception, wait_sec: int) -> None:
        logger.info(
            "一時エラーで再試行 (%ds 待機): video_id=%s %s",
            wait_sec,
            video.video_id,
            _describe_error(e),
        )
        time.sleep(wait_sec)

    def _space_requests(self) -> None:
        """2本目以降の呼び出し前に待機し、1分あたりレート上限(TPM)超過を避ける。"""
        if self._made_call and config.GEMINI_REQUEST_SPACING_SEC > 0:
            time.sleep(config.GEMINI_REQUEST_SPACING_SEC)
        self._made_call = True


def _is_retryable(e: Exception) -> bool:
    """次回実行での再試行で解消しうる一時的失敗か判定する。

    レート/クォータ超過(429)とサーバ混雑(5xx)を一時的とみなす。メンバー限定・
    非公開・年齢制限などの 4xx や空要約は恒久的失敗として既読化させる。
    """
    if isinstance(e, errors.ServerError):
        return True
    if isinstance(e, errors.APIError):
        return e.code == 429
    return False


def _describe_error(e: Exception) -> str:
    """ログ用にエラーの要点を組み立てる。Gemini API エラーは status/code/message を含める。"""
    if isinstance(e, errors.APIError):
        message = (e.message or "").replace("\n", " ")[:200]
        return f"reason=APIError code={e.code} status={e.status} message={message!r}"
    return f"reason={type(e).__name__}"
