import chromadb
import sys
import os

def analyze_rag_quality():
    print("--- RAG Data Quality Analysis ---\n")
    try:
        client = chromadb.PersistentClient(path="./data/chroma_db")
        collection = client.get_or_create_collection(name="legal_documents")
        
        # 多角的にサンプリング (XML, PDF, URL)
        sample = collection.get(limit=10, include=["documents", "metadatas"])
        
        if not sample['ids']:
            print("No data found in ChromaDB.")
            return

        for i in range(len(sample['ids'])):
            doc = sample['documents'][i]
            meta = sample['metadatas'][i]
            source_type = meta.get('source_type', 'unknown')
            title = meta.get('title', 'no-title')
            
            print(f"[{i+1}] Source: {source_type} | Title: {title}")
            print(f"ID: {sample['ids'][i]}")
            print(f"Length: {len(doc)} characters")
            print(f"Content Preview: {doc[:300]}...")
            print("-" * 30)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    analyze_rag_quality()
