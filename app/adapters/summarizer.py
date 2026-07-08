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

    def summarize(self, video: Video) -> Video:
        """summary / summary_ok を埋めて返す。失敗時は代替表示(呼び出し側)に委ねる。"""
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
        return video

    def _generate_with_retry(self, video: Video) -> str:
        """一時的な ServerError(5xx)のみ数回リトライする。4xx は即座に諦める。"""
        attempts = config.GEMINI_RETRY + 1
        for attempt in range(1, attempts + 1):
            try:
                response = self._client.models.generate_content(
                    model=self._model,
                    contents=[
                        types.Part.from_uri(file_uri=video.url, mime_type="video/*"),
                        SUMMARY_PROMPT,
                    ],
                )
                return (response.text or "").strip()
            except errors.ServerError as e:
                if attempt >= attempts:
                    raise
                logger.info(
                    "一時エラーで再試行 (%d/%d): video_id=%s %s",
                    attempt,
                    attempts - 1,
                    video.video_id,
                    _describe_error(e),
                )
                time.sleep(config.GEMINI_RETRY_WAIT_SEC)
        return ""  # 到達しない(ループ内で return / raise する)


def _describe_error(e: Exception) -> str:
    """ログ用にエラーの要点を組み立てる。Gemini API エラーは status/code/message を含める。"""
    if isinstance(e, errors.APIError):
        message = (e.message or "").replace("\n", " ")[:200]
        return f"reason=APIError code={e.code} status={e.status} message={message!r}"
    return f"reason={type(e).__name__}"
