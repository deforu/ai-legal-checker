from pydantic import BaseModel
from typing import Optional, List

class ViolationDetail(BaseModel):
    law: str  # 抵触した法律
    violation_section: str  # 抵触箇所
    details: str  # 違反の詳細説明
    severity: str  # 違反の重大度: high, medium, low
    evidence: Optional[List[dict]] = None  # 判断根拠

class Recommendation(BaseModel):
    original_text: str  # 元の問題テキスト
    revised_text: str  # 提案された修正版
    reason: str  # 修正理由

class AnalysisStep(BaseModel):
    step: str  # 処理ステップ名
    input: str  # ステップへの入力
    output: str  # ステップからの出力
    tool_used: str  # 使用したツール

class ComplianceCheckResponse(BaseModel):
    status: str  # success or error
    result: Optional[dict] = None  # チェック結果
    processing_time: Optional[int] = None  # 処理時間（ms）
    # cost_estimate: Optional[float] = None  # 推定コスト