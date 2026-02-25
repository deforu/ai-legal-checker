def estimate_tokens(text):
    # 日本語と英語の混合を想定した簡易見積もり
    # 1文字あたり、英語なら約0.25トークン、日本語なら約1.0〜1.5トークン
    # 法律文書は漢字が多いため、安全を見て 1文字 ≒ 1トークンに近い値で計算
    return int(len(text) * 0.8) 

# 1. retrieve_documents ステップ
query_gen_prompt_base = 1500 # プロンプト文字列の文字数
input_text_sample = "このサプリを飲むだけで、1ヶ月で10kg痩せました！しかも、癌も治るという噂です。"
tokens_step1_in = estimate_tokens(" " * query_gen_prompt_base + input_text_sample)
tokens_step1_out = 100 # JSONレスポンス

# 2. analyze_compliance ステップ (最大の消費ポイント)
analysis_system_prompt = 2500 # システム指示の文字数
# RAGコンテキスト: 上位10件、各2000文字 (retrieval.py 140行目)
rag_total_chars = 2000 * 10 
analysis_in_total = analysis_system_prompt + len(input_text_sample) + rag_total_chars
tokens_step2_in = estimate_tokens(" " * analysis_in_total)
tokens_step2_out = 1500 # IRAC分析の詳細な出力

# 3. generate_recommendations ステップ
recommend_prompt_base = 1000
recommend_in_total = recommend_prompt_base + len(input_text_sample) + 1500 # 分析結果を含む
tokens_step3_in = estimate_tokens(" " * recommend_in_total)
tokens_step3_out = 800 # 3つの提案

print(f"--- Token Usage Estimate per Request (Approx) ---")
print(f"Step 1 (Query Gen): In={tokens_step1_in}, Out={tokens_step1_out}")
print(f"Step 2 (Analysis ): In={tokens_step2_in}, Out={tokens_step2_out}  <-- MAIN COST")
print(f"Step 3 (Recommend): In={tokens_step3_in}, Out={tokens_step3_out}")
print(f"-------------------------------------------------")
total_in = tokens_step1_in + tokens_step2_in + tokens_step3_in
total_out = tokens_step1_out + tokens_step2_out + tokens_step3_out
print(f"Total Input Tokens : {total_in}")
print(f"Total Output Tokens: {total_out}")
print(f"Grand Total        : {total_in + total_out}")
