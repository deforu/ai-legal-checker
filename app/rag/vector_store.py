import chromadb
from typing import List, Dict
import os

# ChromaDBクライアントの初期化
# 永続化ディレクトリを指定
client = chromadb.PersistentClient(path="./data/chroma_db")
collection = client.get_or_create_collection(name="legal_documents")

def initialize_vector_store(documents: List[Dict]):
    """
    source_docsをベクトルストアにロードする関数
    """
    # ドキュメントをコレクションに追加（バッチ処理）
    batch_size = 100
    total_docs = len(documents)
    
    print(f"Initializing vector store with {total_docs} documents...")
    
    for i in range(0, total_docs, batch_size):
        batch = documents[i:i + batch_size]
        # IDは単純な連番ではなく、ユニークなものにするのがベターだが、
        # ここでは再構築前提で連番にする（既存データがある場合は重複エラーになる可能性があるため注意）
        # ただし、retrieval.py側でデータがある場合はこの関数を呼ばない制御をしている。
        ids = [f"doc_{j}" for j in range(i, i + len(batch))]
        texts = [doc["content"] for doc in batch]
        metadatas = [doc.get("metadata", {}) for doc in batch]
        
        try:
            collection.add(
                ids=ids,
                documents=texts,
                metadatas=metadatas
            )
            print(f"Loaded batch {i // batch_size + 1}/{total_docs // batch_size + 1}")
        except Exception as e:
            print(f"Error adding batch {i}-{i + len(batch)}: {e}")

def search_documents(query: str, top_k: int = 5):
    """
    クエリに類似するドキュメントを検索する関数
    """
    print(f"Searching for: {query} (top_k={top_k})")
    try:
        results = collection.query(
            query_texts=[query],
            n_results=top_k
        )
        
        # 検索結果のログ出力
        if results and 'documents' in results and results['documents']:
            print(f"Found {len(results['documents'][0])} documents.")
            for i, doc in enumerate(results['documents'][0]):
                meta = results['metadatas'][0][i]
                print(f"Result {i+1}: {meta.get('title', 'No Title')} - {meta.get('section', 'No Section')}")
        else:
            print("No documents found.")
            
        return results
    except Exception as e:
        print(f"Error searching documents: {e}")
        return {"documents": [[]], "metadatas": [[]]}

def get_collection_count():
    """
    コレクション内のドキュメント数を取得する関数
    """
    return collection.count()
