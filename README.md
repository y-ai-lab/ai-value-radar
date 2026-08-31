# AI VALUE RADAR v0.1

AI / SaaSの公開情報を1日4回巡回し、Lifetime Deal、値引き、無料クレジット、Affiliate Program、Pricing変更の候補を機械的に絞り込み、上位3件だけをTelegramへ送る小さな監視システムです。70点以上を「有望」、40〜69点を「発信候補・要確認」として扱います。候補ごとの日本語発信用パック（note本文、X投稿、Threads投稿、タイトル案、CTA、ハッシュタグ、公開前チェック）と、スマホ向けの直近レポートも自動保存します。

## できること

```text
公開RSS / 公開API
        ↓
HUNTER      収集
FILTER      URL・タイトル・本文ハッシュで重複除去
SCORER      ルールベース一次採点（0〜70）
ANALYST     任意のCloudflare Workers AIで上位だけ評価
WRITER      日本語通知と公開前発信用パックを生成
OPERATOR    新規・更新・重複を履歴と比較
        ↓
Telegram + data/
```

AIが未設定でも停止せず、ルールベース採点だけで実行します。AIの壊れたJSON、1ソースの失敗、Telegramの失敗は全体を停止させません。

## 発信用パック

Telegramの各候補には、GitHub上の「発信用パック」リンクが付きます。リンクを開くと、候補の概要、価格・条件、なぜ今見るべきか、向く人、見送る人、収益化の見立てに加えて、note本文、X投稿案、Threads投稿案、タイトル案、CTA、ハッシュタグ、公開前チェックリストをMarkdownで確認できます。

発信用パックは追加APIを使わないルールベース生成です。そのため、筆者の実体験を装ったり、自動投稿・自動公開したりしません。公開前に公式Pricing / Deal / Affiliateページを再確認し、自分で試した結果を追記し、必要なPR・アフィリエイト表記を冒頭に置いてください。価格・仕様の確認日もパックに記録されます。

Telegramの末尾には、毎回「発信用パック → 公式条件確認 → 実体験を追記」という次の3ステップと、`data/latest.md`の詳細レポートへのリンクが表示されます。迷ったときはこの順番で確認します。

## 自動実行

GitHub ActionsのPublic Repository上で、標準の`ubuntu-latest` runnerだけを使います。スケジュールはUTCの`05:00 / 11:00 / 17:00 / 23:00`で、日本時間の`14:00 / 20:00 / 翌02:00 / 翌08:00`です。定期実行によるGitHub Actionsの追加運用費は0円です。

`workflow_dispatch`も有効です。Actions → AI VALUE RADAR → Run workflowから、`scan`または`telegram_test`を選べます。

## 最初の設定

このリポジトリで必要な外部設定はGitHub Actions Secretsだけです。

必須：

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

任意：Cloudflare Workers AIを使う場合だけ、次も登録します。

- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_FREE_ONLY_ACK`（値は`I_UNDERSTAND_FREE_ONLY`）

Cloudflare AIはこの明示的な確認値がない限り無効です。Workers Freeプラン以外では使わず、支払い方法を追加しないでください。無料枠を使い切った場合はAI呼び出しが失敗し、ルールベースへ戻ります。AIの上限は1回3候補、1日8呼び出しです。

SecretsはSettings → Secrets and variables → Actions → New repository secretから登録します。値はREADME、コード、ログ、`data/`へ保存しません。

## Telegram通知

通知はスマホで読める短い1メッセージです。新規または重要更新で、対象5カテゴリの40点以上の候補から最大3件を送ります。70点以上は「有望」、40〜69点は「発信候補・要確認」と明記します。各候補に発信用パックのGitHubリンクを付けます。対象がない場合は「今回は有望な発信候補なし」と送ります。同じ内容は履歴で抑止します。

## 監視ソース

v0.1では19件のソース定義を持ちます。

- Hacker Newsの公開JSON検索 4件
- GitHubの公開API（AIリポジトリと公式リリース）5件
- Cloudflare / Zapierの公式RSS 2件
- Product Hunt / AppSumoの公開フィード 2件
- n8n / Zapier / Make / Cloudflare Workers AIの公式Pricingページ 4件
- n8n / HubSpotの公式Affiliateページ 2件

RSS・公開API・単一の公式Pricingページだけを読みます。ログイン、CAPTCHA、ペイウォール回避、サイト全体のクロール、検索結果ページのスクレイピングはしません。各ホストの`robots.txt`を確認し、明示的な拒否または取得不能時はそのソースをスキップします。各リクエストはHTTPS、固定User-Agent、タイムアウト、最大1回の再試行です。

詳細は[`docs/source-audit.md`](docs/source-audit.md)を確認してください。

## 保存データ

- `data/opportunities.json`：公開情報から作った候補履歴
- `data/last_report.json`：直近の実行レポート
- `data/reports/`：直近120回のレポート
- `data/run_history.json`：7日間検証用の実行履歴
- `data/metrics_7d.json`：直近7日間の集計
- `data/errors.jsonl`：ソース単位のエラー記録
- `data/drafts/`：候補ごとの公開前発信用パック（Markdown、最大3件/実行）
- `data/latest.md`：スマホで読みやすい直近監視レポート

保存内容はURL、タイトル、価格、スコア、要約などの公開情報だけです。

## ローカルテスト

外部サービスへ通知せず、標準ライブラリだけでテストできます。

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 scripts/secret_scan.py
```

実データ巡回はGitHub Actionsで実行します。ローカル実行時にTelegram Secretsがなければ通知はスキップされ、レポート保存は続きます。

## 無料運用

- 実行基盤：Public GitHub Repository + 標準GitHub-hosted runner
- AI：任意。Cloudflare Workers AI Freeの無料範囲だけを対象にした安全ガード付き
- データベース：なし。公開JSON / JSONL
- ドメイン：なし
- VPS：なし
- 有料API・有料SaaS：なし
- 発信用パック：追加APIなしのルールベース生成（自動投稿・自動公開なし）

現在の設計上、追加運用費は0円です。GitHubやCloudflareの将来の料金条件が変わった場合は、AIを止めてもルールベースで継続します。

## 停止方法

GitHubのActionsタブで`AI VALUE RADAR` workflowを開き、Disable workflowを選びます。再開はEnable workflowです。

## セキュリティ

Public RepositoryにSecretを置きません。Workflowは必要最小限の`contents: write`だけを使い、コードにSecretを埋め込みません。コミット前に`python3 scripts/secret_scan.py`を実行します。
