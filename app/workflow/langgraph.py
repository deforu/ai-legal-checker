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
    usage_metadata: list # 各ステップのトークン使用量を格納
    debug_info: dict

# ノード関数の定義
def retrieve_documents(state: WorkflowState):
    """
    関連するsource_docsを検索するノード
    薬機法・景表法・ガイドラインの3方向で独立検索し、本法を優先するブースティングを適用する。
    """
    input_text = state["input_text"]
    
    # LLMを使用して3つの検索クエリを生成
    query_generation_prompt = f"""
    You are a legal search expert.
    Based on the following input text, generate THREE distinct search queries to retrieve relevant legal provisions.
    
    1. Yakkiho Query: Focus on the Pharmaceutical and Medical Device Act (薬機法). Use specific terms like "第66条" or "誇大広告".
    2. Kehyoho Query: Focus on the Act against Unjustifiable Premiums and Misleading Representations (景表法). Use specific terms like "第5条" or "優良誤認".
    3. Guideline Query: Focus on administrative guidelines, Q&A, and practical standards.

    Input Text:
    "{input_text}"

    Instructions:
    1. Identify specific claims in the text that might violate the law.
    2. **CRITICAL: Generate queries PRIMARILY IN JAPANESE.**
    3. Return the result in the following JSON format ONLY:
       {{
           "yakkiho_query": "...",
           "kehyoho_query": "...",
           "guideline_query": "..."
       }}
    """
    
    queries = {"yakkiho_query": "", "kehyoho_query": "", "guideline_query": ""}

    try:
        response = llm_gemini.invoke(query_generation_prompt)
        response_content = response.content.strip()
        usage = getattr(response, 'usage_metadata', {})
        
        if "```json" in response_content:
            response_content = response_content.split("```json")[1].split("```")[0].strip()
        elif "```" in response_content:
             response_content = response_content.split("```")[1].split("```")[0].strip()
        queries = json.loads(response_content)
    except Exception as e:
        print(f"Query generation error: {e}")
        usage = {}
        # フォールバック
        queries = {
            "yakkiho_query": f"薬機法 {input_text[:50]}",
            "kehyoho_query": f"景表法 {input_text[:50]}",
            "guideline_query": f"ガイドライン {input_text[:50]}"
        }

    # 各スロットの検索実行
    top_k_per_slot = 7 # 少し多めに取ってからブースト・ソート・選択

    print(f"Searching Yakkiho: {queries.get('yakkiho_query')}")
    docs_yakkiho = search_documents(
        queries.get('yakkiho_query', ""), 
        top_k=top_k_per_slot, 
        where={"law_group": "yakkiho"}
    )
    
    print(f"Searching Kehyoho: {queries.get('kehyoho_query')}")
    docs_kehyoho = search_documents(
        queries.get('kehyoho_query', ""), 
        top_k=top_k_per_slot, 
        where={"law_group": "kehyoho"}
    )
    
    # 3. ガイドライン
    print(f"Searching Guidelines: {queries.get('guideline_query')}")
    docs_guideline = search_documents(
        queries.get('guideline_query', ""), 
        top_k=top_k_per_slot, 
        where={"law_group": "other"}
    )

    merged_documents = []
    merged_metadatas = []
    seen_contents = set()

    def process_and_boost(raw_docs, query_text):
        if not raw_docs or 'documents' not in raw_docs or not raw_docs['documents']:
            return []
        
        results = []
        for i, doc_content in enumerate(raw_docs['documents'][0]):
            if doc_content in seen_contents: continue
            
            metadata = raw_docs['metadatas'][0][i]
            # ChromaDBの距離スコアが利用できない場合は順位スコア
            base_score = 1.0 - (i * 0.1) 
            
            # 【ブースティング】
            # A. 本法ブースト: タイトルに「施行令」「施行規則」「府令」が含まれない場合
            is_main_act = not any(k in metadata.get('title', '') for k in ["施行令", "施行規則", "内閣府令", "府令"])
            if is_main_act and metadata.get('category') == "01_statute":
                base_score *= 1.5
                print(f"  Boosting Main Act: {metadata.get('title')}")

            # B. 条文番号一致ブースト
            section = metadata.get('section', '')
            if section in query_text and len(section) > 1:
                base_score *= 1.3
                print(f"  Boosting Section Match: {section}")

            results.append({
                "content": doc_content,
                "metadata": metadata,
                "score": base_score
            })
            seen_contents.add(doc_content)
        
        results.sort(key=lambda x: x['score'], reverse=True)
        return results

    # 各枠から4件ずつ抽出
    slot_yakkiho = process_and_boost(docs_yakkiho, queries.get('yakkiho_query', ""))[:4]
    slot_kehyoho = process_and_boost(docs_kehyoho, queries.get('kehyoho_query', ""))[:4]
    slot_guideline = process_and_boost(docs_guideline, queries.get('guideline_query', ""))[:4]

    # 全て統合
    final_combined = slot_yakkiho + slot_kehyoho + slot_guideline
    
    final_docs = {
        "documents": [[d["content"] for d in final_combined]],
        "metadatas": [[d["metadata"] for d in final_combined]]
    }
    
    print(f"Final merged docs count: {len(final_combined)} (Yakki:{len(slot_yakkiho)}, Kehyo:{len(slot_kehyoho)}, Guide:{len(slot_guideline)})")
    
    return {
        "retrieved_docs": final_docs,
        "usage_metadata": [usage],
        "debug_info": {
            "generated_query": f"Y:{queries.get('yakkiho_query')} | K:{queries.get('kehyoho_query')} | G:{queries.get('guideline_query')}",
            "retrieved_doc_count": len(final_combined),
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
        usage = getattr(result, 'usage_metadata', {})
    except Exception as e:
        print(f"Gemini API Error in analyze_compliance: {e}")
        if llm_openai:
            print("Switching to OpenAI for compliance analysis...")
            chain = analysis_prompt | llm_openai
            result = chain.invoke({"input_text": input_text, "docs_context": docs_context})
            usage = getattr(result, 'usage_metadata', {})
        else:
            raise e

    updated_state = state.copy()
    updated_state["usage_metadata"] = state.get("usage_metadata", []) + [usage]
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
         usage = getattr(result, 'usage_metadata', {})
    except Exception as e:
         print(f"Gemini API Error in generate_recommendations: {e}")
         if llm_openai:
              print("Switching to OpenAI for recommendations...")
              chain = recommendation_prompt | llm_openai
              result = chain.invoke({"input_text": input_text, "analysis_result": analysis_result["irac_analysis"]})
              usage = getattr(result, 'usage_metadata', {})
         else:
              raise e

    updated_state = state.copy()
    usage_list = state.get("usage_metadata", []) + [usage]
    
    # トークンの合計計算 (詳細なログから再計算)
    total_input = 0
    total_output = 0
    clean_usage_list = []
    
    for u in usage_list:
        if isinstance(u, dict) and u:
            total_input += u.get('input_tokens', 0)
            total_output += u.get('output_tokens', 0)
            clean_usage_list.append(u)
        elif hasattr(u, 'input_tokens'): # 念のためオブジェクトの場合も考慮
            total_input += u.input_tokens
            total_output += u.output_tokens
            clean_usage_list.append({"input_tokens": u.input_tokens, "output_tokens": u.output_tokens})
    
    updated_state["final_output"] = {
        "compliant": "適合" in result.content,
        "recommendations": result.content,
        "analysis_summary": analysis_result["irac_analysis"],
        "token_usage": {
            "input": total_input,
            "output": total_output,
            "total": total_input + total_output,
            "details": usage_list
        }
    }
    updated_state["usage_metadata"] = usage_list
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