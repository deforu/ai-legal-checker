import asyncio
from typing import Dict, Any
from app.models.request import ComplianceCheckRequest
from app.models.response import ComplianceCheckResponse, ViolationDetail, Recommendation
from app.rag.vector_store import search_documents, initialize_vector_store, get_collection_count
from app.workflow.langgraph import create_workflow
import json
import os
from pathlib import Path

# サンプル法律文書の読み込みとベクトルストアへの追加（初回のみ）
# サンプル法律文書の読み込みとベクトルストアへの追加（初回のみ）
def load_sample_documents():
    documents = []
    print("Loading legal documents...")
    
    # 1. JSONファイルの読み込み（既存）
    legal_docs_dir = Path(__file__).parent.parent.parent / "data" / "legal_documents"
    if legal_docs_dir.exists():
        for file_path in legal_docs_dir.glob("*.json"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        for item in data:
                            metadata = {
                                "title": item["title"],
                                "law_category": item["law_category"],
                                "section": item["section"],
                                "tags": ", ".join(item["tags"]) if isinstance(item["tags"], list) else str(item["tags"]),
                                "source_type": "json"
                            }
                            if "metadata" in item:
                                metadata.update(item["metadata"])
                            documents.append({"content": item["content"], "metadata": metadata})
                    elif isinstance(data, dict):
                        metadata = {
                            "title": data["title"],
                            "law_category": data["law_category"],
                            "section": data["section"],
                            "tags": ", ".join(data["tags"]) if isinstance(data["tags"], list) else str(data["tags"]),
                            "source_type": "json"
                        }
                        if "metadata" in data:
                            metadata.update(data["metadata"])
                        documents.append({"content": data["content"], "metadata": metadata})
            except Exception as e:
                print(f"Error loading JSON {file_path}: {e}")

    # 2. XMLファイルの読み込み（新規: 法律文書フォルダ）
    # プロジェクトルートの「source_docs」フォルダを参照
    xml_docs_dir = Path(__file__).parent.parent.parent / "source_docs"
    if xml_docs_dir.exists():
        from bs4 import BeautifulSoup
        print(f"Scanning XML documents in: {xml_docs_dir}")
        for file_path in xml_docs_dir.glob("*.xml"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                soup = BeautifulSoup(content, 'xml')
                law_title = soup.find('LawTitle').text if soup.find('LawTitle') else file_path.stem
                
                # <Article>タグ単位で抽出
                articles = soup.find_all('Article')
                print(f"Found {len(articles)} articles in {file_path.name}")
                
                for article in articles:
                    article_caption = article.find('ArticleCaption')
                    article_title = article.find('ArticleTitle')
                    
                    # 条文番号の抽出 (例: "第六十六条")
                    section_name = article_title.text if article_title else "不明"
                    caption_text = article_caption.text if article_caption else ""
                    
                    # 本文の抽出（Articleタグ内のテキストを結合、ただしXMLタグは除去）
                    # get_text()でタグを除去してテキストのみ取得
                    article_text = article.get_text(separator="\n", strip=True)
                    
                    # メタデータの作成
                    metadata = {
                        "title": law_title,
                        "law_category": "General Law", # 法律名から推測するか、一律設定
                        "section": section_name,
                        "caption": caption_text,
                        "tags": f"{law_title}, {section_name}, {caption_text}",
                        "source_type": "xml",
                        "is_main_provision": True # XMLからの条文は全て重要とみなす
                    }
                    
                    documents.append({
                        "content": article_text,
                        "metadata": metadata
                    })
            except Exception as e:
                print(f"Error loading XML {file_path}: {e}")

    # 3. URLガイドラインの読み込み（新規）
    # 「source_docs/web資料-条文を具体的に解釈するために行政資料」からURLを読み込む
    guideline_file = xml_docs_dir / "web資料-条文を具体的に解釈するために行政資料"
    # ファイル名に拡張子がない場合も考慮
    if not guideline_file.exists():
         guideline_file = xml_docs_dir / "web資料-条文を具体的に解釈するために行政資料.txt"

    if guideline_file.exists():
        import requests
        from bs4 import BeautifulSoup
        print(f"Loading guidelines from: {guideline_file}")
        
        try:
            with open(guideline_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            urls = []
            for line in lines:
                line = line.strip()
                if line.startswith("http"):
                    urls.append(line)
            
            print(f"Found {len(urls)} URLs to scrape.")
            
            for url in urls:
                try:
                    # 簡易的なスクレイピング
                    response = requests.get(url, timeout=10)
                    response.raise_for_status()
                    # エンコーディングの自動検出補正
                    response.encoding = response.apparent_encoding
                    
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # 本文抽出（scriptやstyleを除く）
                    for script in soup(["script", "style"]):
                        script.decompose()
                    
                    text = soup.get_text(separator="\n", strip=True)
                    title = soup.title.string if soup.title else url
                    
                    # テキストが長すぎる場合は分割する（簡易チャンキング）
                    chunk_size = 2000
                    text_chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
                    
                    for i, chunk in enumerate(text_chunks):
                        metadata = {
                            "title": f"{title} (Part {i+1})",
                            "law_category": "Administrative Guideline",
                            "section": "Guideline",
                            "tags": "Guideline, Web",
                            "source_type": "url",
                            "url": url
                        }
                        documents.append({
                            "content": chunk,
                            "metadata": metadata
                        })
                    print(f"Successfully loaded content from {url}")
                    
                except Exception as e:
                    print(f"Error scraping {url}: {e}")

        except Exception as e:
            print(f"Error reading guideline file: {e}")

    return documents

# 初期化時にサンプルドキュメントをロード
try:
    # 既存のDBを削除して再構築するために、明示的に初期化を呼び出す前に
    # ディレクトリチェックなどをここでやるべきだが、initialize_vector_store内で
    # 既存データをどう扱うかによる。今回は「追加」ではなく「再構築」が望ましいので
    # vector_store.py の initialize_vector_store が既存データをクリアするか確認が必要。
    # 実装上は追記型が多いので、本当はリセットが必要。
    # 簡易的に、サーバー起動時に data/chroma_db を削除するバッチ処理などがベターだが、
    # Pythonコード内でやるなら shutil.rmtree 等が必要。
    # 今回は安全のため「追記」動作のままとするが、重複の可能性がある。
    # ※ 本番運用ではID管理が必要。
    
    current_count = get_collection_count()
    if current_count == 0:
        print("Initializing vector store for the first time...")
        sample_docs = load_sample_documents()
        if sample_docs:
            print(f"Total documents to index: {len(sample_docs)}")
            initialize_vector_store(sample_docs)
    else:
        print(f"Vector store already contains {current_count} documents. Skipping initialization.")
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
        violation = ViolationDetail(
            law="景品表示法 / 薬機法（分析結果参照）",
            violation_section="AI分析",
            details=irac_analysis, # ここにGeminiのIRAC分析が常に入る
            severity="high" if not is_compliant else "low",
            evidence=[]
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
            "retrieval_debug": result.get("debug_info", {})
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