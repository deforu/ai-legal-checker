# AI Legal Checker (薬機法・景表法チェックプロトタイプ)

広告テキストなどが日本の法律（**薬機法**、**景品表示法**など）に違反していないかをチェックし、違反箇所と代替表現（言い換え）を提案する高性能なAIシステムのプロトタイプです。

## 🚀 進化した主な機能

1.  **次世代RAG検索 (Legal Document Search)**
    - **法域別スロット検索**: 「薬機法本法」「景表法本法」「運用ガイドライン/事例集」の3つの独立スロットで検索を実行。特定の法律に偏ることなく、多角的なエビデンスを収集します。
    - **分析戦略の自律決定**: AIが入力を解析し、検索キーワードや各法域への重み付け（スロット配分）を動的に最適化します。
    - **多言語Embedding**: `paraphrase-multilingual-MiniLM-L12-v2` を採用し、日本語の法的ニュアンスを正確に捉えた高度なセマンティック検索を実現。

2.  **高速・効率的なベクトルDB運用**
    - **起動高速化**: 既にベクトルストアにデータが存在する場合、再インデックスをスキップして即時にサービスを開始します。
    - **手動リセット**: 環境変数 `FORCE_REINDEX=true` を指定することで、いつでも最新の `source_docs` からDBを再構築可能です。

3.  **精緻な法的分析 (IRACフレームワーク)**
    - **IRAC方式**: 論点 (Issue) → 根拠 (Rule) → あてはめ (Application) → 結論 (Conclusion) の厳格な法的思考プロセスを追体験可能な形式で提供。
    - **ハイブリッド判定**: 構造化された法的思考と、AIによるマーケティング視点の改善提案を融合。

4.  **運用コストの可視化 (Token Tracking)**
    - **トークン計測**: 内部の各ステップ（検索・分析・提案）で消費されたトークン量をレスポンスに含め、実運用時のコスト予測を支援します。

## 🛠️ 技術スタック

- **Backend**: Python 3.12+, FastAPI
- **LLM Orchestration**: LangChain, LangGraph
- **Embedding**: Sentence Transformers (`paraphrase-multilingual-MiniLM-L12-v2`)
- **LLMs**: Google Gemini 1.5 Flash (Main), OpenAI GPT-4o (Fallback)
- **Vector Store**: ChromaDB (Persistent)
- **Data Source**: 
    - 薬機法、景品表示法 XML (e-Gov)
    - 各種広告ガイドライン、違反事例集 (PDF/Markdown)

## 📂 プロジェクト構造

```
.
├── app/
│   ├── api/            # APIエンドポイント定義
│   ├── models/         # Pydanticモデル (Request/Response)
│   ├── rag/            # 検索・Embedding・DBロジック
│   └── workflow/       # LangGraphによる推論フロー制御
├── source_docs/        # 法律・ガイドライン等の生データ
├── db/                 # ベクトルDB (chroma_db) 永続化ディレクトリ
├── 00_マスターノート/   # プロジェクトの設計・タスク・仕様書
├── requirements.txt    # 依存ライブラリ
├── .env                # 環境変数
└── run_server.bat      # サーバー起動スクリプト
```

## 🏁 セットアップと実行

### 1. インストール
```powershell
python -m venv .venv
. .venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### 2. 環境変数の設定 (`.env`)
```bash
GOOGLE_API_KEY=your_gemini_api_key
OPENAI_API_KEY=your_openai_api_key
# オプション: 初回起動時にDBを強制再構築する場合
# FORCE_REINDEX=true
```

### 3. 実行
```powershell
.\run_server.bat
```
APIサーバーは `http://127.0.0.1:8000` で待機します。

## 📖 使い方 (API)

**Endpoint**: `POST /api/v1/compliance/check`

### Request Body (JSON)
```json
{
  "content": {
    "type": "text",
    "data": "美容外科医が選ぶ『信頼できるスキンケアブランド』第1位獲得！国内最高峰の品質を保証します。"
  }
}
```

### Response (Example)
```json
{
  "status": "success",
  "result": {
    "compliant": false,
    "violations": [
      {
        "law": "薬機法 / 景品表示法",
        "violation_section": "AI分析",
        "details": "### 1. Issue...\n### 2. Rule...\n### 3. Application...\n### 4. Conclusion...",
        "severity": "high",
        "evidence": [...]
      }
    ],
    "recommendations": [...],
    "analysis_log": {
      "token_usage": {
        "input": 8150,
        "output": 1819,
        "total": 9969
      }
    }
  },
  "processing_time": 45000
}
```

## ⚠️ 免責事項
本システムはプロトタイプであり、提供される情報は法的正確性を保証するものではありません。最終的な法規判断には弁護士等の専門家の確認が必要です。
