import asyncio
from typing import Dict, Any
from app.models.request import ComplianceCheckRequest
from app.models.response import ComplianceCheckResponse, ViolationDetail, Recommendation
from app.rag.vector_store import search_documents, initialize_vector_store, get_collection_count
from app.workflow.langgraph import create_workflow
import json
import os
import re
from pathlib import Path

# サンプル法律文書の読み込みとベクトルストアへの追加（初回のみ）
def load_sample_documents():
    documents = []
    print("Loading legal documents with semantic chunking...")
    
    source_docs_dir = Path(__file__).parent.parent.parent / "source_docs"
    if not source_docs_dir.exists():
        print(f"Directory not found: {source_docs_dir}")
        return documents

    # 1. XML形式 (01_条文など): 条文単位で分割
    for xml_path in source_docs_dir.rglob("*.xml"):
        try:
            with open(xml_path, 'r', encoding='utf-8') as f:
                content = f.read()
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(content, 'xml')
            law_title = soup.find('LawTitle').text if soup.find('LawTitle') else xml_path.stem
            
            # 本則 (MainProvision) の抽出
            main_provision = soup.find('MainProvision')
            if main_provision:
                articles = main_provision.find_all('Article')
                for article in articles:
                    section_name = article.find('ArticleTitle').text if article.find('ArticleTitle') else "不明"
                    caption = article.find('ArticleCaption')
                    caption_text = caption.text if caption else ""
                    article_text = article.get_text(separator="\n", strip=True)
                    
                    # ★ ベクトル検索の精度向上: 条文の内容にプレフィックスを付与
                    # ChromaDBのデフォルトembeddingは日本語法律文の意味区別が困難なため、
                    # 法律名・条文番号・見出しをコンテンツ先頭に付与してembedding品質を向上させる
                    enriched_content = f"【{law_title}】{section_name} {caption_text}\n{article_text}"
                    
                    law_group = "yakkiho" if "医薬品" in law_title else "kehyoho" if "不当景品" in law_title else "other"
                    
                    metadata = {
                        "title": law_title,
                        "category": "01_statute",
                        "law_group": law_group,
                        "section": section_name,
                        "caption": caption_text,
                        "is_main_provision": True,
                        "source_type": "xml",
                        "path": str(xml_path.relative_to(source_docs_dir))
                    }
                    documents.append({"content": enriched_content, "metadata": metadata})

            # 附則 (SupplProvision) の抽出
            suppl_provisions = soup.find_all('SupplProvision')
            for suppl in suppl_provisions:
                articles = suppl.find_all('Article')
                for article in articles:
                    section_name = article.find('ArticleTitle').text if article.find('ArticleTitle') else "不明"
                    caption = article.find('ArticleCaption')
                    caption_text = caption.text if caption else ""
                    article_text = article.get_text(separator="\n", strip=True)
                    
                    # 附則にもプレフィックスを付与（ただし「附則」を明記）
                    enriched_content = f"【{law_title}・附則】{section_name} {caption_text}\n{article_text}"
                    
                    law_group = "yakkiho" if "医薬品" in law_title else "kehyoho" if "不当景品" in law_title else "other"
                    
                    metadata = {
                        "title": law_title,
                        "category": "01_statute",
                        "law_group": law_group,
                        "section": section_name,
                        "caption": caption_text,
                        "is_main_provision": False,
                        "source_type": "xml",
                        "path": str(xml_path.relative_to(source_docs_dir))
                    }
                    documents.append({"content": enriched_content, "metadata": metadata})
        except Exception as e:
            print(f"Error loading XML {xml_path}: {e}")

    # 2. Markdown形式 (02_OK事例, 03_NG事例, 04_運用基準など): 見出し単位で分割
    for md_path in source_docs_dir.rglob("*.md"):
        try:
            with open(md_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # ディレクトリ名からカテゴリを推測
            parent_dir = md_path.parent.name
            category = "unknown"
            if "02" in parent_dir: category = "02_ok_example"
            elif "03" in parent_dir: category = "03_ng_example"
            elif "04" in parent_dir: category = "04_standard"

            # 見出し（#）で分割
            chunks = re.split(r'\n(?=# )', content)
            for i, chunk in enumerate(chunks):
                if not chunk.strip(): continue
                # 最初の1行を見出し（セクション名）として抽出
                first_line = chunk.split('\n')[0].replace('#', '').strip()
                metadata = {
                    "title": md_path.stem,
                    "category": category,
                    "law_group": "other",
                    "section": first_line if first_line else f"Section {i+1}",
                    "source_type": "md",
                    "path": str(md_path.relative_to(source_docs_dir))
                }
                documents.append({"content": chunk.strip(), "metadata": metadata})
        except Exception as e:
            print(f"Error loading MD {md_path}: {e}")

    # 3. PDF形式: ページ単位または一定文字数で分割（改良案）
    import pypdf
    for pdf_path in source_docs_dir.rglob("*.pdf"):
        try:
            reader = pypdf.PdfReader(pdf_path)
            # ディレクトリ名からカテゴリを推測
            parent_dir = pdf_path.parent.name
            category = "04_standard" # デフォルト
            if "02" in parent_dir: category = "02_ok_example"
            elif "03" in parent_dir: category = "03_ng_example"

            for i, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if not page_text or len(page_text.strip()) < 50: continue
                
                metadata = {
                    "title": pdf_path.stem,
                    "category": category,
                    "law_group": "other",
                    "section": f"Page {i+1}",
                    "source_type": "pdf",
                    "path": str(pdf_path.relative_to(source_docs_dir))
                }
                documents.append({"content": page_text.strip(), "metadata": metadata})
        except Exception as e:
            print(f"Error loading PDF {pdf_path}: {e}")

    return documents


# 初期化時にサンプルドキュメントをロード
try:
    # 既存のカウントに関わらず、再構築が必要な場合はここを調整
    # 今回は initialize_vector_store 内でリセットを行うようにしたため、
    # 常に最新の source_docs を反映するように再初期化を実行する設計とする。
    print("Re-indexing source documents for semantic optimization...")
    sample_docs = load_sample_documents()
    if sample_docs:
        print(f"Total documents to index: {len(sample_docs)}")
        initialize_vector_store(sample_docs)
except Exception as e:
    print(f"Warning: Could not initialize vector store with sample documents: {e}")

async def check_compliance(request: ComplianceCheckRequest) -> ComplianceCheckResponse:
    """
    RAGとLangGraphを使用してコンプライアンスチェックを実行する関数
    """
    import time
    start_time = time.time()
    
    input_text = request.content.data
    
    # LangGraphワークフローを作成
    workflow = create_workflow()

    # 初期状態を設定
    initial_state = {
        "input_text": input_text,
        "retrieved_docs": [],
        "analysis_result": {},
        "final_output": {},
        "current_step": "start",
        "debug_info": {}
    }

    # ワークフローを実行
    result = await workflow.ainvoke(initial_state)

    violations = []
    recommendations = []
    # デフォルトの確信度
    confidence_score = 0.8

    # LangGraphの結果を解析してレスポンス形式に変換
    if "final_output" in result:
        output = result["final_output"]
        irac_analysis = output.get("analysis_summary", "")
        recommendation_text = output.get("recommendations", "")
        
        # 結論に基づいて違反オブジェクトを作成
        is_compliant = output.get("compliant", False)
        
        # 確信度があれば取得
        if "confidence_score" in output:
             confidence_score = output["confidence_score"]

        # 【修正】適合・不適合に関わらず、AIの分析結果を詳細として返す
        # 検索された根拠文書をEvidenceとして追加
        evidence_list = []
        if "retrieved_docs" in result:
             r_docs = result["retrieved_docs"]
             if r_docs and 'documents' in r_docs and r_docs['documents']:
                 for i, doc_text in enumerate(r_docs['documents'][0]):
                     meta = r_docs['metadatas'][0][i]
                     evidence_list.append({
                         "source": f"{meta.get('title')} {meta.get('section')}",
                         "content": doc_text[:200] + "..." # 抜粋
                     })

        violation = ViolationDetail(
            law="景品表示法 / 薬機法（分析結果参照）",
            violation_section="AI分析",
            details=irac_analysis, # ここにGeminiのIRAC分析が常に入る
            severity="high" if not is_compliant else "low",
            evidence=evidence_list
        )
        violations.append(violation)

        # 代替案も常に含める
        recommendation = Recommendation(
            original_text=input_text,
            revised_text="AIの提案を確認してください",
            reason=recommendation_text
        )
        recommendations.append(recommendation)

    else:
        # 結果が取得できなかった場合
        is_compliant = False
        confidence_score = 0.0
        
    end_time = time.time()
    processing_time_ms = int((end_time - start_time) * 1000)

    # レスポンスの作成
    response_result = {
        "compliant": is_compliant, # AIの判定をそのまま使用
        "confidence_score": confidence_score,
        "violations": violations,
        "recommendations": recommendations,
        "analysis_log": {
            "steps": [
                {
                    "step": "langgraph_workflow",
                    "input": input_text,
                    "output": f"Workflow completed in {processing_time_ms/1000:.2f}s",
                    "tool_used": "langgraph"
                }
            ],
            "retrieval_debug": result.get("debug_info", {}),
            "token_usage": result.get("final_output", {}).get("token_usage", {})
        }
    }

    response = ComplianceCheckResponse(
        status="success",
        result=response_result,
        processing_time=processing_time_ms, 
        # cost_estimate=0.0
    )

    return response


def extract_revised_text(recommendations_text, original_text):
    """
    推奨事項から代替表現を抽出する関数（簡易実装）
    """
    # 簡単な実装として、元のテキストに含まれる問題語を一般的な表現に置き換える
    revised = original_text
    # LangGraphが生成した推奨事項から新しい表現を抽出しようと試みる
    if "代替表現" in recommendations_text or "提案表現" in recommendations_text:
        # 簡単な置き換え
        revised = revised.replace("効果", "働き").replace("効能", "特徴").replace("治療", "ケア")

    return revised


def analyze_langgraph_output(langgraph_output, input_text):
    """
    LangGraphの出力から違反の有無を解析する関数
    """
    analysis_summary = langgraph_output.get("analysis_summary", "")

    # IRAC構造のConclusion部分から違反の有無を判定
    conclusion_parts = [
        "結論", "conclusion", "Conclusion", "判定", "judgment", "determination"
    ]

    # 重要なキーワードで検索
    violation_indicators = [
        "違反", "non-compliant", "不適切", "問題", "違法", "appropriate",
        "inappropriate", "contradicts", "not compliant", "not advisable"
    ]

    # 無害な表現の例
    compliant_indicators = [
        "適切", "compliant", "appropriate", "safe", "acceptable", "no violation",
        "適法", "問題なし", "no issues"
    ]

    # 法律的に問題のある表現の検出
    problematic_expressions = [
        "医師が推奨", "医師が推奨する", "医師推奨", "癌が治る", "癌を治す", "癌の治療",
        "病気が治る", "病気を治す", "治療効果", "薬効", "効能", "治癒", "cure", "treat",
        "prevent disease", "medical claim", "health benefit", "disease"
    ]

    analysis_lower = analysis_summary.lower()

    # 分析結果に違反を示唆する表現が含まれているか
    has_violation_indicators = any(indicator.lower() in analysis_lower for indicator in violation_indicators)
    has_compliant_indicators = any(indicator.lower() in analysis_lower for indicator in compliant_indicators)

    # 入力テキストに問題表現が含まれているか
    input_has_problematic = any(expr in input_text for expr in problematic_expressions)

    # ヒューリスティックな判断：IRACの結論と入力テキストの問題表現を組み合わせて判断
    if input_has_problematic:
        return False, f"テキストに問題表現 '{[expr for expr in problematic_expressions if expr in input_text][0]}' が含まれています"

    if has_violation_indicators and not has_compliant_indicators:
        return False, "分析結果には違法性を示唆する表現が含まれています"

    if has_compliant_indicators and not has_violation_indicators:
        return True, "分析結果では法律遵守とされています"

    # IRAC構造から判断（場合分け）
    if "issue:" in analysis_lower and ("not compliant" in analysis_lower or "violation" in analysis_lower):
        return False, "IRACのIssueで違反が指摘されています"

    if "conclusion:" in analysis_lower and ("compliant" in analysis_lower or "appropriate" in analysis_lower):
        return True, "IRACのConclusionで遵守とされています"

    # デフォルトでは、問題があると判断（安全側）
    return False, "分析結果が明確でないため、違反可能性が高いと判断しました"