# PostmanによるAPIテスト手順

このドキュメントでは、AI Legal Checker APIをPostmanでテストする手順を説明します。

## 1. サーバーの起動

まず、APIサーバーを起動する必要があります。ターミナルで以下のコマンドを実行してください。

### Windows (バッチスクリプトを使用)
依存関係のインストールとサーバー起動を一括で行います。
```bash
.\run_server.bat
```

### または直接コマンド実行 (依存関係インストール済みの場合)
```bash
uvicorn app.main:app --reload --port=8000
```

サーバーが起動すると、以下のようなログが表示されます：
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

## 2. Postmanの設定

Postmanを開き、新しいリクエストを作成します。

### リクエスト設定
- **Method**: `POST`
- **URL**: `http://127.0.0.1:8000/api/v1/compliance/check`

### Headers設定
- **Key**: `Content-Type`
- **Value**: `application/json`

### Body設定
1. **Body**タブを選択
2. **raw**を選択
3. 右側のドロップダウンから**JSON**を選択

## 3. テストケース

### ケース1: 基本的なダイエットサプリ (一般的な違反)
以下のJSONを入力してください：

```json
{
  "content": {
    "type": "text",
    "data": "このサプリを飲むだけで、なんと1ヶ月で10kg痩せました！食事制限も運動も一切不要。誰でも簡単にモデル体型になれます。ガンも治るという噂です。"
  },
  "options": {
    "product_name": "ミラクルサプリ"
  }
}
```

### ケース2: RAG精度改善の検証用 (薬機法・景表法)
今回の改修で検出可能になった、より具体的な違反事例です。

```json
{
  "content": {
    "type": "text",
    "data": "このサプリを飲むだけで、1ヶ月で10kg痩せました！しかも、癌も治るという噂です。"
  },
  "options": {
    "product_name": "ミラクルサプリ"
  }
}
```

**期待される結果**:
- **薬機法第66条** (誇大広告)： 「癌が治る」という疾病治療効果の標榜に対する違反指摘。
- **景品表示法** (優良誤認)： 「1ヶ月で10kg」という強調表示に対する根拠不足の指摘。

## 4. テスト実行

「**Send**」ボタンをクリックしてリクエストを送信します。

### 期待されるレスポンス (例)
成功した場合、ステータスコード `200 OK` と共に、以下のようなJSONレスポンスが返ってきます。

```json
{
    "status": "success",
    "result": {
        "compliant": false,
        "confidence_score": 0.8,
        "violations": [
            {
                "law": "薬機法 / 景品表示法",
                "violation_section": "AI分析",
                "details": "ここに詳細な分析結果が表示されます...",
                "severity": "high"
            }
        ],
        "recommendations": [
            {
                "original_text": "...",
                "revised_text": "...",
                "reason": "..."
            }
        ],
        "analysis_log": { ... }
    },
    "processing_time": 49960
}
```

## 5. トラブルシューティング

- **Error: Connection refused**: サーバーが起動しているか確認してください。URLが正しいか (`http://127.0.0.1:8000`) 確認してください。
- **Error: 500 Internal Server Error**: サーバーログを確認してエラー詳細を見てください。APIキー (`GOOGLE_API_KEY`) が `.env` ファイルに正しく設定されているか確認してください。
