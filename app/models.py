"""データモデル定義(docs/functional-design.md のエンティティに対応)。"""

from dataclasses import dataclass


@dataclass
class Channel:
    """監視チャンネル(config/channels.json の1エントリ)。"""

    channel_id: str
    handle: str
    title: str
    added_at: str


@dataclass
class Video:
    """実行時のみメモリに存在する動画表現。"""

    video_id: str
    title: str
    channel_title: str
    url: str
    published_at: str
    rss_summary: str = ""
    summary: str | None = None
    summary_ok: bool = False
