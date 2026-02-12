import shutil
import os
import sys
import subprocess

def reset_db():
    db_path = "./data/chroma_db"
    if os.path.exists(db_path):
        print(f"Deleting existing database at {db_path}...")
        shutil.rmtree(db_path)
        print("Database deleted successfully.")
    else:
        print("Database directory does not exist. Skipping deletion.")

def run_script(script_name):
    print(f"Running {script_name}...")
    # .venvのpythonを使用してスクリプトを実行
    python_exe = os.path.join(".venv", "Scripts", "python.exe")
    result = subprocess.run([python_exe, script_name], capture_output=True, text=True)
    if result.returncode == 0:
        print(f"{script_name} completed successfully.")
        print(result.stdout)
    else:
        print(f"Error running {script_name}:")
        print(result.stderr)

if __name__ == "__main__":
    # 1. DBのリセット
    reset_db()
    
    # 2. XMLからの本則データのみの抽出
    run_script("parse_xml_law.py")
    
    # 3. データの登録
    run_script("init_data.py")
    
    print("\n--- DB Reset and Initialization Complete ---")
    print("Now only Main Provision (Real Rules) are stored in the RAG database.")
