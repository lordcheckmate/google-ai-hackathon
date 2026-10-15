# 🏆 5th Agentic AI Hackathon with Google Cloud - 提出用パッケージ（最新完全版）

ハッカソン提出フォーム（全4画面）にそのままコピー＆ペーストできる最新版テキストと、デプロイ済みの本番環境情報・最新画像一覧です。

---

## 🌐 1. デプロイ情報 & 審査用アクセス情報

| 項目 | 設定値 |
| :--- | :--- |
| **デプロイURL** | `https://ai-meeting-assistant-7y3l4a2iba-uc.a.run.app` |
| **認証方式** | HTTP Basic Auth + Session Cookie（アクセス制限対応） |
| **ID (UserId)** | `judge` |
| **Password** | `Aegis2026!` |
| **Google Cloud Project** | `project-97d34c6c-e057-425f-987` |
| **GitHubリポジトリ** | `https://github.com/pulliberty11/google-ai-hackathon.git` |
| **ホスティング環境** | Google Cloud Run (`us-central1`, 自動スケール, WebSocket双方向通信) |

> [!NOTE]
> URLにアクセスするとブラウザの標準ログインダイアログが表示されます。上記 `judge` / `Aegis2026!` でログインできます。
> また、`https://ai-meeting-assistant-7y3l4a2iba-uc.a.run.app/?user=judge&pass=Aegis2026!` でアクセスすると自動認証も可能です。

---

## 📋 2. 画面別コピー＆ペースト用テキスト

### 【タブ 1】プロジェクト概要

#### プロジェクト名 *（50文字以内）
```text
AEGIS - リアルタイム商談・会議可視化AIエージェント
```
*(文字数: 30 / 50文字)*

#### プロジェクト概要（200〜300文字程度）
```text
AEGIS（エイジス）は、商談や会議の音声をリアルタイムに理解し、議論の流れやシステム構成図、タスク一覧を自律的にSVG可視化するAIコパイロットです。Google ADKとVertex AI Gemini 3.5 Flash Liteを活用し、発言の蓄積から段階的にフローチャートを自動構築・更新します。さらに、Gemini 3.1 Flash Lite ImageによるNano Bananaイラスト生成や、過去の決定事項との論理的矛盾を自律検知してGoogle Cloud TTSの自然な音声で注意喚起を行います。日英バイリンガル対応と発話中・生成中のデュアル状態表示により、円滑な合意形成を実現します。
```
*(文字数: 279文字 - 200〜300文字の規定範囲内)*

---

### 【タブ 2】プロジェクト紹介

#### 課題と解決（Markdown, 800文字以内）
```markdown
### 解決する課題
1. **メモ取りと対話のマルチタスク不可**: 会議中にメモや図作成に意識が向くと、深い傾聴や発言の機会を逃してしまう。
2. **口頭議論の認識ズレと矛盾の見落とし**: 前半と後半で異なる前提が話されても気づかず、プロジェクト後半で手戻りが発生する。
3. **テキスト議事録の限界**: 従来のAI要約は長文テキストであり、業務フローや関係性を瞬時に把握できない。

### アプローチと解決策
- **自律的ビジュアル生成**: 会話を聞きながら、業務フロー・比較表・チェックリストを自律的にSVG描画。「モデルにマークアップを出力させない（No Markup from Models）」設計により、XSSや表示崩れのない安全で美しいダークOLED図面をリアルタイム生成します。
- **Nano Banana 2 Lite（画像生成コパイロット）**: 議論の要所や業務ステップを音声やクリックで即座にイラスト・図解化（Gemini 3.1 Flash Lite Image）。
- **プロアクティブな矛盾検知**: 会議の文脈履歴を保持し、過去の発言や決定事項と食い違う発言が出た瞬間に、画面警告とGoogle Cloud TTS音声で自律的に指摘・介入します。
- **デュアル状態インジケーター**: 発話中とAI生成中が同時に行われている状態を視覚的にオレンジ点滅で明示し、ユーザーの不安を解消。
- **日英バイリンガル対応**: 日本語（ja-JP）と英語（en-US）のシームレスな自動切り替えと、声とクリックの完全な等価性を実現。
```

#### アーキテクチャ説明（Markdown, 800文字以内）
```markdown
### 採用技術スタックと構成
- **フロントエンド**: HTML5 / CSS3 / Vanilla JS、Web Audio API（16kHz PCMストリーミングマイク入力）、デュアル状態表示、リアルタイムSVGレンダラー。
- **バックエンド**: FastAPI (Python 3.11)、WebSockets（双方向通信）、Starlette HTTP Basic Auth & Session Cookie認証。
- **エージェント基盤**: **Google ADK (`google-adk`)** を採用。自律ツール実行ループ（`upsert_block`, `remove_block`, `remove_step`, `highlight`, `illustrate_step`, `flag_contradiction`）をオーケストレーション。
- **AI・LLMスタック**:
  - **Vertex AI Gemini 3.5 Flash Lite**: 超低遅延な発言理解、差分推論、スキーマ準拠JSON生成。
  - **Gemini 3.1 Flash Lite Image (Nano Banana 2 Lite)**: 高解像度イラスト・図解生成。
  - **Google Cloud Speech-to-Text v2**: リアルタイム双方向音声認識（日英対応）。
  - **Google Cloud Text-to-Speech**: Neural2 高品質日本語/英語音声合成（矛盾警告）。
- **インフラ**: **Google Cloud Run**（セッションアフィニティ、自動スケール、1時間タイムアウト）、Cloud Storage / Firestore。

### 設計上の工夫
1. **No Markup from Models**: LLMはPydanticで型定義されたJSON差分のみを出力し、Pythonが確定的にSVGを描画。HTMLタグ欠損やレイアウト崩れを完全に防止。
2. **適応型デバウンス制御**: 発話停止2秒または15秒継続発話ごとの送信バッファリングにより、Gemini APIの無駄な連打を防ぎつつ快適なレスポンスを両立。
```

#### アーキテクチャ図（画像アップロード用）
- ワークスペース直下に最新構成図を用意済みです：
  👉 `architecture_diagram.png`
  （※Gemini 3.5 Flash Lite、Gemini 3.1 Flash Lite Image、Google ADK、Cloud Run、Cloud STT/TTS、デュアル状態表示が明記された最新高解像度画像）

#### プロジェクトイメージ（最大10枚用）
すべて Google Cloud Run 本番環境から直接キャプチャした最新画像です：
1. `architecture_diagram.png`（最新システム構成図）
2. `submission_screenshots/01_dashboard_standby.png`（ダークOLEDダッシュボード・接続状態）
3. `submission_screenshots/02_flow_v1_restaurant.png`（レストランQRオーダー フローチャート初期生成）
4. `submission_screenshots/03_flow_v2_restaurant.png`（キッチン連携ステップ追加・タイムライン更新）
5. `submission_screenshots/04_nano_banana_illustrated.png`（Nano Banana 2 Lite イラスト生成タブ）
6. `submission_screenshots/05_contradiction_alert.png`（自律的矛盾検知・AI警告カード表示）
7. `submission_screenshots/06_compare_table.png`（QRコード注文 vs 専用タブレット 比較表）
8. `submission_screenshots/07_checklist_tasks.png`（導入タスクチェックリスト）

---

### 【タブ 3】審査向け情報

#### GitHubリポジトリ
```text
https://github.com/pulliberty11/google-ai-hackathon.git
```

#### デプロイURL
```text
https://ai-meeting-assistant-7y3l4a2iba-uc.a.run.app
```

#### 動作確認の方法
```text
ID : judge
Password : Aegis2026!

【アクセス・動作確認手順】
1. 上記デプロイURLにアクセスします。
2. ブラウザの認証ダイアログが表示されたら、IDに「judge」、Passwordに「Aegis2026!」を入力してログインしてください。
3. 画面右上の言語セレクターで「JA (日本語)」または「EN (English)」を選択できます（デフォルトで日英両対応）。
4. マイクボタン（またはスペースキー）を押して音声で話すか、右上のテキストボックスから入力を行ってください。
※発話完了後、約2秒の無音（または15秒の継続発話）で自動的にGeminiへ送信され、ロボットアバターがオレンジに点滅しながらビジュアル生成を開始します。

【推奨動作確認シナリオ（レストランQRオーダー＆アンケートシステム）】
以下の順で発話またはテキスト送信をお試しいただくと、AEGISの全主要機能を3分で網羅できます：

① フロー自動生成（初期ステップ）:
「レストランのモバイルオーダーの流れを整理しましょう。まずお客様が卓上のQRコードをスマホで読み取り、アプリ不要でWebメニューを開いて料理を選びます。」
→ 画面にフローチャート（v1）が自動描画されます。

② フロー更新・追加ステップ:
「続いて、お客様が料理をカートに入れて注文を確定し、厨房のキッチンディスプレイにデータが即座に届き、調理後に料理が配膳されます。」
→ 既存フローを保持したまま、新しいステップが追加された（v2）タブが生成されます。

③ ナノバナナ画像生成（イラスト化）:
「エイジス、QRコード読み取りステップのイラストを描いて」
→ QRコード読み取りノードにNano Bananaのイラストが生成・添付されます。

④ 矛盾検知（AIプロアクティブ介入）:
「ちょっと待ってください。うちの店はスマホ注文は禁止で、レジで現金払いのみです。」
→ 過去の決定事項と矛盾することをAIが自動検知し、画面上に赤い矛盾警告カードを表示＋音声で注意喚起します。

⑤ ハイライトとステップ削除:
「スマホ決済のステップをハイライトして、配膳のステップを削除してください」
→ ノードの枠線が強調され、指定されたノードが安全に削除されて前後の線が自動で繋ぎ直されます。
```

---

## ✅ 3. 提出前最終チェックリスト

- [x] **Google Cloud アプリケーション実行プロダクト**: Google Cloud Run（Revision 7 稼働確認済み）
- [x] **Google Cloud AI 技術**: Vertex AI Gemini 3.5 Flash Lite, Gemini 3.1 Flash Lite Image, Google ADK, Cloud STT v2, Cloud Text-to-Speech Neural2（すべて本番稼働中）
- [x] **認証機能**: ID (`judge`) / Password (`Aegis2026!`) によるセキュアなアクセス制限
- [x] **最新スクリーンショット**: 本番環境から取得した7枚のPNG画像を `submission_screenshots/` に格納済み
- [x] **最新システム構成図**: `architecture_diagram.png` 更新済み
- [x] **GitHubリポジトリ**: 最新コミットが `origin/main` へ push 完了
