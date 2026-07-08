# リポジトリ構造定義書 (Repository Structure Document)

本書は `docs/architecture.md` のレイヤード（パイプライン指向）構成を、具体的なディレクトリ・ファイル配置に落とし込む。
言語は Python。パッケージ名は `app`、実行は `python -m app.run` / `python -m app.add_channel`。

## プロジェクト構造

```
youtube_app/
├── app/                       # ソースコード（Python パッケージ）
│   ├── __init__.py
│   ├── run.py                 # エントリ: 日次パイプライン（app.run）
│   ├── add_channel.py         # エントリ: 監視チャンネル追加（app.add_channel）
│   ├── pipeline.py            # オーケストレーション（固定順の結線・状態確定）
│   ├── config.py              # 定数・設定・環境変数(Secrets)読み込み
│   ├── models.py              # データモデル（Channel / Video / SeenState）
│   └── adapters/              # アダプタレイヤー（外部 I/O をカプセル化）
│       ├── __init__.py
│       ├── config_store.py    # channels.json / seen.json の読み書き
│       ├── channel_resolver.py# @handle/URL → channel_id 解決
│       ├── rss_fetcher.py     # 無認証 RSS の取得・パース
│       ├── summarizer.py      # Gemini 要約
│       ├── mail_builder.py    # HTML メール生成
│       └── mail_sender.py     # Gmail SMTP 送信
├── config/
│   └── channels.json          # 監視チャンネル一覧（コミット管理）
├── state/
│   └── seen.json              # 通知済み動画 ID（コミット管理・実行毎に書き戻し）
├── tests/                     # テストコード
│   ├── unit/                  # ユニットテスト（app と同じ構造）
│   ├── integration/           # 統合テスト（パイプライン結線）
│   └── fixtures/              # RSS/レスポンスのモックデータ
├── docs/                      # プロジェクトドキュメント（永続6ドキュメント）
├── .github/
│   └── workflows/
│       └── notify.yml         # scheduled workflow（22:00 JST / cron 0 13 * * *）
├── requirements.txt           # 依存関係
├── pyproject.toml             # ruff/pytest 等のツール設定
├── .gitignore
└── README.md
```

## ディレクトリ詳細

### app/ (ソースコードディレクトリ)

#### app/（トップレベル）

**役割**: エントリポイントとオーケストレーション、横断的な設定・モデルを配置。

**配置ファイル**:
- `run.py` / `add_channel.py`: `python -m app.xxx` で実行されるエントリ。引数受付・ログ初期化・終了コードのみを担当。
- `pipeline.py`: アダプタを固定順で結線。新着判定と「送信成功後のみ seen 更新」のトランザクション境界。
- `config.py`: パス定数・Gemini モデル ID・環境変数（`GEMINI_API_KEY` / `GMAIL_ADDRESS` / `GMAIL_APP_PASSWORD`）の読み込み。
- `models.py`: `Channel` / `Video` / `SeenState`（dataclass）。

**命名規則**:
- モジュール名: snake_case（`mail_sender.py`）。
- クラス名: PascalCase（`MailSender`）。関数名: snake_case。定数: UPPER_SNAKE_CASE。

**依存関係**:
- 依存可能: `app.adapters`, `app.config`, `app.models`
- 依存禁止: エントリ（run/add_channel）を adapters から import しない。

#### app/adapters/

**役割**: 外部システム（RSS / Gemini / Gmail）とファイル I/O をカプセル化。失敗の局所化（チャンネル/動画単位の握りつぶし）を担う。

**配置ファイル**:
- `config_store.py`: JSON の読み書き、チャンネル重複拒否、seen の読み書き。
- `channel_resolver.py`: 入力パースと channel_id 解決。
- `rss_fetcher.py`: RSS 取得・パース → `Video[]`。
- `summarizer.py`: Gemini 呼び出し、失敗時 `summary_ok=False`。
- `mail_builder.py`: `Video[]` → `(subject, html)`。
- `mail_sender.py`: SMTP 送信（失敗時に例外）。

**依存関係**:
- 依存可能: `app.models`, `app.config`, 外部ライブラリ（httpx/feedparser/google-genai/標準）
- 依存禁止: `app.pipeline`（アダプタは制御フローを知らない）。

### config/ ・ state/ (データディレクトリ)

**役割**: コミット管理する設定・状態を分離配置。

- `config/channels.json`: 手動管理の監視リスト。`add_channel` が追記。
- `state/seen.json`: 既読 ID。`run` が送信成功後に更新し、workflow が commit/push。

いずれも機密を含まないため Git 管理してよい（`.gitignore` に入れない）。

### tests/ (テストディレクトリ)

#### tests/unit/

**役割**: ユニットテストを `app/` と対応する構造で配置。

**構造**:
```
tests/unit/
├── test_config_store.py       # 重複拒否・seen 読み書き
├── test_filter_new.py          # 新着差分（pipeline 内ロジック filter_new）
├── test_mail_builder.py       # 要約成功/失敗の HTML
└── test_channel_resolver.py   # @handle/URL パース
```

**命名規則**: `test_[対象].py`（pytest 既定の discovery 準拠）。

#### tests/integration/

**役割**: RSS/Gemini/SMTP をモック化した結線テスト。

**構造**:
```
tests/integration/
├── test_pipeline_flow.py      # 取得→差分→要約→HTML→送信
└── test_no_new_items.py       # 0本のとき未送信
```

#### tests/fixtures/

**役割**: RSS XML / Gemini レスポンス等のモックデータ。

### docs/ (ドキュメントディレクトリ)

**配置ドキュメント**:
- `product-requirements.md`: プロダクト要求定義書
- `functional-design.md`: 機能設計書
- `architecture.md`: アーキテクチャ設計書
- `repository-structure.md`: リポジトリ構造定義書（本書）
- `development-guidelines.md`: 開発ガイドライン
- `glossary.md`: 用語集
- `ideas/`: 初期要件（`initial-requirements.md`）

### .github/workflows/

**役割**: GitHub Actions 定義。

- `notify.yml`: `schedule`（cron `0 13 * * *`）と `workflow_dispatch`。Secrets を env 注入 → `python -m app.run` → seen.json を commit/push（`[skip ci]`）。

## ファイル配置規則

### ソースファイル

| ファイル種別 | 配置先 | 命名規則 | 例 |
|------------|--------|---------|-----|
| エントリポイント | `app/` | snake_case | `run.py`, `add_channel.py` |
| オーケストレーション | `app/` | snake_case | `pipeline.py` |
| アダプタ | `app/adapters/` | snake_case | `rss_fetcher.py` |
| モデル | `app/models.py` | 単一ファイル | dataclass 群 |

### テストファイル

| テスト種別 | 配置先 | 命名規則 | 例 |
|-----------|--------|---------|-----|
| ユニットテスト | `tests/unit/` | `test_[対象].py` | `test_config_store.py` |
| 統合テスト | `tests/integration/` | `test_[シナリオ].py` | `test_pipeline_flow.py` |
| モックデータ | `tests/fixtures/` | 内容準拠 | `sample_feed.xml` |

### 設定ファイル

| ファイル種別 | 配置先 | 命名規則 |
|------------|--------|---------|
| 定数・環境変数読み込み | `app/config.py` | - |
| 監視リスト/状態 | `config/`, `state/` | `*.json` |
| ツール設定 | プロジェクトルート | `pyproject.toml` |
| 依存 | プロジェクトルート | `requirements.txt` |

## 命名規則

### ディレクトリ名
- レイヤー/グルーピング: 複数形 snake_case（`adapters/`, `tests/`）。

### ファイル名（Python）
- モジュール: snake_case（`mail_sender.py`）。
- クラス: ファイル内で PascalCase（`MailSender`）。
- 定数モジュール: `config.py` に集約。

### テストファイル名
- パターン: `test_[対象].py`。

## 依存関係のルール

### レイヤー間の依存

```
エントリ (run.py / add_channel.py)
    ↓ (OK)
オーケストレーション (pipeline.py)
    ↓ (OK)
アダプタ (adapters/*) → 外部 I/O・JSON
```

**禁止される依存**:
- アダプタ → pipeline（❌）
- アダプタ → エントリ（❌）
- pipeline → エントリ（❌）

### 循環依存の禁止
- 共有型は `app/models.py` に集約し、双方向 import を避ける。

## スケーリング戦略

### 機能の追加
1. **小規模**: 既存アダプタ/関数に追記。
2. **中規模**: `adapters/` に新規モジュールを追加し pipeline から結線。
3. **大規模**: 送信・要約バックエンドの差し替えは、同一インターフェースの別アダプタとして追加。

### ファイルサイズの管理
- 1ファイル 300 行以下を推奨。超過時は責務単位で分割（例: 要約プロンプト生成を切り出し）。

## 特殊ディレクトリ

### .steering/
**役割**: 個別作業の要求・設計・タスクリストを記録（一時ファイル）。
**命名規則**: `YYYYMMDD-task-name/`（例: `20260708-add-retry`）。`.gitignore` 対象。

### .claude/
**役割**: Claude Code 設定（`commands/` `skills/` `agents/`）。

## 除外設定

### .gitignore
- `__pycache__/`, `*.pyc`
- `.venv/`, `venv/`
- `.env`
- `.steering/`
- `*.log`
- `.DS_Store`
- `.pytest_cache/`, `.ruff_cache/`, `coverage*`

> 注意: `config/channels.json` と `state/seen.json` は **除外しない**（Git 管理・書き戻し対象）。
