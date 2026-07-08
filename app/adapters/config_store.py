"""channels.json / seen.json の読み書き。

seen の保存は追記セマンティクス(挿入順を保持し、上限超過分を古い順に切り詰める)。
"""

import json
from collections.abc import Iterable
from dataclasses import asdict
from pathlib import Path

from app.config import CHANNELS_PATH, SEEN_IDS_MAX, SEEN_PATH
from app.models import Channel


class ConfigStore:
    def __init__(
        self,
        channels_path: Path = CHANNELS_PATH,
        seen_path: Path = SEEN_PATH,
        max_seen: int = SEEN_IDS_MAX,
    ) -> None:
        self._channels_path = channels_path
        self._seen_path = seen_path
        self._max_seen = max_seen

    def load_channels(self) -> list[Channel]:
        data = self._load_json(self._channels_path, default={"channels": []})
        return [Channel(**entry) for entry in data.get("channels", [])]

    def add_channel(self, channel: Channel) -> bool:
        """チャンネルを追記する。重複(同一 channel_id)は追記せず False を返す。"""
        channels = self.load_channels()
        if any(c.channel_id == channel.channel_id for c in channels):
            return False
        channels.append(channel)
        self._write_json(self._channels_path, {"channels": [asdict(c) for c in channels]})
        return True

    def load_seen(self) -> set[str]:
        return set(self._load_seen_list())

    def save_seen(self, new_ids: Iterable[str]) -> None:
        """通知済み ID を追記する。呼び出しは送信成功後に限ること。"""
        ids = self._load_seen_list()
        known = set(ids)
        for vid in new_ids:
            if vid not in known:
                ids.append(vid)
                known.add(vid)
        # 上限超過分は古い順に切り詰める
        ids = ids[-self._max_seen :]
        self._write_json(self._seen_path, {"seen_ids": ids})

    def _load_seen_list(self) -> list[str]:
        data = self._load_json(self._seen_path, default={"seen_ids": []})
        return list(data.get("seen_ids", []))

    @staticmethod
    def _load_json(path: Path, default: dict) -> dict:
        # ファイル未作成は初回実行として空扱い。破損(パース不能)は例外で停止。
        if not path.exists():
            return default
        with path.open(encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _write_json(path: Path, data: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
