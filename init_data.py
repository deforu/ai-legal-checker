import sys
import os
sys.path.append(os.getcwd())

# これをインポートすることで、app/rag/retrieval.py のトップレベルにある初期化コードが走り、データがロードされる
try:
    from app.rag.retrieval import sample_docs
    print(f"データロード完了: {len(sample_docs)} 件のsource_docsをベクトルストアに保存しました。")
except Exception as e:
    print(f"エラーが発生しました: {e}")