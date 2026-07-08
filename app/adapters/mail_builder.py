"""新着 Video 群から1通分の HTML メールを生成する。"""

import html
from datetime import datetime
from zoneinfo import ZoneInfo

from app.models import Video

JST = ZoneInfo("Asia/Tokyo")

_STYLE_CARD = (
    "margin:0 0 24px 0;padding:16px;border:1px solid #ddd;border-radius:8px;font-family:sans-serif;"
)
_STYLE_META = "color:#666;font-size:13px;margin:4px 0 12px 0;"
_STYLE_SUMMARY = "font-size:14px;line-height:1.7;margin:0;"
_STYLE_WARN = (
    "font-size:14px;line-height:1.7;margin:0;padding:8px;background:#fff3e0;border-radius:4px;"
)


class MailBuilder:
    def build(self, videos: list[Video]) -> tuple[str, str]:
        today = datetime.now(JST).strftime("%Y-%m-%d")
        subject = f"【YouTube新着】{today} 新着 {len(videos)} 本"
        cards = "\n".join(self._build_card(v) for v in videos)
        heading = f"YouTube 新着まとめ({today} / {len(videos)}本)"
        body = (
            f'<div style="max-width:720px;margin:0 auto;">'
            f'<h2 style="font-family:sans-serif;">{heading}</h2>'
            f"{cards}"
            f"</div>"
        )
        return subject, body

    def _build_card(self, video: Video) -> str:
        title = html.escape(video.title)
        url = html.escape(video.url, quote=True)
        channel = html.escape(video.channel_title)
        published = html.escape(self._format_published(video.published_at))

        if video.summary_ok and video.summary:
            summary_html = f'<p style="{_STYLE_SUMMARY}">{self._to_html_text(video.summary)}</p>'
        else:
            fallback = self._to_html_text(video.rss_summary) or "(概要欄なし)"
            summary_html = f'<p style="{_STYLE_WARN}">⚠️ 要約できませんでした<br>{fallback}</p>'

        return (
            f'<div style="{_STYLE_CARD}">'
            f'<h3 style="margin:0;"><a href="{url}">{title}</a></h3>'
            f'<p style="{_STYLE_META}">{channel} ・ {published}</p>'
            f"{summary_html}"
            f"</div>"
        )

    @staticmethod
    def _format_published(published_at: str) -> str:
        """ISO8601 を JST 表示に変換する。パース不能な場合は原文のまま表示する。"""
        try:
            dt = datetime.fromisoformat(published_at)
            return dt.astimezone(JST).strftime("%Y-%m-%d %H:%M (JST)")
        except ValueError:
            return published_at

    @staticmethod
    def _to_html_text(text: str | None) -> str:
        """テキストをエスケープし、改行を <br> に変換する。"""
        if not text:
            return ""
        return html.escape(text).replace("\n", "<br>")
