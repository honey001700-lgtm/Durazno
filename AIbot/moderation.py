# moderation.py
import random
import discord
from typing import List, Set

# 惡徒用戶 ID 列表 (通常會從設定檔或資料庫載入)
EVIL_USER_IDS: Set[int] = {
    919067686124806204,  # 範例惡徒 ID
    919067686124806204,
}

# 惡徒關鍵字列表 (通常也會從設定檔或資料庫載入)
EVIL_KEYWORDS: List[str] = [
    "希特勒", "宇志波", "黑咖啡", "小穴" # 請替換為你實際要過濾的關鍵字
]

# 惡徒回應列表 
EVIL_RESPONSES: List[str] = [
    "閉嘴啦你！臭惡徒！(嫌惡)",
    "哼！我才不會回答像你這種壞蛋的問題呢！(轉頭)",
    "去你的！離我遠一點啦！(推開)",
    "你別說話了，再說我就要生氣囉！真是的！(鼓臉)",
    "滾啦！(丟一個臭雞蛋給你)"
]

def is_evil_user(user_id: int) -> bool:
    """檢查使用者是否為惡徒用戶。"""
    return user_id in EVIL_USER_IDS

def contains_evil_keyword(text: str) -> bool:
    """檢查文本內容是否包含惡徒關鍵字。"""
    return any(keyword in text for keyword in EVIL_KEYWORDS)

def get_evil_response() -> str:
    """隨機返回一個惡徒回應。"""
    return random.choice(EVIL_RESPONSES)

async def handle_moderation(message: discord.Message) -> bool:
    """
    處理訊息的審核邏輯。
    如果訊息被惡徒或敏感詞觸發，則返回 True 並發送回應；否則返回 False。
    """
    # 檢查發送者是否為惡徒
    if is_evil_user(message.author.id):
        return True # 惡徒用戶直接忽略，不回應

    # 檢查回覆的訊息作者是否為惡徒
    if message.reference:
        try:
            ref_msg = await message.channel.fetch_message(message.reference.message_id)
            if ref_msg and is_evil_user(ref_msg.author.id):
                return True # 不回應惡徒的訊息
        except discord.NotFound:
            pass # 如果引用的訊息找不到，則忽略此檢查

    # 檢查訊息中 @ 的用戶是否為惡徒
    if any(is_evil_user(user.id) for user in message.mentions):
        return True # 不回應提及惡徒的訊息

    # 檢查訊息內容是否包含惡徒關鍵字
    if contains_evil_keyword(message.content):
        await message.reply(get_evil_response(), mention_author=False)
        return True # 已處理惡徒關鍵字，返回 True

    return False # 沒有觸發任何審核規則