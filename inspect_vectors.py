import chromadb
import sys
import os

# プロジェクトルートをパスに追加（必要に応じて）
sys.path.append(os.getcwd())

def inspect_vectors():
    print("ChromaDBの中身を確認します...\n")
    
    try:
        # 保存されているDBに接続
        client = chromadb.PersistentClient(path="./data/chroma_db")
        collection = client.get_or_create_collection(name="legal_documents")

        # データを1件だけ取得（embedding=ベクトル も含む）
        # include引数で 'embeddings' を指定しないとベクトルデータは返ってきません
        result = collection.get(limit=1, include=["documents", "metadatas", "embeddings"])

        if result['ids']:
            print("=== 1. 人間が見ているデータ（元のテキスト） ===")
            print(f"文書ID: {result['ids'][0]}")
            print(f"内容: {result['documents'][0][:100]}... (以下略)")
            
            print("\n=== 2. AIが見ているデータ（ベクトル/数値化） ===")
            vector = result['embeddings'][0]
            print(f"データの次元数（数字の個数）: {len(vector)}")
            print(f"実際の数値データ（先頭の20個のみ）: {vector[:20]}")
            print("\nこのように、AIはこの「数字の羅列」として文章を記憶しています。")
            print("検索時は、ユーザーの質問も同じように数値化し、この数値に近いデータを探し出します。")
            
        else:
            print("データベースは空です。まだデータがロードされていません。")
            print("次のステップでテストを実行して、データを投入しましょう。")
            
    except Exception as e:
        print(f"エラーが発生しました: {e}")

if __name__ == "__main__":
    inspect_vectors()
