# 🛡️ PROJECT A.E.G.I.S.
### Autonomous AI Hearing & Visual Meeting Co-Pilot
**第5回 Agentic AI Hackathon with Google Cloud 応募作品**

[![Google Cloud Run](https://img.shields.io/badge/Google%20Cloud-Cloud%20Run-blue?logo=google-cloud)](https://cloud.google.com/run)
[![Gemini 3.8 Live](https://img.shields.io/badge/Gemini%20API-3.8%20Multimodal-4285F4?logo=google)](https://ai.google.dev/)
[![Nano Banana](https://img.shields.io/badge/Google%20Cloud%20AI-Nano%20Banana-F59E0B)](https://ai.google.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-1.0.0-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Web Speech API](https://img.shields.io/badge/Speech-70%2B%20Languages-10B981)](#)

---

## 🌟 概要 (Executive Summary)

**「作れる」から「使える」へ。自律的に会議の整合性と視覚化を護る、次世代AIエージェント。**

リモート会議では、**「過去の発言との食い違い（矛盾・言った言わない問題）」**、**「口頭の数字の計算ミス」**、**「言葉だけで伝わらないアーキテクチャの認識ズレ」** が頻発し、多大な手戻りを生み出しています。

**PROJECT A.E.G.I.S.** は、人間同士の会話をリアルタイムに傾聴（Hearing）し、以下の自律アクションを完全自動で実行する **マルチモーダル・コパイロット** です：

1. **Truth Sentinel（矛盾検知エンジン）**: 会議の時系列台帳（Temporal Claim Graph）を維持し、過去の発言（Old Speak）と新しい発言（New Speak）の食い違い（納期、予算、数値、技術選定など）を検知。Google Meetチャットへ即座に確認質問を自動投稿。
2. **Nano Banana Visual Synthesizer**: 会話中の「このアーキテクチャ図解して」「イメージ描いて」に即応し、Google Cloud **Nano Banana (`gemini-3.1-flash-image`)** を用いて超高精細なシステム図・概念図をリアルタイム生成。
3. **Live Process Flow & Math Calculation**: 会話内のステップや計算式を瞬時に解析し、Pure Black OLED HUDにリアルタイム図解・数式カードを展開。
4. **Autonomous Screen Share & Meet Bridge**: 「Hey agent, show us your screen」の音声トリガーで自律的に画面共有を起動。ユーザーの通常Chromeブラウザから1行でGoogle Meetへ直接接続可能。

---

## 🏛️ システムアーキテクチャ (System Architecture)

```
       [ Human Participants in Google Meet / Normal Chrome ]
                                 │
     ┌───────────────────────────┴───────────────────────────┐
     │                                                       │
  [Chrome Web Speech API / Mic]                  [Meet Live Bridge (F12)]
  (16kHz Real-time Audio Ingress)                (Captions & Auto-Chat Bot)
     │                                                       │
     └───────────────────────────┬───────────────────────────┘
                                 ▼
         ╔═══════════════════════════════════════════════════╗
         ║           PROJECT A.E.G.I.S. SERVER               ║
         ║              (Google Cloud Run)                   ║
         ║                                                   ║
         ║  ┌─────────────────────────────────────────────┐  ║
         ║  │  Truth Sentinel: Temporal Claim Graph       │  ║
         ║  │  - Cross-speaker contradiction detection    │  ║
         ║  │  - Timeline / Budget / Metric arbiters      │  ║
         ║  └─────────────────────────────────────────────┘  ║
         ║                        │                          ║
         ║        ┌───────────────┴───────────────┐          ║
         ║        ▼                               ▼          ║
         ║  [ Google Cloud AI ]          [ Google Cloud AI ]  ║
         ║    Gemini 3.8 Live               Nano Banana      ║
         ║  (Multimodal Reasoning)       (Image Synthesis)   ║
         ║        │                               │          ║
         ╚════════╪═══════════════════════════════╪══════════╝
                  │                               │
                  ▼                               ▼
       [ Reactive Character Avatar ]     [ High-Def Visual Canvas ]
       (Listening / Thinking / Alert)    (Realtime SVG & 4K Schematics)
                  │                               │
                  └───────────────┬───────────────┘
                                  ▼
                   [ Pure Black Cinematic HUD ]
                   (Zero-Latency Judge View)
```

---

## 🏆 ハッカソン審査基準への適合 (Hackathon Alignment)

| 審査項目 | 本プロジェクトの実装内容 |
| :--- | :--- |
| **課題の新規性と解決策の有効性** | 会議中の「言った言わない」「認識のズレ」という誰もが直面する痛点を、受動的な議事録作成ではなく**「リアルタイムの自律的介入（矛盾指摘＋図解）」**で根本解決。 |
| **自律性・エージェントらしさ** | 指示待ちのチャットボットではなく、会話の文脈を自律判断して「Meetチャットへの自動投稿」「画面共有の自動起動」「キャラクタのアニメーション状態遷移」を実行。 |
| **Google Cloud 技術の利用** | **① Cloud Run** (コンテナ実行基盤)<br>**② Nano Banana (`gemini-3.1-flash-image`)** (リアルタイム図解・画像生成)<br>**③ Gemini 3.8 / Gemini API** (マルチモーダル推論)<br>**④ Cloud Build** (CI/CD自動化) |
| **実装品質と拡張性** | 審査員がワンクリックで体験できるハイブリッド設計（ブラウザ内Web Speechマイク＋Meet Bridge）。多言語（日英）対応、WebSocket常時双方向通信、完全型付け（FastAPI + Pydantic）。 |

---

## 🚀 クイックスタート (Local Execution)

### 1. 依存ライブラリのインストール
```bash
pip install -r requirements.txt
```

### 2. ローカルサーバーの起動
```bash
python -m uvicorn backend.agent_server:app --host 127.0.0.1 --port 8000
```
ブラウザで `http://localhost:8000` を開きます。

### 3. エンドツーエンド検証（8シナリオ全自動テスト）
```bash
python tests/simulate_meeting.py
```
> **実行結果**:
> - Turn 1: リアルタイムプロセルフロー自動描画 ✅
> - Turn 2: リアルタイム計算式カード展開 ✅
> - Turn 3 & 4: 矛盾検知（Q3納期 vs Q2納期）& チャットメッセージ生成 ✅
> - Turn 5: 音声トリガー画面共有起動（"Hey agent show us your screen"） ✅
> - Turn 6: 音声＋視覚のデュアル回答 ✅
> - Turn 7: 日本語多言語矛盾検知（第3四半期 vs 第2四半期） ✅
> - Turn 8: Google Cloud Nano Banana によるシステム図解生成 ✅
> **`🎉 ALL 8 TEST SCENARIOS PASSED WITH 100% ACCURACY!`**

---

## ☁️ Google Cloud Run へのデプロイ方法

### 方法 A: Google Cloud CLI からのワンコマンドデプロイ
```bash
# Linux / macOS / Cloud Shell
chmod +x deploy_cloud_run.sh
./deploy_cloud_run.sh

# Windows (PowerShell)
.\deploy_cloud_run.ps1
```

### 方法 B: Google Cloud Console (GUI / GitHub連携)
1. [Google Cloud Console](https://console.cloud.google.com/run) にアクセス。
2. **「サービスの作成」** をクリック。
3. **「ソースリポジトリから継続的に新しいリビジョンをデプロイする」** を選択し、本GitHubリポジトリを指定。
4. ポートを `8080` に設定し、**「未認証の呼び出しを許可」** をチェックして「作成」をクリック。
5. 数分で発行されたパブリックURL（`https://aegis-copilot-xxxx.run.app`）をハッカソン提出フォームに登録します。

---

## 🍌 Nano Banana 機能の使い方

1. **画面上部のボタン**: HUDトップバーの `🍌 NANO BANANA VISUAL` をクリックし、プリセットまたは任意のシステム構成を入力。
2. **会話からの自律トリガー**: 会議中やマイク入力で「システム構成を図解して」「アーキテクチャ図を描いて」「Nano Banana」と発言すると、エージェントが自律的に高精細なダイアグラムを生成して画面共有します。

---

## 🔒 セキュリティとプライバシー

- **No Hidden Browser**: 外部クラウドに資格情報を預けることなく、ユーザー自身の通常Chromeで安全に動作。
- **Ephemeral Processing**: 会議の時系列台帳はセッション中のみメモリ上に保持され、終了時に安全にパージ。
- **Grounded Clarification**: 断定による誤認を防ぐため、矛盾検出時は必ず「選択肢付きの確認質問（Which one do you mean: A vs B?）」として中立的に提示。

---

## 📄 ライセンス
Apache License 2.0
