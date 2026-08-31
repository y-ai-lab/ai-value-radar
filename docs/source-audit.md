# Source audit — AI VALUE RADAR v0.1

## 方針

収益候補の探索はAI / SaaSに限定し、公開RSS、公開JSON API、公式の公開Pricingページだけを対象にします。認証の回避、CAPTCHAの解決、robotsの拒否を無視した取得、ペイウォール越しの取得、サイト全体の巡回は行いません。

`src/ai_value_radar/sources.py`の各ソースには、プロトコル、公式性、取得上限、利用目的を記録しています。実行時はホストごとに`robots.txt`を一度確認し、明示的に拒否されたエンドポイントは読みません。robotsが取得できない場合も、そのホストは保守的にスキップします。

## 登録ソース

| ID | 形式 | 目的 | 取得範囲 |
|---|---|---|---|
| `hn_ai_saas` | 公開JSON API | AI SaaSの新規話題 | タイトル・短い本文 |
| `hn_lifetime_deal` | 公開JSON API | Lifetime Deal | タイトル・短い本文 |
| `hn_affiliate_program` | 公開JSON API | Affiliate | タイトル・短い本文 |
| `hn_pricing` | 公開JSON API | Pricing変更 | タイトル・短い本文 |
| `github_ai_repositories` | GitHub公式API | AI / SaaSリポジトリ | 公開メタデータ |
| `github_n8n_releases` | GitHub公式API | n8n更新 | リリース本文 |
| `github_flowise_releases` | GitHub公式API | Flowise更新 | リリース本文 |
| `github_openwebui_releases` | GitHub公式API | Open WebUI更新 | リリース本文 |
| `github_litellm_releases` | GitHub公式API | LiteLLM更新 | リリース本文 |
| `github_dify_releases` | GitHub公式API | Dify更新 | リリース本文 |
| `github_langflow_releases` | GitHub公式API | Langflow更新 | リリース本文 |
| `github_ollama_releases` | GitHub公式API | Ollama更新 | リリース本文 |
| `github_anythingllm_releases` | GitHub公式API | AnythingLLM更新 | リリース本文 |
| `github_comfyui_releases` | GitHub公式API | ComfyUI更新 | リリース本文 |
| `cloudflare_blog` | 公式RSS | AI / SaaS発表 | RSS本文 |
| `zapier_blog` | 公式RSS | 自動化・Pricing話題 | RSS本文 |
| `openai_news` | 公式RSS | OpenAIの製品・研究発表 | RSS本文 |
| `google_ai_blog` | 公式RSS | Google AI発表 | RSS本文 |
| `aws_machine_learning_blog` | 公式RSS | AI実装・サービス発表 | RSS本文 |
| `huggingface_blog` | 公式RSS | AIモデル・アプリ発表 | RSS本文 |
| `google_deepmind_blog` | 公式RSS | AI研究・製品発表 | RSS本文 |
| `product_hunt_feed` | 公開Atom | 新規プロダクト | フィード項目 |
| `appsumo_feed` | 公開RSS | Deal情報 | フィード項目 |
| `n8n_pricing_page` | 公式ページ | Pricing変更 | 1ページの要約 |
| `zapier_pricing_page` | 公式ページ | Pricing変更 | 1ページの要約 |
| `make_pricing_page` | 公式ページ | Pricing変更 | 1ページの要約 |
| `cloudflare_workers_ai_pricing` | 公式ページ | AI利用条件変更 | 1ページの要約 |
| `n8n_affiliate_page` | 公式ページ | Affiliate報酬・条件 | 1ページの要約 |
| `hubspot_affiliate_page` | 公式ページ | Affiliate報酬・条件 | 1ページの要約 |

公式Pricingページはサイト内リンクをたどらず、URLを1回読むだけです。Dynamic pageやbot対策で取得できない場合はエラーとして記録し、他のソースを続行します。

## コスト・レート制御

- HTTPリクエスト上限：1実行60回
- HTTPタイムアウト：12秒
- 再試行：一時的な失敗に最大1回
- 取得項目：ソースごとに最大24件程度
- AI：1実行最大3件、UTC日次最大8回
- Telegram：1実行最大1メッセージ、候補は最大3件
- Actions：`ubuntu-latest`の標準runner、実行上限10分

## 確認すべき公式情報

- [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions)：Public Repositoryで標準GitHub-hosted runnerを使う場合の無料条件
- [GitHub runner選択](https://docs.github.com/actions/using-jobs/choosing-the-runner-for-a-job)：`ubuntu-latest`が標準runnerであること
- [Cloudflare Workers AI pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/)：Workers Freeの1日10,000 Neurons、超過時はFreeでは追加処理が失敗すること
- [Cloudflare Workers AI limits](https://developers.cloudflare.com/workers-ai/platform/limits/)：テキスト生成のレート制限
- [Telegram Bot API](https://core.telegram.org/bots/api)：`sendMessage`の公開Bot API

これらは作業開始時点の公式ページを確認した結果です。料金や利用条件は将来変わる可能性があるため、v0.1ではAIを任意機能にし、無料条件に不確実性が出たらルールベースへ戻れる構造にしています。
