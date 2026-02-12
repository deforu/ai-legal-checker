from fastapi import APIRouter, HTTPException
from app.models.request import ComplianceCheckRequest
from app.models.response import ComplianceCheckResponse
from app.rag.retrieval import check_compliance

router = APIRouter()

@router.post("/compliance/check", response_model=ComplianceCheckResponse)
async def compliance_check(request: ComplianceCheckRequest):
    """
    投稿内容の法律コンプライアンスをチェックするエンドポイント
    """
    try:
        # RAGを使用してコンプライアンスチェックを実行
        result = await check_compliance(request)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))