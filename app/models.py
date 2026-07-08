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
    # summary_ok=False のとき、一時的失敗(429/5xx)で次回実行の再試行対象か。
    # 恒久的失敗(メンバー限定/非公開/年齢制限等)は False のまま既読化される。
    summary_retryable: bool = False
