"""固定順パイプライン: RSS 取得 → 新着判定 → 要約 → HTML 生成 → 送信 → 状態書き戻し。

送信成功後にのみ seen.json を更新する(トランザクション境界)。
"""

import logging

from app.adapters.config_store import ConfigStore
from app.adapters.mail_builder import MailBuilder
from app.adapters.mail_sender import MailSender
from app.adapters.rss_fetcher import RssFetcher
from app.adapters.summarizer import Summarizer
from app.models import Video

logger = logging.getLogger(__name__)


def filter_new(videos: list[Video], seen: set[str]) -> list[Video]:
    """seen に無い動画のみを抽出する。同一実行内の重複 video_id も除去する。"""
    new_videos: list[Video] = []
    picked: set[str] = set()
    for video in videos:
        if video.video_id in seen or video.video_id in picked:
            continue
        picked.add(video.video_id)
        new_videos.append(video)
    return new_videos


def run_pipeline(
    store: ConfigStore | None = None,
    fetcher: RssFetcher | None = None,
    summarizer: Summarizer | None = None,
    builder: MailBuilder | None = None,
    sender: MailSender | None = None,
) -> int:
    """日次パイプラインを実行し、通知した新着本数を返す。"""
    store = store or ConfigStore()
    fetcher = fetcher or RssFetcher()
    builder = builder or MailBuilder()

    channels = store.load_channels()
    if not channels:
        logger.info("監視チャンネルが未登録のため終了します")
        _log_kpi_summary(channels=0, new=0, ok=0, ng=0, sent=False)
        return 0

    seen = store.load_seen()
    videos = fetcher.fetch(channels)
    new_videos = filter_new(videos, seen)

    if not new_videos:
        # 新着0本の日は送信しない
        _log_kpi_summary(channels=len(channels), new=0, ok=0, ng=0, sent=False)
        return 0

    # Summarizer / MailSender は新着がある場合のみ生成する
    # (新着0本の実行では Secrets 不要で完走できる)
    summarizer = summarizer or Summarizer()
    sender = sender or MailSender()

    for video in new_videos:
        summarizer.summarize(video)

    subject, html_body = builder.build(new_videos)
    sender.send(subject, html_body)  # 失敗時は例外 → seen 未更新のまま異常終了

    # 送信成功後にのみ seen を更新する(送信前に落ちても翌日リカバリ可能にするため)
    store.save_seen([v.video_id for v in new_videos])

    ok = sum(1 for v in new_videos if v.summary_ok)
    _log_kpi_summary(
        channels=len(channels), new=len(new_videos), ok=ok, ng=len(new_videos) - ok, sent=True
    )
    return len(new_videos)


def _log_kpi_summary(channels: int, new: int, ok: int, ng: int, sent: bool) -> None:
    """KPI 測定用サマリー(docs/architecture.md「運用監視・KPI 測定」の実装要件)。"""
    logger.info(
        "KPI: channels=%d new=%d summary_ok=%d summary_ng=%d sent=%s",
        channels,
        new,
        ok,
        ng,
        "yes" if sent else "no",
    )
