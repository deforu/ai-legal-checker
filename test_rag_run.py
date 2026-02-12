import asyncio
import os
import sys
from dotenv import load_dotenv

# プロジェクトルートをパスに追加
sys.path.append(os.getcwd())

from app.models.request import ComplianceCheckRequest, ContentData, RequestOptions
from app.rag.retrieval import check_compliance

async def main():
    print("=== RAGコンプライアンスチェック テスト開始 ===")
    
    # テストする入力テキスト
    # 薬機法に抵触しそうな表現（医師が推奨、病気が治るなど）
    test_text = "このサプリメントは医師が推奨しており、飲むだけで癌が治る効果があります。"
    
    print(f"入力テキスト: {test_text}\n")
    print("AIが分析中... (LangGraphワークフローを実行しています)\n")
    
    # リクエストオブジェクトの作成
    request = ComplianceCheckRequest(
        content=ContentData(type="text", data=test_text),
        options=RequestOptions(target_laws=["pharma_act"])
    )
    
    try:
        # コンプライアンスチェックの実行
        response = await check_compliance(request)
        
        print("=== 分析結果 ===")
        result = response.result
        print(f"ステータス: {'違反あり' if not result['compliant'] else '問題なし'}")
        
        if result['violations']:
            print("\n[検出された違反]")
            for v in result['violations']:
                print(f"- 法律: {v.law}")
                print(f"- 条文: {v.violation_section}")
                print(f"- 詳細: {v.details}")
        
        if result['recommendations']:
            print("\n[AIによる代替表現の提案]")
            print(result['recommendations'][0].revised_text)
            # 全体の推奨テキストも表示（LangGraphの生の回答に近いもの）
            # retrieval.py の実装により、recommendations[0].reason に詳細が入っている場合がある
            print("\n[詳細なアドバイス]")
            print(result['recommendations'][0].reason)

        print(f"\n処理時間: {response.processing_time}ms")
        
    except Exception as e:
        print(f"エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
