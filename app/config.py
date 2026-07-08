"""パス定数・モデル ID・Secrets(環境変数)の読み込みを集約する。"""

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
CHANNELS_PATH = ROOT_DIR / "config" / "channels.json"
SEEN_PATH = ROOT_DIR / "state" / "seen.json"

RSS_URL_TEMPLATE = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

# 要約向けモデル。環境変数 GEMINI_MODEL で上書き可能。
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

# seen.json の保持上限(超過分は古い順に切り詰め)
SEEN_IDS_MAX = 5000

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465

HTTP_TIMEOUT = 30.0


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"環境変数 {name} が設定されていません")
    return value


def gemini_api_key() -> str:
    return _require_env("GEMINI_API_KEY")


def gmail_address() -> str:
    return _require_env("GMAIL_ADDRESS")


def gmail_app_password() -> str:
    return _require_env("GMAIL_APP_PASSWORD")
