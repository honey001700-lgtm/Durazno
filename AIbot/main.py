# main.py
import discord
from discord.ext import commands
import asyncio
import random
from config import (
    DISCORD_TOKEN, GEMINI_URL, BOT_ACTIVITY_STATUS,
    PERSONALITY_FILE_PATH, DEFAULT_PERSONALITY, EMPTY_PROMPT_RESPONSES
)
from utils import read_file_content
from gemini_service import query_gemini_api
from moderation import handle_moderation
from special_users_manager import load_special_users_data, handle_special_user_message

BOT_PERSONALITY = read_file_content(PERSONALITY_FILE_PATH, DEFAULT_PERSONALITY)
SPECIAL_USERS_DATA = load_special_users_data()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"{bot.user} 已上線！")
    await bot.change_presence(activity=discord.Game(name=BOT_ACTIVITY_STATUS))

@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
        return

    await bot.process_commands(message)

    prompt = message.content.strip()
    user_name = message.author.display_name
    mentioned = bot.user in message.mentions
    replied = message.reference and await is_reply_to_bot(message)

    if not (mentioned or replied) or message.content.startswith(bot.command_prefix):
        return

    if await handle_moderation(message):
        return

    if await handle_special_user_message(message, BOT_PERSONALITY, prompt, user_name, SPECIAL_USERS_DATA, query_gemini_api):
        return

    if not prompt:
        await message.reply(random.choice(EMPTY_PROMPT_RESPONSES), mention_author=False)
        return

    async with message.channel.typing():
        answer = await asyncio.to_thread(query_gemini_api, BOT_PERSONALITY, prompt, user_name, "普通")
    await message.reply(answer, mention_author=False)

async def is_reply_to_bot(message: discord.Message) -> bool:
    if message.reference:
        try:
            ref = await message.channel.fetch_message(message.reference.message_id)
            return ref and ref.author == bot.user
        except:
            return False
    return False

@bot.command(name="hi")
async def hi(ctx: commands.Context):
    await ctx.reply("嗨～我是你的小惡魔♡ 才不想理你呢...除非你說我可愛！", mention_author=False)

if __name__ == "__main__":
    try:
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        print(f"Bot 啟動失敗: {e}")