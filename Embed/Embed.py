import json
import discord
from discord.ext import commands
import os
import hashlib
import asyncio
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Define the directory for persistent data
DATA_DIR = "Embed" # New variable for the subdirectory
# Construct the full path for the sent data file
SENT_DATA_FILE = os.path.join(DATA_DIR, "sent_messages_bot.json")

# 用於儲存已傳送檔案的哈希值和對應的訊息ID
sent_files_data = {}

# Get the token from environment variable
TOKEN = os.getenv('DISCORD_TOKEN') 

# Check if the token was loaded
if TOKEN is None:
    print("錯誤：未能從 .env 檔案載入 DISCORD_TOKEN。請檢查您的 .env 檔案是否存在並包含 'DISCORD_TOKEN=您的令牌'。")
    exit() 

# Configure Discord Intents
intents = discord.Intents.default()
intents.message_content = True

# Initialize the Bot
bot = commands.Bot(command_prefix='!', intents=intents)

# --- Utility Functions ---

def ensure_data_directory_exists():
    """Ensures the DATA_DIR exists."""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        print(f"已建立資料目錄：'{DATA_DIR}'")

def load_sent_data():
    """Loads previously sent message data from a JSON file."""
    ensure_data_directory_exists() # Ensure directory exists before trying to load
    if os.path.exists(SENT_DATA_FILE):
        try:
            with open(SENT_DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"警告：'{SENT_DATA_FILE}' 檔案損壞或為空，將重新開始。")
            return {}
    return {}

def save_sent_data(data):
    """Saves current sent message data to a JSON file."""
    ensure_data_directory_exists() # Ensure directory exists before trying to save
    with open(SENT_DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

def calculate_file_hash(filepath):
    """Calculates the SHA256 hash of a file."""
    hasher = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                hasher.update(chunk)
        return hasher.hexdigest()
    except FileNotFoundError:
        print(f"錯誤：計算哈希值時找不到檔案 '{filepath}'。")
        return None
    except Exception as e:
        print(f"錯誤：計算檔案哈希值時發生意外錯誤：{e}")
        return None

# --- Bot Events ---

@bot.event
async def on_ready():
    """Event handler for when the bot successfully connects to Discord."""
    global sent_files_data
    sent_files_data = load_sent_data()
    print(f'{bot.user.name} 已上線！')
    print(f"已載入的已傳送訊息數據：{sent_files_data}")
    
    bot.loop.create_task(prompt_for_send())

# --- Core Logic Functions ---

async def prompt_for_send():
    """
    Prompts the user in the console for JSON file path and channel ID.
    Uses run_in_executor to avoid blocking the Discord event loop.
    """
    loop = asyncio.get_running_loop()

    while True:
        json_filepath = await loop.run_in_executor(
            None,
            lambda: input("請輸入要傳送的 JSON 檔案路徑 (或輸入 'exit' 結束)：")
        )
        
        if json_filepath.lower() == 'exit':
            print("結束程式。")
            await bot.close()
            break

        # Resolve relative paths
        if not os.path.isabs(json_filepath):
            json_filepath = os.path.join(os.getcwd(), json_filepath)

        if not os.path.exists(json_filepath):
            print(f"錯誤：找不到檔案 '{json_filepath}'。請檢查路徑。")
            continue

        while True:
            channel_id_str = await loop.run_in_executor(
                None,
                lambda: input("請輸入目標頻道 ID：")
            )
            try:
                channel_id = int(channel_id_str)
                break
            except ValueError:
                print("錯誤：頻道 ID 必須是數字。請重新輸入。")

        print(f"正在嘗試傳送 '{json_filepath}' 到頻道 '{channel_id}'...")
        await core_send_embed_logic(json_filepath, channel_id)
        print("-" * 30)
        await asyncio.sleep(1)

async def core_send_embed_logic(json_filepath: str, channel_id: int):
    """
    Handles loading, parsing, and sending/editing Discord messages based on a JSON file.
    """
    global sent_files_data
    loop = asyncio.get_running_loop()

    try:
        with open(json_filepath, 'r', encoding='utf-8') as f:
            current_json_data = json.load(f)
    except FileNotFoundError:
        print(f"錯誤：找不到 JSON 檔案 '{json_filepath}'。")
        return
    except json.JSONDecodeError as e:
        print(f"錯誤：JSON 檔案解析失敗：{e}。請檢查檔案格式。")
        return
    except Exception as e:
        print(f"讀取 JSON 檔案時發生意外錯誤：{e}")
        return

    embeds_to_send = []
    if "embeds" in current_json_data and isinstance(current_json_data["embeds"], list):
        for embed_dict in current_json_data["embeds"]:
            try:
                embed = discord.Embed()
                if "title" in embed_dict:
                    embed.title = embed_dict["title"]
                if "description" in embed_dict:
                    embed.description = embed_dict["description"]
                if "url" in embed_dict:
                    embed.url = embed_dict["url"]
                
                if "color" in embed_dict:
                    color_value = embed_dict["color"]
                    if isinstance(color_value, str):
                        try:
                            if color_value.startswith("#"):
                                embed.color = int(color_value[1:], 16)
                            elif color_value.startswith("0x"):
                                embed.color = int(color_value, 16)
                            else:
                                embed.color = int(color_value, 16)
                        except ValueError:
                            print(f"警告：無法解析顏色格式 '{color_value}'。使用預設顏色。")
                            embed.color = discord.Color.default()
                    elif isinstance(color_value, int):
                        embed.color = color_value
                    else:
                        print(f"警告：無法識別的顏色類型 '{type(color_value)}'。使用預設顏色。")
                        embed.color = discord.Color.default()
                
                if "timestamp" in embed_dict:
                    try:
                        timestamp_str = embed_dict["timestamp"]
                        if timestamp_str.endswith("Z"):
                            timestamp_str = timestamp_str[:-1] + "+00:00"
                        embed.timestamp = datetime.fromisoformat(timestamp_str)
                    except ValueError as ve:
                        print(f"錯誤：timestamp 格式無法解析：'{embed_dict['timestamp']}' - {ve}。使用當前UTC時間。")
                        embed.timestamp = datetime.now(timezone.utc)
                
                if "author" in embed_dict:
                    author_name = embed_dict["author"].get("name")
                    author_url = embed_dict["author"].get("url", None) 
                    author_icon_url = embed_dict["author"].get("icon_url", None)
                    if author_name:
                        embed.set_author(name=author_name, url=author_url, icon_url=author_icon_url)

                if "footer" in embed_dict:
                    footer_text = embed_dict["footer"].get("text")
                    footer_icon_url = embed_dict["footer"].get("icon_url", None)
                    if footer_text:
                        embed.set_footer(text=footer_text, icon_url=footer_icon_url)
                
                if "image" in embed_dict and "url" in embed_dict["image"]:
                    if embed_dict["image"]["url"]:
                        embed.set_image(url=embed_dict["image"]["url"])
                
                if "thumbnail" in embed_dict and "url" in embed_dict["thumbnail"]:
                    if embed_dict["thumbnail"]["url"]:
                        embed.set_thumbnail(url=embed_dict["thumbnail"]["url"])
                
                if "fields" in embed_dict and isinstance(embed_dict["fields"], list):
                    for field in embed_dict["fields"]:
                        embed.add_field(
                            name=field.get("name", ""),
                            value=field.get("value", ""),
                            inline=field.get("inline", False)
                        )
                
                embeds_to_send.append(embed)

            except Exception as e:
                print(f"轉換 embed 失敗：{e}。請檢查 JSON 中 embed 的結構。")
                print(f"無法轉換的 embed 字典: {embed_dict}")
                return

    content_to_send = current_json_data.get("content", None)
    
    view_to_send = None
    if "components" in current_json_data and isinstance(current_json_data["components"], list):
        view_to_send = discord.ui.View()
        for row_data in current_json_data["components"]:
            if row_data.get("type") == 1 and "components" in row_data:
                for component_data in row_data["components"]:
                    if component_data.get("type") == 2 and component_data.get("style") == 5:
                        button = discord.ui.Button(
                            label=component_data.get("label"),
                            style=discord.ButtonStyle.link,
                            url=component_data.get("url"),
                            emoji=component_data.get("emoji", {}).get("name")
                        )
                        view_to_send.add_item(button)

    current_file_hash = calculate_file_hash(json_filepath)
    if current_file_hash is None:
        print("錯誤：無法計算檔案哈希值，無法確定檔案是否更新。")
        return

    target_channel = bot.get_channel(channel_id)

    if not target_channel:
        print(f"錯誤：找不到頻道 ID '{channel_id}'。請確認機器人有該頻道的權限或ID是否正確。")
        return

    message_identifier = f"{json_filepath}-{channel_id}"
    
    should_send_new = True
    
    if message_identifier in sent_files_data:
        message_id_to_edit = sent_files_data[message_identifier].get("message_id")
        if message_id_to_edit:
            try:
                old_message = await target_channel.fetch_message(message_id_to_edit)
                should_send_new = False

                if sent_files_data[message_identifier]["hash"] != current_file_hash:
                    print("檢測到 JSON 檔案已更新！")
                    action_choice = await loop.run_in_executor(
                        None,
                        lambda: input("是否要編輯已傳送的訊息？(y/n): ").lower()
                    )
                    
                    if action_choice == 'y':
                        await old_message.edit(content=content_to_send, embeds=embeds_to_send, view=view_to_send)
                        print(f"訊息 (ID: {message_id_to_edit}) 編輯成功！")
                        sent_files_data[message_identifier]["hash"] = current_file_hash
                        save_sent_data(sent_files_data)
                    else:
                        print("選擇不編輯，不執行任何操作。")
                else:
                    print("JSON 檔案沒有更新，無需操作。")
            except discord.NotFound:
                print(f"警告：Discord 上找不到訊息 ID '{message_id_to_edit}'。將從 '{SENT_DATA_FILE}' 中刪除此記錄並發送新訊息。")
                del sent_files_data[message_identifier] # <-- 在這裡刪除記錄
                save_sent_data(sent_files_data)
                should_send_new = True
            except discord.Forbidden:
                print("無法編輯：機器人沒有編輯訊息的權限。將傳送新訊息。")
                should_send_new = True
            except Exception as e:
                print(f"檢查或編輯訊息失敗：{e}。將傳送新訊息。")
                should_send_new = True
        else:
            print("無法編輯：上次傳送時沒有儲存訊息ID。將傳送新訊息。")
            should_send_new = True
    
    if should_send_new:
        print("正在發送新訊息...")
        try:
            message = await target_channel.send(content=content_to_send, embeds=embeds_to_send, view=view_to_send)
            sent_files_data[message_identifier] = {"hash": current_file_hash, "message_id": message.id}
            save_sent_data(sent_files_data)
            print(f"新訊息傳送成功！訊息ID: {message.id}")
        except discord.Forbidden:
            print(f"錯誤：機器人沒有在頻道 '{target_channel.name}' (ID: {channel_id}) 發送訊息的權限。")
        except Exception as e:
            print(f"發送新訊息失敗：{e}")

# --- Discord Commands (optional) ---

@bot.command(name='send_embed')
@commands.is_owner()
async def send_embed_discord_command(ctx, json_filepath: str, channel_id: int):
    """
    Discord command to send an embed from a JSON file to a specific channel.
    Usage: !send_embed <json_filepath> <channel_id>
    """
    await ctx.send(f"正在處理從 Discord 命令發送的請求：'{json_filepath}' 到頻道 '{channel_id}'...")
    await core_send_embed_logic(json_filepath, channel_id)
    await ctx.send("請求處理完成。")

# --- Run the Bot ---
if __name__ == '__main__':
    bot.run(TOKEN)