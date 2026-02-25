import chromadb
from chromadb.utils import embedding_functions
from typing import List, Dict
import os
import shutil

# ChromaDBクライアントの初期化
# スキーマ不整合（バージョンアップ時など）が発生した場合、自動でDBを削除・再作成する
CHROMA_DB_PATH = "./data/chroma_db"

# ★ 根本修正: 日本語対応の多言語embeddingモデルを使用
# ChromaDBデフォルトの all-MiniLM-L6-v2 は英語専用のため日本語法律文を理解できない
# paraphrase-multilingual-MiniLM-L12-v2 は50言語以上に対応し、日本語のセマンティック検索が可能
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name=EMBEDDING_MODEL
)

def _init_chroma():
    """ChromaDBクライアントとコレクションを安全に初期化する"""
    try:
        _client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        _collection = _client.get_or_create_collection(
            name="legal_documents",
            embedding_function=embedding_func
        )
        return _client, _collection
    except Exception as e:
        print(f"⚠ ChromaDB初期化エラー（スキーマ不整合の可能性）: {e}")
        print(f"→ 旧DBを削除して再作成します: {CHROMA_DB_PATH}")
        if os.path.exists(CHROMA_DB_PATH):
            shutil.rmtree(CHROMA_DB_PATH, ignore_errors=True)
        _client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        _collection = _client.create_collection(
            name="legal_documents",
            embedding_function=embedding_func
        )
        print("✓ ChromaDB再作成完了")
        return _client, _collection

client, collection = _init_chroma()

def reset_vector_store():
    """
    コレクションを削除して新しく作成し直す（再インデックス用）
    """
    global collection
    print("Resetting vector store...")
    try:
        client.delete_collection(name="legal_documents")
        collection = client.create_collection(
            name="legal_documents",
            embedding_function=embedding_func
        )
        print("Vector store reset successful.")
    except Exception as e:
        print(f"Error resetting vector store: {e}")
        collection = client.get_or_create_collection(
            name="legal_documents",
            embedding_function=embedding_func
        )

def initialize_vector_store(documents: List[Dict]):
    """
    source_docsをベクトルストアにロードする関数
    """
    # 既存のデータをクリアして再構築
    reset_vector_store()
    
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

def search_documents(query: str, top_k: int = 5, where: Dict = None):
    """
    クエリに類似するドキュメントを検索する関数。metadataによるフィルタリングをサポート。
    """
    print(f"Searching for: {query} (top_k={top_k}, where={where})")
    try:
        results = collection.query(
            query_texts=[query],
            n_results=top_k,
            where=where
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
