# YouTube 新着要約通知エージェント

監視対象の YouTube チャンネルの新着動画を毎晩 22:00 JST に検出し、Gemini で日本語要約して1通の HTML メールで通知する決定的パイプライン。

- 新着検出: 無認証 RSS(API キー・OAuth 不要)
- 要約: Gemini API に YouTube URL を直渡し(既定モデル: `gemini-2.5-flash`、`GEMINI_MODEL` で上書き可)
- 通知: Gmail SMTP(アプリパスワード)で自分宛てに送信。新着0本の日は送信しない
- 状態: `state/seen.json` に通知済み ID を記録し、リポジトリへコミットして書き戻す(取りこぼし・二重通知なし)
- 実行基盤: GitHub Actions scheduled workflow(`.github/workflows/notify.yml`)

詳細は `docs/` の各ドキュメントを参照(PRD / 機能設計 / アーキテクチャ / リポジトリ構造 / 開発ガイドライン / 用語集)。

## セットアップ

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### GitHub Actions で運用する場合

リポジトリの Secrets に以下を登録:

| Secret | 内容 |
|--------|------|
| `GEMINI_API_KEY` | Gemini API キー |
| `GMAIL_ADDRESS` | 送信元/宛先の Gmail アドレス |
| `GMAIL_APP_PASSWORD` | Gmail アプリパスワード |

## 使い方

```bash
# 監視チャンネルの追加(@handle / URL を channel_id に解決して config/channels.json へ追記)
python -m app.add_channel "@handlename"
python -m app.add_channel "https://www.youtube.com/@handlename"
python -m app.add_channel "https://www.youtube.com/channel/UCxxxxxxxxxxxxxxxxxxxxxx"

# 手動実行(ローカルでは環境変数 GEMINI_API_KEY / GMAIL_ADDRESS / GMAIL_APP_PASSWORD が必要)
python -m app.run
```

定時実行は GitHub Actions が毎晩 22:00 JST(cron `0 13 * * *`)に行う。手動トリガーは Actions タブの workflow_dispatch から。

### 初期シード(登録直後に一度だけ)

チャンネル登録直後は各チャンネルの RSS に過去動画(最大15本)が載っているため、`app.run` をそのまま実行すると大量のバックログを一括要約してしまう。これを避けるため、初回は **シード**を使う。

- 各チャンネル直近 N 本のみ要約してメール送信し、現在の新着全 ID を既読(`seen.json`)として記録する。
- 以降の `app.run` は登録後に出た新着のみを処理する。

GitHub Actions の workflow_dispatch で `seed_recent` に本数(例: `2`)を入力して実行するか、ローカルで:

```bash
python -m app.seed --recent 2
```

`seed_recent` を空欄にすると通常実行(`app.run`)になる。

## 開発

```bash
pytest                  # テスト
ruff check .            # Lint
ruff format .           # フォーマット
```

構成の詳細は `docs/repository-structure.md`、規約は `docs/development-guidelines.md` を参照。
