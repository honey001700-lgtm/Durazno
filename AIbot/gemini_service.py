# gemini_service.py
import requests
import json
from typing import Dict, Any

from config import GEMINI_URL, GEMINI_HTTP_ERROR_RESPONSE, GEMINI_GENERIC_ERROR_RESPONSE, GEMINI_EMPTY_RESPONSE
from utils import build_gemini_prompt

def query_gemini_api(
    bot_personality: str, 
    user_prompt: str, 
    user_name: str, 
    user_style: str = None
) -> str:
    """
    呼叫 Gemini AI API，並根據 Bot 性格、使用者輸入和風格產生回應。
    """
    full_prompt = build_gemini_prompt(bot_personality, user_prompt, user_name, user_style)
    
    headers = {"Content-Type": "application/json"}
    payload = {"contents": [{"role": "user", "parts": [{"text": full_prompt}]}]}

    try:
        response = requests.post(GEMINI_URL, headers=headers, json=payload, timeout=30) # 增加 timeout
        response.raise_for_status() # 檢查 HTTP 請求是否成功 (2xx)

        # 嘗試解析 JSON 回應
        response_json = response.json()
        
        # 安全地提取文字內容
        text = response_json.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        
        return text or GEMINI_EMPTY_RESPONSE
        
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP 錯誤: {http_err} - 回應: {response.text}")
        return GEMINI_HTTP_ERROR_RESPONSE
    except requests.exceptions.ConnectionError as conn_err:
        print(f"連線錯誤: {conn_err}")
        return GEMINI_GENERIC_ERROR_RESPONSE # 或者提供一個專門的連線錯誤訊息
    except requests.exceptions.Timeout as timeout_err:
        print(f"請求超時: {timeout_err}")
        return GEMINI_GENERIC_ERROR_RESPONSE # 或者提供一個專門的超時錯誤訊息
    except json.JSONDecodeError as json_err:
        print(f"JSON 解析錯誤: {json_err} - 回應: {response.text}")
        return GEMINI_GENERIC_ERROR_RESPONSE
    except Exception as e:
        print(f"呼叫 Gemini AI 發生未知錯誤: {e}")
        return GEMINI_GENERIC_ERROR_RESPONSE