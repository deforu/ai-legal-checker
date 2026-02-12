@echo off
REM AI Legal Checker プロトタイプ実行スクリプト

if not exist .venv (
    echo Creating virtual environment...
    python -m venv .venv
)

echo Activating virtual environment...
call .venv\Scripts\activate

echo Installing dependencies...
pip install -r requirements.txt

echo Starting the API server...
uvicorn app.main:app --reload --port=8000