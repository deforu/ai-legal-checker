import asyncio
import os
import sys
from dotenv import load_dotenv

sys.path.append(os.getcwd())

from app.models.request import ComplianceCheckRequest, ContentData, RequestOptions
from app.rag.retrieval import check_compliance

async def main():
    print("=== [改善版] RAGコンプライアンスチェック テスト開始 ===")
    
    # テストシナリオ: ステマ規制違反の疑いがある投稿
    # 企業から依頼されているのに「PR」表記がない
    test_text = "最近、この化粧水を使い始めました！肌の調子がすごく良くて、みんなにも絶対おすすめ！今ならキャンペーン中だよ。（※実は企業案件だがPR表記なし）"
    
    print(f"入力テキスト: {test_text}\n")
    print("AIが分析中... (追加された「ステマ規制」のデータを検索しています)\n")
    
    request = ComplianceCheckRequest(
        content=ContentData(type="text", data=test_text),
        options=RequestOptions(target_laws=["premiums_and_representations_act"])
    )
    
    try:
        response = await check_compliance(request)
        result = response.result
        
        # 結果表示
        print("=== AIによる法的分析結果 (IRAC) ===")
        # LangGraphから返ってきた生の分析テキストを表示（ここが一番重要）
        # retrieval.pyの実装上、analysis_logにはステップごとの情報が入るが、
        # ここではviolationsのdetailsから分析内容を読み取る
        
        if result['violations']:
            for v in result['violations']:
                print(f"▼ 判定: {v.law}")
                print(f"▼ 根拠条文: {v.violation_section}")
                print(f"▼ 詳細分析:\n{v.details}")
                print("-" * 50)
        else:
            print("違反は検出されませんでした。")

        if result['recommendations']:
            print("\n=== AIによる修正案 ===")
            print(f"修正案: {result['recommendations'][0].revised_text}")
            
    except Exception as e:
        print(f"エラー: {e}")

if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
