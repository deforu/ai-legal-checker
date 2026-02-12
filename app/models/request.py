from pydantic import BaseModel
from typing import Optional, List

class ContentData(BaseModel):
    type: str  # "text" or "image"
    data: str  # テキスト内容またはBase64エンコードされた画像データ

class RequestOptions(BaseModel):
    target_laws: Optional[List[str]] = None  # チェック対象の法律リスト
    category: Optional[str] = None  # 商品カテゴリ
    product_specifications: Optional[str] = None  # 商品仕様情報

class ComplianceCheckRequest(BaseModel):
    content: ContentData
    options: Optional[RequestOptions] = None