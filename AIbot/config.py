# config.py
import os
from dotenv import load_dotenv

load_dotenv() # 載入 .env 檔案中的環境變數

# --- 環境變數設定 ---
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not DISCORD_TOKEN:
    raise ValueError("錯誤：DISCORD_TOKEN 環境變數未設定。請檢查 .env 檔案。")
if not GEMINI_API_KEY:
    raise ValueError("錯誤：GEMINI_API_KEY 環境變數未設定。請檢查 .env 檔案。")

# Gemini API URL
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

# --- 檔案路徑設定 ---
PERSONALITY_FILE_PATH = "AIbot/assets/personality.txt"
SPECIAL_USERS_DATA_PATH = "AIbot/data/special_users.json"

# --- 預設值設定 ---
DEFAULT_PERSONALITY = "色氣的兔女郎，今年26歲，成天想和別人性愛。"

# --- 回應訊息設定 ---
# 當提示內容為空時的預設回應列表
EMPTY_PROMPT_RESPONSES = [
    "哼！沒事不要 @ 我啦，我又不是24hr線上陪睡的笨蛋~ (撇頭)",
    "真是的，什麼都不說就 @ 我，很無聊欸！你想我想到沒詞了嗎？(嘟嘴)",
    "嗯？有什麼事就快說啦！我時間很寶貴的，才不是專門等你的呢！",
    "呀～什麼話都不講是想怎樣？該不會是…想跟我獨處嗎？嘻嘻～ (靠近)",
    "別這樣看我啦！沒事就不要亂叫，我會心臟砰砰跳的…真是的！",
    "幹嘛啦？想說什麼又不敢說嗎？真是個膽小鬼～ (輕笑)",
    "嗯？只是 @ 我就滿足了嗎？還是…想玩欲擒故縱？我可不會上當喔！(挑眉)",
    "就、就只會這樣嗎？太無聊了吧！想跟我說話就要好好講喔，不然... (盯著你)"
]

# Gemini API 錯誤回應
GEMINI_HTTP_ERROR_RESPONSE = "哼！你是不是做了什麼奇怪的事啊？不然握才不會壞掉呢！討厭啦～ (撇頭)"
GEMINI_GENERIC_ERROR_RESPONSE = "真是的！怎麼又出問題了啦～ 我才不是故意的喔！笨蛋… (嘟嘴)"
GEMINI_EMPTY_RESPONSE = "哼…我才不想回答你呢！"

# Bot 狀態訊息
BOT_ACTIVITY_STATUS = "在等你呼喚我呢...哼！"