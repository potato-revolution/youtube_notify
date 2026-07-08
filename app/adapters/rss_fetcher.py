"""無認証 RSS からの新着取得。チャンネル単位の失敗は握りつぶして継続する。"""

import logging

import feedparser
import httpx

from app.config import HTTP_TIMEOUT, RSS_URL_TEMPLATE
from app.models import Channel, Video

logger = logging.getLogger(__name__)


class RssFetcher:
    def fetch(self, channels: list[Channel]) -> list[Video]:
        videos: list[Video] = []
        for channel in channels:
            try:
                videos.extend(self._fetch_one(channel))
            except Exception as e:
                # 部分失敗の許容: 他チャンネルの処理を継続する(取りこぼしゼロ優先)
                logger.warning(
                    "RSS 取得失敗: channel_id=%s reason=%s",
                    channel.channel_id,
                    type(e).__name__,
                )
        return videos

    def _fetch_one(self, channel: Channel) -> list[Video]:
        url = RSS_URL_TEMPLATE.format(channel_id=channel.channel_id)
        resp = httpx.get(url, timeout=HTTP_TIMEOUT)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
        channel_title = feed.feed.get("title", channel.title)

        videos: list[Video] = []
        for entry in feed.entries:
            video_id = entry.get("yt_videoid", "")
            title = entry.get("title", "")
            link = entry.get("link", "")
            if not video_id or not title or not link:
                # 必須フィールド欠損の項目はスキップ
                continue
            videos.append(
                Video(
                    video_id=video_id,
                    title=title,
                    channel_title=channel_title,
                    url=link,
                    published_at=entry.get("published", ""),
                    rss_summary=entry.get("summary", "") or entry.get("media_description", ""),
                )
            )
        return videos
