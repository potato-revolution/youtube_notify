"""動画が Shorts / 終了済みライブかを無認証プローブで判定する。

RSS(feeds/videos.xml)には尺・ライブ・Shorts の区別が無いため、YouTube への
追加 HTTP リクエストで判定する:
- Shorts: https://www.youtube.com/shorts/{id} が 200 を返す
          (通常動画・ライブは 303 で /watch にリダイレクトする)
- 終了済みライブ: watch ページ HTML に `"isLiveContent":true` が含まれる

プローブ失敗時(ネットワークエラー等)は除外しない=通常動画として要約に回す
(取りこぼしゼロ優先。誤って本編動画を落とすより Shorts を1本通す方を選ぶ)。
"""

import logging

import httpx

from app.config import HTTP_TIMEOUT, HTTP_USER_AGENT
from app.models import Video

logger = logging.getLogger(__name__)

_SHORTS_URL = "https://www.youtube.com/shorts/{video_id}"
_WATCH_URL = "https://www.youtube.com/watch?v={video_id}"
_LIVE_MARKER = '"isLiveContent":true'


class VideoClassifier:
    """Shorts / 終了済みライブなら True を返し、要約対象から除外する。"""

    def is_excluded(self, video: Video) -> bool:
        try:
            if self._is_short(video.video_id):
                return True
            return self._is_live(video.video_id)
        except Exception as e:
            logger.warning(
                "分類失敗のため除外せず継続: video_id=%s reason=%s",
                video.video_id,
                type(e).__name__,
            )
            return False

    def _is_short(self, video_id: str) -> bool:
        # Short は /shorts/{id} が 200、通常動画・ライブは 303 でリダイレクトする
        resp = httpx.head(
            _SHORTS_URL.format(video_id=video_id),
            timeout=HTTP_TIMEOUT,
            follow_redirects=False,
            headers={"User-Agent": HTTP_USER_AGENT},
        )
        return resp.status_code == 200

    def _is_live(self, video_id: str) -> bool:
        resp = httpx.get(
            _WATCH_URL.format(video_id=video_id),
            timeout=HTTP_TIMEOUT,
            headers={"User-Agent": HTTP_USER_AGENT},
        )
        resp.raise_for_status()
        return _LIVE_MARKER in resp.text
