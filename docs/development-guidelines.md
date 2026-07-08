# 開発ガイドライン (Development Guidelines)

本書は本プロジェクト（Python / GitHub Actions パイプライン）のコーディング規約と開発プロセスを定義する。
テンプレートは TypeScript を例示するが、本プロジェクトは **Python** のため以下は Python 前提で記述する。

## コーディング規約

### 命名規則

#### 変数・関数（Python）

```python
# ✅ 良い例
new_videos = detect_new_videos(feed_items, seen_ids)
def build_html_body(videos: list[Video]) -> str: ...

# ❌ 悪い例
data = fetch()
def do(x): ...
```

**原則**:
- 変数・関数・モジュール: snake_case。関数は動詞で始める。
- 定数: UPPER_SNAKE_CASE（`config.py` に集約）。
- Boolean: `is_` / `has_` / `should_` で始める（例: `summary_ok`, `is_new`）。

#### クラス・型

```python
# クラス: PascalCase、名詞
class RssFetcher: ...
class MailSender: ...

# データモデルは dataclass（PascalCase）
from dataclasses import dataclass

@dataclass
class Video:
    video_id: str
    title: str
    summary: str | None
    summary_ok: bool
```

### コードフォーマット

- **インデント**: 4スペース。
- **行の長さ**: 最大 100 文字。
- **フォーマッタ / Lint**: `ruff format` と `ruff check` を使用。
- **型ヒント**: 公開関数・メソッドの引数と戻り値に必ず型注釈を付ける。

```python
def filter_new(videos: list[Video], seen: set[str]) -> list[Video]:
    return [v for v in videos if v.video_id not in seen]
```

### コメント規約

**関数のドキュメント（docstring）**:
```python
def summarize(self, video: Video) -> Video:
    """YouTube URL を Gemini に渡して日本語の構造化要約を生成する。

    失敗時（メンバー限定/非公開/年齢制限/長すぎ/API エラー）は
    summary_ok=False にして返し、呼び出し側で代替表示に委ねる。

    Args:
        video: 要約対象。url を参照する。
    Returns:
        summary / summary_ok を埋めた Video。
    """
```

**インラインコメント**: 「何を」ではなく「なぜ」を書く。
```python
# ✅ 送信成功後にのみ seen を更新する（送信前に落ちても翌日リカバリ可能にするため）
store.save_seen(seen | new_ids)

# ❌ seen を保存する
store.save_seen(seen | new_ids)
```

### エラーハンドリング

**原則（本プロジェクト固有の方針）**:
- **取りこぼしゼロ優先**: 動画単位・チャンネル単位の失敗は握りつぶして継続し、成功分は通知に含める。
- **状態確定は送信成功後のみ**: メール送信に失敗したら `seen.json` を更新せず例外で終了（翌日再通知）。
- 機密（API キー / アプリパスワード）を例外メッセージ・ログに出さない。

```python
# アダプタ内: 動画単位の失敗を局所化
def summarize(self, video: Video) -> Video:
    try:
        video.summary = self._call_gemini(video.url)
        video.summary_ok = True
    except Exception as e:
        logger.warning("summarize failed: video_id=%s reason=%s", video.video_id, type(e).__name__)
        video.summary = None
        video.summary_ok = False
    return video

# パイプライン: 送信失敗は伝播させ、状態を更新しない
sender.send(subject, html)     # 失敗時は例外 → seen 未更新のまま異常終了
store.save_seen(seen | new_ids)
```

**ログ**: 標準 `logging` を使用。`logger.warning` で握りつぶした失敗を記録。例外の `type(e).__name__` は出してよいが、メッセージに秘匿情報が混ざる場合は選別する。

## Git運用ルール

### ブランチ戦略

個人開発・小規模のため軽量運用とする。

- `main`: 常にデプロイ（＝Actions 実行）可能な状態。
- `feature/[機能名]`: 新機能開発。
- `fix/[修正内容]`: バグ修正。

作業は feature/fix ブランチを切り、PR で `main` にマージ（セルフレビュー可）。

> 注意: Actions が `state/seen.json` を自動コミットするため、自動コミットには必ず `[skip ci]` を付け、人手の変更と混同しない。

### コミットメッセージ規約

Conventional Commits に従う。

**フォーマット**: `<type>(<scope>): <subject>`

**Type**: `feat` / `fix` / `docs` / `style` / `refactor` / `test` / `chore`

**例**:
```
feat(summarizer): Gemini による YouTube URL 直渡し要約を実装

- google-genai で URL を part として渡し日本語構造化要約を生成
- 失敗時は summary_ok=False にして代替表示に委譲

Closes #12
```

**自動コミット例**（workflow 内）:
```
chore(state): update seen.json [skip ci]
```

### プルリクエストプロセス

**作成前チェック**:
- [ ] `pytest` が全てパス
- [ ] `ruff check` / `ruff format --check` がパス
- [ ] Secrets や個人情報をコミットに含めていない

**PRテンプレート**:
```markdown
## 概要
[変更内容の簡潔な説明]

## 変更理由
[なぜこの変更が必要か]

## 変更内容
- [変更点1]
- [変更点2]

## テスト
- [ ] ユニットテスト追加
- [ ] workflow_dispatch で手動実行確認（該当時）

## 関連Issue
Closes #[Issue番号]
```

## テスト戦略

テストピラミッド: ユニット中心、統合で結線、E2E は手動（`workflow_dispatch`）。

### ユニットテスト

**対象**: 個別関数・クラス（新着判定、ConfigStore、MailBuilder、ChannelResolver）。
**カバレッジ目標**: コアロジック 80% 以上。
**フレームワーク**: pytest。

```python
def test_filter_new_returns_only_unseen():
    videos = [Video(video_id="a", ...), Video(video_id="b", ...)]
    seen = {"a"}
    result = filter_new(videos, seen)
    assert [v.video_id for v in result] == ["b"]

def test_add_channel_duplicate_is_rejected(tmp_path):
    store = ConfigStore(tmp_path)
    ch = Channel(channel_id="UC1", handle="@x", title="X", added_at="...")
    assert store.add_channel(ch) is True
    assert store.add_channel(ch) is False   # 重複は拒否
```

### 統合テスト

**対象**: RSS/Gemini/SMTP をモック化したパイプライン結線。

```python
def test_pipeline_sends_one_mail_with_new_items(mock_rss, mock_gemini, mock_smtp):
    run_pipeline(...)
    assert mock_smtp.send.call_count == 1

def test_pipeline_no_new_items_does_not_send(mock_rss_empty, mock_smtp):
    run_pipeline(...)
    assert mock_smtp.send.call_count == 0     # 0本の日は送信しない
```

### E2Eテスト

**対象**: 実チャンネルでの `workflow_dispatch` 手動実行。受信メールの体裁と、seen.json 書き戻しによる二重通知防止を確認。

### テスト命名規則

**パターン**: `test_[対象]_[条件]_[期待結果]`

```python
# ✅ 良い例（すべて snake_case）
def test_filter_new_all_seen_returns_empty(): ...
def test_summarize_api_error_sets_summary_ok_false(): ...

# ❌ 悪い例
def test_1(): ...
def test_works(): ...
```

### モック・スタブの使用

**原則**: 外部依存（RSS/Gemini/SMTP/ファイル）はモック化し、判定・生成ロジックは実装を使用。`monkeypatch` / `unittest.mock` を使う。

## コードレビュー基準

### レビューポイント

**機能性**:
- [ ] 要件（取りこぼしゼロ・二重通知ゼロ・0本日未送信）を満たすか
- [ ] エッジケース（RSS 欠損、要約失敗、送信失敗）が考慮されているか

**可読性・保守性**:
- [ ] 命名・型注釈・docstring が明確か
- [ ] アダプタ/パイプラインの責務分離が守られているか（アダプタが制御フローを持たない）
- [ ] 重複がないか

**信頼性**:
- [ ] 送信失敗時に seen が更新されないことが保証されているか
- [ ] 部分失敗が全体を止めないか

**セキュリティ**:
- [ ] Secrets がハードコード/ログ出力されていないか
- [ ] 入力（@handle/URL）検証があるか

### レビューコメントの優先度
- `[必須]` 修正必須 / `[推奨]` 修正推奨 / `[提案]` 検討 / `[質問]` 確認

## 開発環境セットアップ

### 必要なツール

| ツール | バージョン | インストール方法 |
|--------|-----------|-----------------|
| Python | 3.11+ | 公式 / pyenv |
| pip | 同梱 | - |
| ruff | 最新 | `pip install ruff` |
| pytest | ^8.0 | `pip install pytest` |

### セットアップ手順

```bash
# 1. リポジトリのクローン
git clone [URL]
cd youtube_app

# 2. 仮想環境と依存関係
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. 環境変数（ローカル実行用）
export GEMINI_API_KEY=...
export GMAIL_ADDRESS=you@example.com
export GMAIL_APP_PASSWORD=...

# 4. 監視チャンネル追加 → 実行
python -m app.add_channel "@handlename"
python -m app.run
```

### CI/CD

- **CI**: PR / push で `ruff check` と `pytest` を実行。
- **本番実行**: `.github/workflows/notify.yml` が cron `0 13 * * *`（22:00 JST）と `workflow_dispatch` で `python -m app.run` を実行し、`state/seen.json` を `[skip ci]` 付きで commit/push。
- **Secrets**: `GEMINI_API_KEY` / `GMAIL_ADDRESS` / `GMAIL_APP_PASSWORD` を GitHub Secrets に登録。
