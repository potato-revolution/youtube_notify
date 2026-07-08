"""固定順パイプライン: RSS 取得 → 新着判定 → 要約 → HTML 生成 → 送信 → 状態書き戻し。

送信成功後にのみ seen.json を更新する(トランザクション境界)。
"""

import logging

from app.adapters.config_store import ConfigStore
from app.adapters.mail_builder import MailBuilder
from app.adapters.mail_sender import MailSender
from app.adapters.rss_fetcher import RssFetcher
from app.adapters.summarizer import Summarizer
from app.adapters.video_classifier import VideoClassifier
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


def split_excluded(
    videos: list[Video], classifier: VideoClassifier
) -> tuple[list[Video], list[Video]]:
    """Shorts / 終了済みライブを除外リストへ振り分け、(要約対象, 除外) を返す。"""
    kept: list[Video] = []
    excluded: list[Video] = []
    for video in videos:
        if classifier.is_excluded(video):
            excluded.append(video)
        else:
            kept.append(video)
    return kept, excluded


def run_pipeline(
    store: ConfigStore | None = None,
    fetcher: RssFetcher | None = None,
    classifier: VideoClassifier | None = None,
    summarizer: Summarizer | None = None,
    builder: MailBuilder | None = None,
    sender: MailSender | None = None,
) -> int:
    """日次パイプラインを実行し、通知した新着本数を返す。"""
    store = store or ConfigStore()
    fetcher = fetcher or RssFetcher()
    classifier = classifier or VideoClassifier()
    builder = builder or MailBuilder()

    channels = store.load_channels()
    if not channels:
        logger.info("監視チャンネルが未登録のため終了します")
        _log_kpi_summary(channels=0, new=0, ok=0, ng=0, sent=False)
        return 0

    seen = store.load_seen()
    videos = fetcher.fetch(channels)
    candidates = filter_new(videos, seen)
    # Shorts / 終了済みライブを除外(除外分も既読化して翌日以降の再プローブを防ぐ)
    new_videos, excluded = split_excluded(candidates, classifier)
    if excluded:
        logger.info("除外(Shorts/終了済みライブ): %d 本", len(excluded))

    if not new_videos:
        # 新着0本(または全て除外)の日は送信しない
        if excluded:
            store.save_seen([v.video_id for v in excluded])
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

    # 送信成功後にのみ seen を更新する(送信前に落ちても翌日リカバリ可能にするため)。
    # 除外分も併せて既読化する。
    store.save_seen([v.video_id for v in new_videos] + [v.video_id for v in excluded])

    ok = sum(1 for v in new_videos if v.summary_ok)
    _log_kpi_summary(
        channels=len(channels), new=len(new_videos), ok=ok, ng=len(new_videos) - ok, sent=True
    )
    return len(new_videos)


def pick_recent_per_channel(videos: list[Video], recent: int) -> list[Video]:
    """各チャンネルの先頭 recent 本を選ぶ(RSS は新しい順のため直近 N 本になる)。"""
    counts: dict[str, int] = {}
    picked: list[Video] = []
    for video in videos:
        key = video.channel_title
        if counts.get(key, 0) < recent:
            counts[key] = counts.get(key, 0) + 1
            picked.append(video)
    return picked


def seed_pipeline(
    recent_per_channel: int,
    store: ConfigStore | None = None,
    fetcher: RssFetcher | None = None,
    classifier: VideoClassifier | None = None,
    summarizer: Summarizer | None = None,
    builder: MailBuilder | None = None,
    sender: MailSender | None = None,
) -> int:
    """一度きりの初期シード。

    各チャンネル直近 recent_per_channel 本(Shorts / 終了済みライブを除く)のみ
    要約してメール送信し、現在 RSS にある新着の全 ID を既読として記録する。
    これにより、登録直後のバックログ(数十本)を一括要約せずに運用を開始できる。
    以降の run_pipeline は登録後に出た新着のみを処理する。
    """
    store = store or ConfigStore()
    fetcher = fetcher or RssFetcher()
    classifier = classifier or VideoClassifier()
    builder = builder or MailBuilder()

    channels = store.load_channels()
    if not channels:
        logger.info("監視チャンネルが未登録のため終了します")
        return 0

    seen = store.load_seen()
    videos = fetcher.fetch(channels)
    candidates = filter_new(videos, seen)
    if not candidates:
        logger.info("シード対象の新着はありません")
        return 0

    # Shorts / 終了済みライブを除外してから直近 N 本を選ぶ
    included, excluded = split_excluded(candidates, classifier)
    to_summarize = pick_recent_per_channel(included, recent_per_channel)

    # 要約対象がある場合のみ送信する(全て除外なら送信せず既読化のみ)
    if to_summarize:
        summarizer = summarizer or Summarizer()
        sender = sender or MailSender()
        for video in to_summarize:
            summarizer.summarize(video)
        subject, html_body = builder.build(to_summarize)
        sender.send(subject, html_body)  # 失敗時は例外 → seen 未更新のまま異常終了

    # 送信成功後にのみ、現在の新着全 ID(除外分含む)を既読化する(再通知しない)
    store.save_seen([v.video_id for v in candidates])

    ok = sum(1 for v in to_summarize if v.summary_ok)
    logger.info(
        "SEED: channels=%d seeded=%d summarized=%d summary_ok=%d excluded=%d",
        len(channels),
        len(candidates),
        len(to_summarize),
        ok,
        len(excluded),
    )
    return len(to_summarize)


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
