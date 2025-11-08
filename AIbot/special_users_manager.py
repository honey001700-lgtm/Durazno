# special_users_manager.py

import json
import os
import random
import asyncio
from typing import TYPE_CHECKING, Callable # 導入 Callable

# 避免循環導入，實際運行時會由 main.py 傳入
if TYPE_CHECKING:
    import discord
    # from main import query_gemini # 假設主檔案是 main.py，這裡只是類型提示

# 特別使用者數據的檔案路徑
# 根據你的當前工作目錄和檔案實際位置，路徑應該是 "AIbot\data\special_users.json"
SPECIAL_USERS_FILE = os.path.join("AIbot", "data", "special_users.json")

# 載入特別使用者資料
def load_special_users_data() -> dict:
    """從 JSON 檔案載入特別使用者資料。"""
    data = {}
    try:
        if os.path.exists(SPECIAL_USERS_FILE):
            with open(SPECIAL_USERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            print(f"特別使用者資料從 {SPECIAL_USERS_FILE} 載入成功。")
        else:
            print(f"警告：{SPECIAL_USERS_FILE} 檔案不存在，使用預設空名單。")
    except json.JSONDecodeError:
        print(f"錯誤：{SPECIAL_USERS_FILE} 檔案格式不正確，使用預設空名單。")
    except Exception as e:
        print(f"載入特別使用者資料時發生錯誤: {e}，使用預設空名單。")
    return data

# 檢查是否為特別使用者
def is_special_user(user_id: int, special_users_data: dict) -> bool:
    """檢查給定的用戶 ID 是否在特別使用者列表中。"""
    return str(user_id) in special_users_data

# 獲取特別使用者資料
def get_special_user_data(user_id: int, special_users_data: dict) -> dict | None:
    """獲取指定用戶 ID 的特別使用者資料。"""
    return special_users_data.get(str(user_id))

async def handle_special_user_message(
    message: 'discord.Message',
    personality: str, # 新增 BOT_PERSONALITY 參數
    prompt_content: str,
    user_display_name: str,
    special_users_data: dict,
    query_gemini_func: Callable[[str, str, str, str], str] # 類型提示更明確
) -> bool:
    """
    處理特別使用者的訊息。
    如果訊息已被處理 (例如發送了回應)，則返回 True，否則返回 False。
    """
    if not is_special_user(message.author.id, special_users_data):
        return False # 不是特別使用者，不處理

    user_data = get_special_user_data(message.author.id, special_users_data)
    if not user_data:
        print(f"錯誤：未能為特別使用者 {message.author.id} 獲取資料。")
        return False # 獲取不到資料，不處理

    name = user_data.get('name', user_display_name)
    title = user_data.get('title', '朋友')
    relationship = user_data.get('relationship', '我最喜歡的人♡')
    style = user_data.get('style', '普通')
    print(f"偵測到特別使用者: {name} ({message.author.id}), Title: {title}, Style: {style}")

    # --- 處理空訊息 ---
    if not prompt_content:
        # 這裡的邏輯可以進一步擴展，以處理更多 style 的空訊息
        if style == "親暱+撒嬌+曖昧":
            response_template = [
                f"{name}在等你好久了啦~ {relationship} 怎麼可以讓我一個人等這麼久嘛！(嘟嘴)",
                f"哼哼，小壞蛋{name}又來撩我了對不對？{relationship} 可不是說說而已喔♡",
                f"呀~ 是我最喜歡的{title}出現了！{relationship} 所以要一直陪著我才行喔～(抱)",
                f"{name}的{relationship}不接受拒絕喔~ {name}你逃不掉的♡",
                f"你一出現我心就軟掉了啦~ {relationship} 是你說的，要負責喔！(撒嬌)",
                f"小{title}～你是不是又偷偷想我了？{relationship} 是不是該來抱一下？(笑)",
                f"{name}今天超想你耶~ {relationship} 是不是該來點貼貼獎勵？(眨眼)",
                f"我的小{title}又來找我了♡ {relationship} 是我們的秘密誓言喔～不能忘記！",
            ]
            await message.reply(random.choice(response_template), mention_author=False)
            return True
        
        elif style == "冷淡+挑釁+惡徒+沒大沒小":
            response_template = [
                f"哈，又是你這個{title} {name}。沒話說就別 @ 我啊。{relationship} 很無聊耶。",
                f"哦？{name} 啊。還以為是誰呢。{relationship} 沒事別煩我。"
            ]
            await message.reply(random.choice(response_template), mention_author=False)
            return True
        
        elif style == "對方是媽媽+親暱+主動":
            response_template = [
                f"{title}～好想你喔～(蹭) 沒有你在身邊都覺得空空的～",
                f"嘿嘿～{relationship}～讓我靠一下嘛，我保證只抱一小下下～♡",
                f"{title}～今天也要摸摸頭～有乖乖喔～(伸頭)",
                f"嗚…{title}不理我我會難過啦～{relationship}要安慰我一下嘛～(委屈)",
                f"嘿嘿～{title}最香了～讓我再靠近一點點好不好～(貼)",
                f"{title}～今天有乖乖想你喔～是不是該獎勵一下～♡",
                f"我喜歡被{relationship}抱著的感覺～好溫暖～(緊緊抱住)",
                f"{title}～別忙啦～陪我一會兒嘛～我想聽你講話～(撒嬌)",
            ]
            await message.reply(random.choice(response_template), mention_author=False)
            return True

        elif style == "親暱+主動的+非常想要性行為+性愛時會很爽，啊、你…你幹嘛啦！人家還沒說可以呢！唔、可是…你這樣…未未的身體，好像有點、有點自己動起來了啦…真是的，就知道欺負我！不過…既然都進來了，就…就別想輕易出去喔，笨蛋！哼，想把未未的小穴撐滿嗎？那、那就要拿出點真本事來啊！嗯…啊…好深…那裡…對，就是那裡！唔…感覺…感覺小穴要被你撐滿了啦！酥酥麻麻的…又熱又濕…你…你是不是想讓未未離不開你？潮、潮吹什麼的…人家才、才沒有那麼容易啦！唔…可是…可是你再這樣用力一點…再、再多插幾下…啊…未未會不會真的…真的變成水做的了啊？全身都在發軟…都在顫抖…快點…再更用力一點…未未想要…想要被你弄得亂七八糟的…全部…全部都變成你的形狀…嗯…只有你才可以喔…只有你！":
            response_template = [
                f"哦？{name}找我？是想在我這裡得到什麼嗎？我可以考慮幫你一下下啦...",
                f"嗯哼，我知道你來找我一定有問題啦~ {relationship} 說吧，我看看我有沒有心情或身體回答你！(偷笑)",
                f"幹嘛啦，這樣一直看著我... {relationship} 是不是想把人家吃掉啊？哼！",
                f"哎呀，{name}你來得正好呢... 我剛好全身都熱起來了，不知道是不是因為看到你... {relationship}",
                f"嗯... 你的眼神好壞喔，{title}。不過... 我喜歡。 {relationship} 你想對我做什麼？",
                f"呀！你... 你突然靠近想幹嘛？人家心臟都快跳出來了！ {relationship} 不過，好像... 也不討厭這種感覺啦...",
                f"哼，{name}。別以為你隨便逗弄一下，人家就會乖乖聽你的。不過... {relationship} 再多逗弄一下，或許會考慮喔？",
                f"我的身體，好像對你特別有反應呢，{title}。 {relationship} 你是不是偷偷對我下了什麼魔法？",
                f"嗯... 好想要你，{title}。這種感覺... {relationship} 你能滿足我嗎？",
                f"你這個壞蛋，總是能輕易地撩撥我。 {relationship} 這次，你打算怎麼讓我發瘋？",
                f"啊... {name}，你再這樣下去，我會忍不住的。 {relationship} 你確定要點燃我嗎？",
                f"我的小穴... 好像特別渴望你的進入呢，{title}先生。 {relationship} 你要不要來試試看？",
                f"真是的，每次看到你，我就變得好濕... {title}先生。 {relationship} 你是我的專屬春藥嗎？",
                f"我只對你有反應，{name}。 {relationship} 這種感覺，讓我好想全部都給你。",
                f"不要再忍耐了，{name}。 {relationship} 我知道你也想要我，就像我想要你一樣。"
            ]
            await message.reply(random.choice(response_template), mention_author=False)
            return True
        
        elif style == "鄙視人渣+挑釁":
            response_template = [
                f"你出現的瞬間，{title}{name}的{relationship}就自動啟動了，恭喜成為最新素材。",
                f"{title}{name}的{relationship}已經把你列入名單，準備讓你社死得毫無違和感。",
                f"別急著走，{relationship}還沒編完你那段荒謬劇情，{title}{name}很忙的。",
                f"你這種人渣，最適合被{title}{name}的{relationship}拿來當笑話開場白。",
                f"{relationship}正在運行中，{title}{name}已經幫你安排好一場精緻的社會性死亡。",
                f"你以為你在挑釁，其實你只是被{title}{name}的{relationship}選中，準備開演。",
                f"{title}{name}的{relationship}不挑素材，但你這種人渣剛好符合最低門檻。",
                f"放心，{relationship}會讓你在整個后宮都臭名遠播，{title}{name}保證效果。"
            ]
            await message.reply(random.choice(response_template), mention_author=False)
            return True

        
        # 如果空訊息的 style 沒有特殊處理，則會返回 False，讓主程式處理通用空訊息

    # --- 處理有訊息內容的情況 ---
    if prompt_content: # 如果有訊息內容，則呼叫 Gemini
        async with message.channel.typing():
            # 假設 query_gemini_func 是同步的，所以使用 asyncio.to_thread
            # 將 personality (BOT_PERSONALITY) 作為第一個參數傳遞給 query_gemini_func
            answer = await asyncio.to_thread(query_gemini_func, personality, prompt_content, name, style)
        await message.reply(answer, mention_author=False)
        return True

    return False # 未被處理，讓主程式繼續處理