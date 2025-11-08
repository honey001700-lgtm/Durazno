# utils.py
import os
import json
import textwrap
from typing import Dict, Any

# 讀取檔案內容的通用函數
def read_file_content(file_path: str, default_content: str = "") -> str:
    """
    讀取指定檔案的內容，如果檔案不存在或讀取失敗則返回預設內容。
    """
    try:
        if not os.path.exists(file_path):
            print(f"警告：檔案 '{file_path}' 不存在。將使用預設內容。")
            return default_content
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                print(f"警告：檔案 '{file_path}' 為空。將使用預設內容。")
            return content or default_content
    except Exception as e:
        print(f"錯誤：讀取檔案 '{file_path}' 失敗: {e}。將使用預設內容。")
        return default_content

# 載入 JSON 資料的通用函數
def load_json_data(file_path: str) -> Dict[str, Any]:
    """
    載入指定 JSON 檔案的資料，如果檔案不存在或讀取失敗則返回空字典。
    """
    try:
        if not os.path.exists(file_path):
            print(f"警告：JSON 檔案 '{file_path}' 不存在。返回空資料。")
            return {}
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"錯誤：解析 JSON 檔案 '{file_path}' 失敗: {e}。返回空資料。")
        return {}
    except Exception as e:
        print(f"錯誤：載入 JSON 檔案 '{file_path}' 失敗: {e}。返回空資料。")
        return {}

# 構建 Gemini 提示的輔助函數 (可在此處進一步客製化提示模板)
def build_gemini_prompt(
    bot_personality: str, 
    user_prompt: str, 
    user_name: str, 
    user_style: str = None
) -> str:
    """
    根據 Bot 性格、使用者輸入、使用者名稱和風格來構建完整的 Gemini 提示。
    """
    adjusted_personality = f"{bot_personality}\n請以「{user_style}」的風格來回答。" if user_style and user_style != "普通" else bot_personality
    
    # 使用 textwrap.dedent 清理多行字串的縮排，使提示更整潔
    full_prompt = textwrap.dedent(f"""
    {adjusted_personality}
    以下是使用者 {user_name} 說的話：{user_prompt}
    請盡量以 {user_name} 稱呼對方。
    """)
    return full_prompt.strip() # 移除可能的多餘空白