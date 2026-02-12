# AI Legal Checker (薬機法・景表法チェックプロトタイプ)

広告テキストなどが日本の法律（**薬機法**、**景品表示法**など）に違反していないかをチェックし、違反箇所と代替表現（言い換え）を提案するAIシステムのプロトタイプです。

## 🚀 主な機能

1.  **高度な法的検索 (RAG)**
    - **マルチクエリ検索**: ユーザーの入力から「条文検索用」と「ガイドライン検索用」の2つのクエリを生成し、多角的に情報を収集します。
    - **永続化ベクトルストア**: ChromaDBを使用し、再起動後もデータを保持（重複ロード防止機能付き）。
    - **データソース (`source_docs`)**: 薬機法、景品表示法などの全文XMLに加え、厚生労働省や消費者庁のWebガイドラインもインデックス化。

2.  **堅牢なAI推論 (Multi-LLM & Fallback)**
    - **メイン**: Google Gemini (Flash/Pro) による高速推論。
    - **フォールバック**: Geminiがレート制限 (429 Error) に達した場合、自動的に **OpenAI (GPT-4o)** に切り替わり、処理を継続します。
    - **IRACフレームワーク**: 法的三段論法（Issue, Rule, Application, Conclusion）を用いた論理的な法的分析。

3.  **エージェンティック・ワークフロー**
    - **LangGraph** を使用し、検索 → 分析 → 推論 → 提案 のフローを制御。

## 🛠️ 技術スタック

- **Backend**: Python 3.12+, FastAPI
- **LLM Orchestration**: LangChain, LangGraph
- **LLMs**: Google Gemini (via `langchain-google-genai`), OpenAI GPT-4o (via `langchain-openai`)
- **Vector Store**: ChromaDB
- **Search**: Tavily (Optional fallback)

## 📂 プロジェクト構造

```
.
├── app/
│   ├── api/            # APIエンドポイント定義
│   ├── models/         # Pydanticモデル
│   ├── rag/            # RAGロジック (retrieval.py, vector_store.py)
│   └── workflow/       # LangGraphワークフロー定義
├── source_docs/        # 法律データソース (XML定義, URLリスト)
├── data/               # 生成されたベクトルDB (chroma_db)
├── tests/              # テストコード
├── requirements.txt    # 依存ライブラリ
├── run_server.bat      # サーバー起動スクリプト
└── .env                # 環境変数 (APIキー等)
```

## 🏁 セットアップ手順

### 1. 前提条件
- Python 3.12以上がインストールされていること
- Google AI Studio API Key (Gemini用)
- OpenAI API Key (フォールバック用)

### 2. インストール

```powershell
# リポジトリのクローン
git clone https://github.com/deforu/ai-legal-checker.git
cd ai-legal-checker

# 仮想環境の作成
python -m venv .venv

# 仮想環境の有効化 (Windows)
.venv\Scripts\activate

# 依存ライブラリのインストール
pip install -r requirements.txt
```

### 3. 環境変数の設定
ルートディレクトリに `.env` ファイルを作成し、以下の情報を記述してください。

```bash
GOOGLE_API_KEY=your_gemini_api_key
OPENAI_API_KEY=your_openai_api_key
# TAVILY_API_KEY=your_tavily_key  # (オプション)
```

### 4. 実行

付属のバッチファイルで簡単にサーバーを起動できます。初回起動時に `source_docs` 内のデータを自動的にベクトルDBに取り込みます。

```powershell
.\run_server.bat
```

起動後、APIサーバーは `http://127.0.0.1:8000` で待機します。

## 📖 使い方 (API)

Postmanやcurlを使用して、以下のエンドポイントにリクエストを送信してください。

**Endpoint**: `POST /api/v1/compliance/check`

**Request Body**:
```json
{
  "data": "このサプリを飲むだけで、1ヶ月で10kg痩せました！しかも、癌も治るという噂です。"
}
```

**Response (Example)**:
```json
{
    "status": "success",
    "result": {
        "compliant": false,
        "violations": [
            {
                "law": "薬機法",
                "violation_section": "第66条 (誇大広告)",
                "details": "..."
            }
        ],
        "recommendations": [
            {
                "revised_text": "...",
                "reason": "..."
            }
        ]
    }
}
```

## ⚠️ 注意事項/免責

本システムは技術検証用のプロトタイプであり、**法的助言を提供するものではありません**。
