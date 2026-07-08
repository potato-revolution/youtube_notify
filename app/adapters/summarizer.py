"""Gemini に YouTube URL を直接渡して日本語の構造化要約を生成する。"""

import logging

from google import genai
from google.genai import types

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
        self._client = genai.Client(api_key=api_key or config.gemini_api_key())
        self._model = model or config.GEMINI_MODEL

    def summarize(self, video: Video) -> Video:
        """summary / summary_ok を埋めて返す。失敗時は代替表示(呼び出し側)に委ねる。"""
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=[
                    types.Part.from_uri(file_uri=video.url, mime_type="video/*"),
                    SUMMARY_PROMPT,
                ],
            )
            text = (response.text or "").strip()
            if not text:
                raise ValueError("empty summary")
            video.summary = text
            video.summary_ok = True
        except Exception as e:
            # メンバー限定 / 非公開 / 年齢制限 / 長すぎ / API エラー等。
            # 例外メッセージに機密が混ざらないよう型名のみ記録する。
            logger.warning("要約失敗: video_id=%s reason=%s", video.video_id, type(e).__name__)
            video.summary = None
            video.summary_ok = False
        return video
