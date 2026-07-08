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

# Gemini 1 リクエストのタイムアウト(ミリ秒)。
# 長尺動画(40〜60分)でも処理を完了できるよう長めに取りつつ、
# ハングでジョブ全体が止まらないよう上限は設ける。
GEMINI_TIMEOUT_MS = 600_000

# 一時的な ServerError(5xx=混雑等)に対する追加リトライ回数と待機秒数。
GEMINI_RETRY = 2
GEMINI_RETRY_WAIT_SEC = 10

# レート/クォータ超過(429)に対する追加リトライ回数と待機秒数。
# RPM/TPM は約60秒窓でリセットされるため、5xx より長めに待ってから再試行する。
# (日次クォータ超過なら実行内リトライでは解消しないが、その場合も seen 未登録のまま
#  残るため翌日以降の実行で自動リトライされる。)
GEMINI_RATE_LIMIT_RETRY = 1
GEMINI_RATE_LIMIT_WAIT_SEC = 30

# 動画要約のトークン消費を抑える設定(無料枠のクォータ超過=429 対策)。
# fps は既定 1.0 → 0.2(5秒に1フレーム)。音声主体の動画なら精度への影響は小さい。
GEMINI_VIDEO_FPS = 0.2
GEMINI_MEDIA_RESOLUTION = "MEDIA_RESOLUTION_LOW"
# 連続する動画要約の間に挟む待機秒数(1分あたりレート上限=TPM 対策)。
GEMINI_REQUEST_SPACING_SEC = 5

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465

HTTP_TIMEOUT = 30.0

# Shorts / ライブ判定プローブ用の User-Agent。ブラウザを装わないと watch ページの
# 一部フラグ(isLiveContent 等)が省略されることがあるため明示する。
HTTP_USER_AGENT = "Mozilla/5.0"


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
