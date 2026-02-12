from fastapi import FastAPI
from app.api.v1.endpoints import router as api_v1_router

app = FastAPI(title="AI Legal Checker API", version="0.1.0")

# APIルートの登録
app.include_router(api_v1_router, prefix="/api/v1")

@app.get("/")
def read_root():
    return {"message": "AI Legal Checker API is running"}