from typing import Dict, Any, TypedDict
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from app.rag.vector_store import search_documents
import os
import json
from dotenv import load_dotenv

load_dotenv()

from langchain_openai import ChatOpenAI
from google.api_core.exceptions import ResourceExhausted
import time

# 環境変数からAPIキーを読み込む
google_api_key = os.getenv("GOOGLE_API_KEY")
openai_api_key = os.getenv("OPENAI_API_KEY")

if not google_api_key:
    raise ValueError("GOOGLE_API_KEY environment variable is not set")

# LLMの初期化
llm_gemini = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0, google_api_key=google_api_key)

# OpenAIの初期化（APIキーがある場合のみ）
llm_openai = None
if openai_api_key:
    llm_openai = ChatOpenAI(model="gpt-4o", temperature=0, openai_api_key=openai_api_key)



class WorkflowState(TypedDict):
    input_text: str
    retrieved_docs: list
    analysis_result: dict
    final_output: dict
    current_step: str
    debug_info: dict

# ノード関数の定義
def retrieve_documents(state: WorkflowState):
    """
    関連するsource_docsを検索するノード（検索クエリの生成を改善）
    """
    input_text = state["input_text"]
    
    # LLMを使用して検索クエリを拡張生成（条文用とガイドライン用に分ける）
    query_generation_prompt = f"""
    You are a legal search expert.
    Based on the following input text, generate TWO distinct search queries to retrieve relevant legal provisions.
    
    1. Statute Query: Focus on the Pharmaceutical and Medical Device Act (PMD Act) and the Act against Unjustifiable Premiums and Misleading Representations (Premiums and Representations Act). Use specific legal terms and article numbers.
    2. Guideline Query: Focus on administrative guidelines, interpretation standards, and "Medical Drugs Guidelines". Use terms related to practical application and criteria.

    Input Text:
    "{input_text}"

    Instructions:
    1. Identify specific claims in the text that might violate the law.
    2. **CRITICAL: Generate functionality PRIMARILY IN JAPANESE.**
    3. Return the result in the following JSON format ONLY:
       {{
           "statute_query": "...",
           "guideline_query": "..."
       }}
    
    Example Output:
    {{
        "statute_query": "薬機法 第66条 誇大広告 未承認医薬品 景品表示法 優良誤認",
        "guideline_query": "医薬品等適正広告基準 効能効果の範囲 ダイエット 痩身 ガイドライン"
    }}
    """
    
    statute_query = ""
    guideline_query = ""

    try:
        response_content = llm_gemini.invoke(query_generation_prompt).content.strip()
        # Clean up code blocks if present
        if "```json" in response_content:
            response_content = response_content.split("```json")[1].split("```")[0].strip()
        elif "```" in response_content:
             response_content = response_content.split("```")[1].split("```")[0].strip()
        
        queries = json.loads(response_content)
        statute_query = queries.get("statute_query", "")
        guideline_query = queries.get("guideline_query", "")
        
    except Exception as e:
        print(f"Gemini API Error in retrieve_documents: {e}")
        if llm_openai:
             print("Switching to OpenAI for query generation...")
             try:
                response_content = llm_openai.invoke(query_generation_prompt).content.strip()
                if "```json" in response_content:
                    response_content = response_content.split("```json")[1].split("```")[0].strip()
                elif "```" in response_content:
                     response_content = response_content.split("```")[1].split("```")[0].strip()
                queries = json.loads(response_content)
                statute_query = queries.get("statute_query", "")
                guideline_query = queries.get("guideline_query", "")
             except Exception as oe:
                 print(f"OpenAI API Error: {oe}")
                 raise oe
        else:
             raise e

    # 検索の実行（それぞれトップ10件を取得）
    print(f"Executing Search 1 (Statute): {statute_query}")
    # カテゴリ：01_statute かつ 本則(is_main_provision: True) に限定して検索
    docs_statute = search_documents(statute_query, top_k=10, where={"$and": [{"category": "01_statute"}, {"is_main_provision": True}]})
    
    print(f"Executing Search 2 (Guideline): {guideline_query}")
    # 条文以外（事例や運用基準）を対象に検索
    docs_guideline = search_documents(guideline_query, top_k=10, where={"category": {"$ne": "01_statute"}})
    
    # 結果の統合と重複排除
    merged_documents = []
    merged_metadatas = []
    seen_contents = set()
    
    def process_results(raw_docs):
        if raw_docs and 'documents' in raw_docs and raw_docs['documents']:
            for i, doc_content in enumerate(raw_docs['documents'][0]):
                if doc_content not in seen_contents:
                    metadata = raw_docs['metadatas'][0][i]
                    # 新しいメタデータ構造に合わせて、全てのヒットを採用（既にインデックス時に精査済みのため）
                    merged_documents.append(doc_content)
                    merged_metadatas.append(metadata)
                    seen_contents.add(doc_content)
    
    process_results(docs_statute)
    process_results(docs_guideline)
    
    # 上位10件に絞る（合計）
    final_docs = {
        "documents": [merged_documents[:10]],
        "metadatas": [merged_metadatas[:10]]
    }
    
    print(f"Final merged docs count: {len(final_docs['documents'][0])}")
    
    return {
        "retrieved_docs": final_docs,
        "debug_info": {
            "generated_query": f"Statute: {statute_query} | Guideline: {guideline_query}",
            "retrieved_doc_count": len(final_docs["documents"][0]),
            "retrieved_doc_titles": [f"{m.get('title', 'Unknown')} - {m.get('section', '')}" for m in final_docs["metadatas"][0]]
        }
    }

def analyze_compliance(state: WorkflowState): # Changed AgentState to WorkflowState
    """
    検索された文書に基づいてコンプライアンス分析を行うノード
    """
    input_text = state["input_text"]
    retrieved_docs = state["retrieved_docs"]
    
    # Retrieve documents content
    docs_context = ""
    if retrieved_docs and 'documents' in retrieved_docs and retrieved_docs['documents']:
        for i, doc in enumerate(retrieved_docs['documents'][0]):
            meta = retrieved_docs['metadatas'][0][i]
            title = meta.get('title', 'Unknown Law')
            section = meta.get('section', '')
            
            # 制限撤廃: 条文全体を含める
            docs_context += f"Document {i+1} ({title} {section}):\n{doc}\n\n"
            
    # LLM instruction for analysis
    analysis_prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a strict legal expert AI.
Analyze the compliance of the input text based *only* on the provided [Related Legal Documents].
Specifically, strictly review from the perspectives of the Premiums and Representations Act (misleading representations) and the Pharmaceutical and Medical Device Act (prohibition of advertising unapproved drugs/exaggerated claims).

Prohibitions:
- Avoid ambiguous expressions; clearly point out the risk as "high possibility of violation" or "suspicion of violation".
- Do not make judgments based on knowledge outside the provided legal documents. Always cite the article (or guideline) as the basis for your argument.

Output Format:
Please structure your response in IRAC format (Issue, Rule, Application, Conclusion) in Japanese.

1. **Issue (論点)**: Which part of the text is problematic?
2. **Rule (法的事項)**: Which specific article of the law or guideline applies? (Cite the content from provided documents)
3. **Application (あてはめ)**: How does the input text conflict with the rule?
4. **Conclusion (結論)**: Final judgment (Compliant/Non-compliant) and risk level.
"""),
        ("user", """
[Input Text]
{input_text}

[Related Legal Documents]
{docs_context}

Analyze the compliance:
""")
    ])

    try:
        chain = analysis_prompt | llm_gemini
        result = chain.invoke({"input_text": input_text, "docs_context": docs_context})
    except Exception as e:
        print(f"Gemini API Error in analyze_compliance: {e}")
        if llm_openai:
            print("Switching to OpenAI for compliance analysis...")
            chain = analysis_prompt | llm_openai
            result = chain.invoke({"input_text": input_text, "docs_context": docs_context})
        else:
            raise e

    updated_state = state.copy()
    updated_state["analysis_result"] = {"irac_analysis": result.content}
    updated_state["current_step"] = "analyze"

    print("Compliance analysis completed using IRAC framework")
    return updated_state

def generate_recommendations(state: WorkflowState) -> WorkflowState:
    """言い換え案を生成するノード"""
    input_text = state["input_text"]
    analysis_result = state["analysis_result"]

    recommendation_prompt = ChatPromptTemplate.from_messages([
        ("system", "あなたは法律コンサルタントです。法律に抵触する可能性のある表現に対して、違法性を排除した代替表現を提案してください。"),
        ("human", """
元の表現: {input_text}

分析結果: {analysis_result}

上記の分析結果を踏まえ、法律に抵触しない代替表現を3つ提案してください。
各提案には、なぜその表現が安全であるかの理由も含めてください。

出力形式:
1. 提案表現1: [表現] - [理由]
2. 提案表現2: [表現] - [理由]
3. 提案表現3: [表現] - [理由]

出力は日本語でお願いします。
        """)
    ])

    chain = recommendation_prompt | llm_gemini
    
    try:
         result = chain.invoke({"input_text": input_text, "analysis_result": analysis_result["irac_analysis"]})
    except Exception as e:
         print(f"Gemini API Error in generate_recommendations: {e}")
         if llm_openai:
              print("Switching to OpenAI for recommendations...")
              chain = recommendation_prompt | llm_openai
              result = chain.invoke({"input_text": input_text, "analysis_result": analysis_result["irac_analysis"]})
         else:
              raise e

    updated_state = state.copy()
    updated_state["final_output"] = {
        "compliant": "適合" in result.content,
        "recommendations": result.content,
        "analysis_summary": analysis_result["irac_analysis"]
    }
    updated_state["current_step"] = "recommend"

    print("Recommendations generated")
    return updated_state

# ワークフローの作成
def create_workflow():
    """
    LangGraphを使用した法律チェックワークフローを作成
    """
    workflow = StateGraph(WorkflowState)

    # ノードの追加
    workflow.add_node("retrieve", retrieve_documents)
    workflow.add_node("analyze", analyze_compliance)
    workflow.add_node("recommend", generate_recommendations)

    # エントリポイントの設定
    workflow.set_entry_point("retrieve")

    # エッジの追加（フローの定義）
    workflow.add_edge("retrieve", "analyze")
    workflow.add_edge("analyze", "recommend")
    workflow.add_edge("recommend", END)

    # ワークフローのコンパイル
    app = workflow.compile()
    return app