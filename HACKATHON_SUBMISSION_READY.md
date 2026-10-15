# 🏆 5th Agentic AI Hackathon with Google Cloud - 提出用パッケージ

ハッカソン提出フォーム（全4画面）にそのままコピー＆ペーストできる完成版テキストと、デプロイ済みの本番環境情報です。

---

## 🌐 1. デプロイ情報 & 審査用アクセス情報

| 項目 | 設定値 |
| :--- | :--- |
| **デプロイURL** | `https://ai-meeting-assistant-7y3l4a2iba-uc.a.run.app` |
| **認証方式** | HTTP Basic Auth + Session Cookie（アクセス制限対応） |
| **ID (UserId)** | `judge` |
| **Password** | `Aegis2026!` |
| **GitHubリポジトリ** | `https://github.com/pulliberty11/google-ai-hackathon.git` |
| **ホスティング環境** | Google Cloud Run (`us-central1`, 自動スケール, WebSocket対応) |

> [!NOTE]
> URLにアクセスするとブラウザの標準ログインダイアログが表示されます。上記 `judge` / `Aegis2026!` でログインできます。
> また、`https://ai-meeting-assistant-7y3l4a2iba-uc.a.run.app/?user=judge&pass=Aegis2026!` でアクセスすると自動ログインも可能です。

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
AEGIS（エイジス）は、商談や会議の音声をリアルタイムに理解し、議論の流れやシステム構成図、タスク一覧を自律的にSVG可視化するAIコパイロットです。Google ADKとGemini 2.5 Flashを活用し、発言の蓄積から段階的にフローチャートを自動構築・更新します。さらに、過去の決定事項との論理的矛盾を発見すると自律的にアラートを発し、Google Cloud TTSの自然な音声で注意喚起を行います。議事録の文字起こしに留まらず、参加者全員の共通理解を瞬時に生み出す次世代の会議体験を実現します。
```
*(文字数: 248文字 - 200〜300文字の規定範囲内)*

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
- **Nano Banana（画像生成コパイロット）**: 議論の要所や業務ステップをワンクリックまたは音声指示でイラスト・図解化（Gemini 3.1 Flash Image）。
- **プロアクティブな矛盾検知**: 会議の文脈履歴を保持し、過去の発言や決定事項と食い違う発言が出た瞬間に、画面警告とGoogle Cloud TTS音声で自律的に指摘・介入します。
- **声とクリックの完全な等価性**: 声でもUIクリックでも同じ操作（ハイライト、ステップ削除、詳細解説モーダル表示）が可能です。
```

#### アーキテクチャ説明（Markdown, 800文字以内）
```markdown
### 採用技術スタックと構成
- **フロントエンド**: HTML5 / CSS3 / Vanilla JS、Web Audio API（16kHz PCMストリーミングマイク入力）、リアルタイムSVGレンダラー。
- **バックエンド**: FastAPI (Python 3.11)、WebSockets（双方向通信）、Starlette HTTP Basic Auth & Session Cookie認証。
- **エージェント基盤**: **Google ADK (`google-adk`)** を採用。自律ツール実行ループ（`upsert_block`, `remove_block`, `highlight`, `illustrate_step`, `flag_contradiction`）をオーケストレーション。
- **AI・LLMスタック**:
  - **Vertex AI Gemini 2.5 Flash**: 超低遅延な発言理解、差分推論、スキーマ準拠JSON生成。
  - **Gemini 3.1 Flash Image (Nano Banana)**: 高解像度ベクター調イラスト・図解生成。
  - **Google Cloud Speech-to-Text v2**: リアルタイム双方向音声認識。
  - **Google Cloud Text-to-Speech**: Neural2 高品質日本語/英語音声合成（矛盾警告）。
- **インフラ**: **Google Cloud Run**（セッションアフィニティ、自動スケール、1時間タイムアウト）、Cloud Storage / Firestore。

### 設計上の工夫
1. **No Markup from Models**: LLMはPydanticで型定義されたJSON差分のみを出力し、Pythonが確定的にSVGを描画。LLM特有のHTMLタグ欠損やレイアウト崩れを完全に防止。
2. **適応型デバウンス制御**: 発話停止2秒または15秒継続発話ごとの送信バッファリングにより、Gemini APIの無駄な連打を防ぎつつ快適なレスポンスを両立。
```

#### アーキテクチャ図（画像）
- ワークスペース直下に高解像度画像を用意済みです：
  👉 `architecture_diagram.png`
  （※Google Cloud Run、Vertex AI、ADK、Cloud STT/TTS、フロントエンドの連携が美しくまとまったシステム構成図です）

#### プロジェクトイメージ（最大10枚）
以下の画像をアップロード可能です：
1. `architecture_diagram.png`（システム構成図）
2. `step3_workflow_v2.png`（フロー自動生成・更新画面）
3. `step6_banana_agent.png`（Nano Banana 画像生成画面）
4. `step7_contradiction.png`（AI 矛盾検知警告カード表示）
5. `step4_compare.png`（比較表ブロック）
6. `step5_calculation.png`（試算・数値分析ブロック）
7. `step8_checklist.png`（タスクチェックリスト画面）

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
3. 画面左上の言語セレクターで「ja-JP（日本語）」または「en-US（英語）」を選択できます（デフォルトは英語/日本語両対応）。
4. マイクボタン（またはスペースキー）を押して音声で話すか、右下のテキストボックスからチャット入力を行ってください。
※発話完了後、約2秒の無音で自動的にGeminiへ送信・ビジュアル生成が開始されます。

【推奨動作確認シナリオ（レストランQRオーダー＆アンケートシステム）】
以下の順で発話またはテキスト送信をお試しいただくと、AEGISの全主要機能を3分で網羅できます：

① フロー自動生成（初期ステップ）:
「レストランのモバイルオーダーの流れを整理しましょう。まずお客様が卓上のQRコードをスマホで読み取り、アプリ不要でWebメニューを開いて料理を選びます。」
→ 画面にフローチャート（v1）が自動描画されます。

② フロー更新・追加ステップ:
「続いて、お客様が料理をカートに入れて注文を確定し、厨房のキッチンディスプレイにデータが即座に届きます。」
→ 既存フローを保持したまま、新しいステップが追加された（v2）タブが生成されます。

③ ナノバナナ画像生成（イラスト化）:
「エイジス、QRコード読み取りステップのイラストを描いて」
→ QRコード読み取りノードにNano Bananaのイラストが生成・添付されます。ノードクリックでモーダル拡大表示が可能です。

④ 矛盾検知（AIプロアクティブ介入）:
「ちょっと待ってください。うちの店はスマホ注文は禁止で、レジで現金払いのみです。」
→ 過去の決定事項と矛盾することをAIが自動検知し、画面上に赤い矛盾警告カードを表示＋音声で注意喚起します。

⑤ ハイライトとステップ削除:
「スマホ決済のステップをハイライトして、配膳のステップを削除してください」
→ ノードの枠線が強調され、指定されたノードが安全に削除されて前後の線が自動で繋ぎ直されます。
```

---

## ✅ 3. 提出前最終チェックリスト

- [x] **Google Cloud アプリケーション実行プロダクト**: Google Cloud Run 上で本番稼働中
- [x] **Google Cloud AI 技術**: Vertex AI Gemini 2.5 Flash, Gemini 3.1 Flash Image, Google ADK, Cloud STT v2, Cloud Text-to-Speech
- [x] **認証機能**: ID (`judge`) / Password (`Aegis2026!`) によるセキュアなアクセス制限
- [x] **GitHubリポジトリ**: 最新コミットが `origin/main` へ push 完了
- [x] **システム構成図**: `architecture_diagram.png` 生成済み
