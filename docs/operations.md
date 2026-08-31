# 運用メモ

## 毎日

Telegramの通知を見るだけです。通知がない場合でも、Actionsの実行結果は`data/last_report.json`と`data/run_history.json`に残ります。

## 失敗時

- 一部ソース失敗：`data/errors.jsonl`を確認。残りのソースは続行。
- AI失敗：`last_report.json`の`ai.errors`を確認。ルールベースで継続。
- Telegram失敗：レポートと履歴は保存済み。SecretsまたはBotの受信先を確認。
- Actions失敗：ActionsのRun → job logを確認。手動の`scan`で再実行。

## 7日間の検証

`data/metrics_7d.json`で以下を確認します。

- 朝起きたときに見る価値があった通知数
- 有望判定数とAffiliate可能案件数
- 発信候補数（40点以上）と有望判定数（70点以上）
- 重複率・エラー率・1回の実行時間
- AI呼び出し件数と誤判定数

「通知が来たか」より、「実際にリンク先を確認する価値があったか」を最重要KPIにします。
