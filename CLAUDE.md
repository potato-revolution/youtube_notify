# youtube_app

監視対象 YouTube チャンネルの新着を毎晩 22:00 JST に検出し、Gemini で日本語要約して 1 通の HTML メールで通知する Python パイプライン。設計は `docs/`(PRD / 機能設計 / アーキテクチャ / リポジトリ構造 / 開発ガイドライン / 用語集)、運用は README.md。

## Commands
- Setup: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- Test: `pytest`(`tests/unit/`)。単一ファイルは `pytest tests/unit/test_summarizer.py`
- Lint: `ruff check .` / Format: `ruff format .`(行長 100、py311)
- 手動実行: `python -m app.run`(`GEMINI_API_KEY` / `GMAIL_ADDRESS` / `GMAIL_APP_PASSWORD` が必要)
- チャンネル追加: `python -m app.add_channel "@handle"` → `config/channels.json` に追記

## Conventions
- 構成は `app/pipeline.py`(オーケストレーション)+ `app/adapters/`(RSS / 要約 / メール / 設定などの外部 I/O)。新しい外部連携は adapter として足す
- アダプタ内では動画単位の失敗を局所化し、パイプラインでは送信失敗を伝播させて状態を更新しない
- `state/seen.json` は **送信成功後にのみ** 更新する(送信前に落ちても翌日リカバリできるようにするため)
- 公開関数には型注釈を必ず付ける。データモデルは `app/models.py` の dataclass。詳細は `docs/development-guidelines.md`

## Gotchas
- チャンネル登録直後は RSS に過去動画(最大 15 本)が載るので、`app.run` ではなく `python -m app.seed --recent N` で初回シードする
- Gemini 5xx は指数バックオフで再試行し、使い切ったら `GEMINI_FALLBACK_MODEL` に切替える。この順序を変えない
- 新着 0 本の日はメールを送らない仕様
- 要約には YouTube URL を Gemini に直渡ししている(字幕取得は行わない)
