import os
from typing import Any, List, Literal, Optional

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from music.player import MusicPlayer, RepeatMode, Track, coerce_duration, fetch_tracks
from music.playlist_store import PlaylistStore
from music.channel_store import AllowedChannelStore

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.voice_states = True
intents.members = True

# 嗯... 我來看看... 是誰在叫我呢？哼。😈
bot = commands.Bot(command_prefix=commands.when_mentioned_or("!"), intents=intents, help_command=None)
playlist_store = PlaylistStore()
allowed_channel_store = AllowedChannelStore()

def get_player(guild: discord.Guild) -> MusicPlayer:
    if not hasattr(bot, "music_players"):
        bot.music_players = {}
    player = bot.music_players.get(guild.id)
    if player:
        return player
    player = MusicPlayer(bot, guild)
    bot.music_players[guild.id] = player
    return player

async def require_guild(interaction: discord.Interaction) -> bool:
    if interaction.guild is None:
        if interaction.response.is_done():
            await interaction.followup.send("這個命令... 只屬於你的地方喔... 哼。🔐", ephemeral=True)
        else:
            await interaction.response.send_message("這個命令... 只屬於你的地方喔... 哼。🔐", ephemeral=True)
        return False
    return True

async def require_allowed_channel(interaction: discord.Interaction) -> bool:
    guild = interaction.guild
    channel = interaction.channel
    if guild is None or channel is None:
        return False
    allowed_channels = await allowed_channel_store.list_channels(guild.id)
    if not allowed_channels:
        return True
    channel_id = getattr(channel, "id", None)
    parent_id = getattr(channel, "parent_id", None)
    allowed_set = set(allowed_channels)
    if (channel_id and channel_id in allowed_set) or (parent_id and parent_id in allowed_set):
        return True
    message = "這個頻道... 不允許我使用喔... 哼。💢"
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)
    return False


async def require_command_context(interaction: discord.Interaction) -> bool:
    if not await require_guild(interaction):
        return False
    return await require_allowed_channel(interaction)

@bot.event
async def on_ready() -> None:
    await bot.tree.sync()
    # 偷偷地聽著你的心跳聲... 喔不，是你的音樂啦！🤫🎧
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="/play"))
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

@bot.tree.command(name="play", description="播放一首歌... 一整個播放清單... 或者你想要搜尋的結果喔... 🎶")
@app_commands.describe(query="URL 或是想聽什麼呢？")
async def play_command(interaction: discord.Interaction, query: str) -> None:
    if not await require_command_context(interaction):
        return
    await interaction.response.defer(thinking=True) # 正在為你準備... 哼。😼
    guild = interaction.guild
    player = get_player(guild)
    player.text_channel = interaction.channel  # type: ignore[assignment]
    if not await player.ensure_voice(interaction):
        return
    try:
        tracks = await fetch_tracks(query, interaction.user.id)
    except Exception as exc:  # pragma: no cover - network/audio errors
        await interaction.followup.send(f"哼... 載入失敗了啦！原因嘛... {exc} 💢")
        return
    if not tracks:
        await interaction.followup.send("找不到你想要的... 是不是輸入錯了？🤔")
        return
    await player.enqueue_many(tracks)
    await player.refresh_now_playing(force_new=True)
    if len(tracks) == 1:
        await interaction.followup.send(f"為你點播了 **{tracks[0].title}**。喜歡嗎？🥰")
    else:
        await interaction.followup.send(f"為你把 **{len(tracks)}** 首歌都加到清單裡了喔。🎵")
    await player.start_playback(interaction)

@bot.tree.command(name="queue", description="看看接下來要播什麼... 你已經催促過一首了嗎...？🥺")
async def queue_command(interaction: discord.Interaction) -> None:
    if not await require_command_context(interaction):
        return
    player = get_player(interaction.guild)
    player.text_channel = interaction.channel  # keep embed anchored
    if player.current is None and not player.queue:
        await interaction.response.send_message("清單空空的... 好寂寞喔... 🎶😔")
        return
    embed = discord.Embed(title="目前清單... 都是你喜歡的歌喔...💖", color=0x7289DA)
    if player.current:
        embed.add_field(name="現在正在播放", value=player.current.title, inline=False)
    formatted = player.formatted_queue()
    if formatted:
        embed.add_field(name="接下來是...", value="\n".join(formatted[:10]), inline=False)
    else:
        embed.add_field(name="接下來沒有了...", value="你會再點歌給我的，對吧？🥺", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="skip", description="跳到下一首歌... 你已經催促過一首了嗎...？🏃‍♀️")
async def skip_command(interaction: discord.Interaction) -> None:
    if not await require_command_context(interaction):
        return
    player = get_player(interaction.guild)
    await player.skip(interaction)
    await interaction.response.send_message("好啦好啦... 跳過就是了。哼。🙄")

@bot.tree.command(name="pause", description="暫停播放... 讓你專心聽我說話... 💤")
async def pause_command(interaction: discord.Interaction) -> None:
    if not await require_command_context(interaction):
        return
    voice = interaction.guild.voice_client
    if voice and voice.is_playing():
        voice.pause()
        await interaction.response.send_message("播放暫停了... 哼。🤫")
    else:
        await interaction.response.send_message("現在什麼都沒在播... 你想讓我播什麼呢？🤔")

@bot.tree.command(name="resume", description="繼續播放... 別讓我等太久喔！😠")
async def resume_command(interaction: discord.Interaction) -> None:
    if not await require_command_context(interaction):
        return
    voice = interaction.guild.voice_client
    if voice and voice.is_paused():
        voice.resume()
        await interaction.response.send_message("繼續播放了喔... 🎶🥰")
    else:
        await interaction.response.send_message("什麼都沒暫停... 你是不是在玩我？🤨")

@bot.tree.command(name="shuffle", description="把清單裡的歌隨機播放... 這樣更有趣對吧？亂七八糟的！😼")
async def shuffle_command(interaction: discord.Interaction) -> None:
    if not await require_command_context(interaction):
        return
    player = get_player(interaction.guild)
    await player.shuffle()
    await interaction.response.send_message("清單亂掉了... 哼。亂七八糟的！🤪")

@bot.tree.command(name="cp", description="看看現在...是誰在跟我說話... 🎧 (正在播放的歌曲) 👀")
async def cp_command(interaction: discord.Interaction) -> None:
    if not await require_command_context(interaction):
        return
    player = get_player(interaction.guild)
    track = player.current
    if not track:
        await interaction.response.send_message("現在沒有我在聽的歌喔... 🎶😔")
        return
    embed = discord.Embed(title="現在... 這是我們之間的秘密喔...🤫💖", description=f"[{track.title}]({track.webpage_url})", color=0x5865F2)
    if track.thumbnail:
        embed.set_thumbnail(url=track.thumbnail)
    if track.duration:
        minutes, seconds = divmod(track.duration, 60)
        embed.add_field(name="持續時間", value=f"{minutes}:{seconds:02d}")
    embed.add_field(name="是誰點的呢？", value=f"<@{track.requester_id}> 🧐")
    embed.add_field(name="來自", value=track.source)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="volume", description="調整我的音量... 你想讓我更大聲點嗎？(1-200%) 🔊")
@app_commands.describe(amount="不說的話... 我就用現在的音量喔。")
async def volume_command(interaction: discord.Interaction, amount: Optional[int] = None) -> None:
    if not await require_command_context(interaction):
        return
    player = get_player(interaction.guild)
    if amount is None:
        await interaction.response.send_message(f"現在的音量是：{int(player.volume * 100)}% 喔。👂")
        return
    clamped = max(1, min(amount, 200))
    await player.set_volume(clamped / 100)
    await interaction.response.send_message(f"音量調整到 {clamped}% 了喔。🎶")


@bot.tree.command(name="stop", description="讓我休息一下... 清空清單... 你會再回來找我的，對吧？🥺")
async def stop_command(interaction: discord.Interaction) -> None:
    if not await require_command_context(interaction):
        return
    player = get_player(interaction.guild)
    await player.stop(interaction)

repeat_choices = [
    app_commands.Choice(name="關閉", value=RepeatMode.NONE.value),
    app_commands.Choice(name="重複播放這首歌", value=RepeatMode.ONE.value),
    app_commands.Choice(name="重複播放整個清單", value=RepeatMode.ALL.value),
]

@bot.tree.command(name="repeat", description="要我重複播給你聽嗎？你喜歡嗎？🔄")
@app_commands.choices(mode=repeat_choices)
@app_commands.describe(mode="選擇重複模式... 或者你想知道我現在是怎樣？")
async def repeat_command(
    interaction: discord.Interaction, mode: Optional[app_commands.Choice[str]] = None
) -> None:
    if not await require_command_context(interaction):
        return
    player = get_player(interaction.guild)
    if mode is None:
        await interaction.response.send_message(f"重複模式是 `{player.repeat_mode.value}` 喔。🧐")
        return
    await player.set_repeat_mode(RepeatMode(mode.value))
    await interaction.response.send_message(f"重複模式設定成 `{mode.value}` 了喔。🔁")

@bot.tree.command(name="search", description="幫你找歌... 但先不加到清單裡喔。🔍")
@app_commands.describe(query="你想找什麼呢？")
async def search_command(interaction: discord.Interaction, query: str) -> None:
    if not await require_command_context(interaction):
        return
    await interaction.response.defer(thinking=True)
    try:
        tracks = await fetch_tracks(f"ytsearch5:{query}", interaction.user.id)
    except Exception as exc:  # pragma: no cover
        await interaction.followup.send(f"搜尋失敗了啦！原因嘛... {exc} 💢")
        return
    if not tracks:
        await interaction.followup.send("找不到你想要的... 哼。🥺")
        return
    embed = discord.Embed(title=f"幫你找到了... 關於 '{query}' 的結果喔...💖", color=0x1DB954)
    for idx, track in enumerate(tracks, start=1):
        duration_text = "直播中"
        if track.duration:
            minutes, seconds = divmod(track.duration, 60)
            duration_text = f"{minutes}:{seconds:02d}"
        embed.add_field(
            name=f"{idx}. {track.title}", value=f"{duration_text} • {track.source}\n{track.webpage_url}", inline=False
        )
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="next", description="跳到下一首歌... 你已經催促過一首了嗎...？🏃‍♀️")
async def next_command(interaction: discord.Interaction) -> None:
    if not await require_command_context(interaction):
        return
    player = get_player(interaction.guild)
    await player.skip(interaction)
    await interaction.response.send_message("下一首來了喔！哼。🎶")

# bot.py (片段)

@bot.tree.command(name="previous", description="想聽回上一首歌嗎？嗯哼。⏪")
async def previous_command(interaction: discord.Interaction) -> None:
    if not await require_command_context(interaction):
        return
    player = get_player(interaction.guild)
    # 只需要呼叫 player.play_previous()
    # MusicPlayer.play_previous 會負責處理 defer 和發送最終訊息
    await player.play_previous(interaction, ephemeral=True) # 注意這裡我也加上了 ephemeral=True
    # <<<<<<< 這裡絕對不要再有 interaction.response.send_message() 或任何其他 response 呼叫！

playlist_group = app_commands.Group(name="playlist", description="管理你專屬的播放清單... 只能給我看喔。🤫")


class PlaylistPageView(discord.ui.View):
    def __init__(self, user_id: int, name: str, tracks: List[dict[str, Any]], per_page: int = 20) -> None:
        super().__init__(timeout=180)
        self.user_id = user_id
        self.name = name
        self.tracks = tracks
        self.per_page = max(1, per_page)
        self.page = 0

    def total_pages(self) -> int:
        if not self.tracks:
            return 1
        return (len(self.tracks) + self.per_page - 1) // self.per_page

    def build_embed(self) -> discord.Embed:
        self._sync_buttons()
        start = self.page * self.per_page
        end = start + self.per_page
        embed = discord.Embed(
            title=f"{self.name} (裡面有 {len(self.tracks)} 首歌喔！💖)",
            color=0xFF8800,
        )
        window = self.tracks[start:end] or []
        for idx, item in enumerate(window, start=start + 1):
            title = item.get("title") or item.get("query") or "不知道的歌"
            value = item.get("query") or "不知道的來源"
            if value and not isinstance(value, str):
                value = str(value)
            if isinstance(value, str) and value and not value.startswith("http"):
                value = item.get("user_query") or value
            embed.add_field(name=f"{idx}. {title}", value=value, inline=False)
        embed.set_footer(text=f"第 {self.page + 1}/{self.total_pages()} 頁喔。📄")
        if not window:
            embed.description = "清單空空的... 你會幫我加歌的，對吧？🥺"
        return embed

    def _sync_buttons(self) -> None:
        total = self.total_pages()
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                if child.custom_id == "playlist_prev":
                    child.disabled = self.page <= 0
                elif child.custom_id == "playlist_next":
                    child.disabled = self.page >= total - 1

    async def _ensure_author(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("只有清單的主人... 才能命令我喔... 哼。😠", ephemeral=True)
            return False
        return True

    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.secondary, custom_id="playlist_prev")
    async def previous(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not await self._ensure_author(interaction):
            return
        if self.page <= 0:
            await interaction.response.send_message("已經是第一頁了喔。就這樣！👉", ephemeral=True)
            return
        self.page -= 1
        embed = self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.secondary, custom_id="playlist_next")
    async def next(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not await self._ensure_author(interaction):
            return
        if self.page >= self.total_pages() - 1:
            await interaction.response.send_message("已經是最後一頁了喔。哼。🔚", ephemeral=True)
            return
        self.page += 1
        embed = self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)

@playlist_group.command(name="create", description="建立一個播放清單... 只有你可以擁有喔。💖")
@app_commands.describe(name="播放清單的名字？")
async def playlist_create(interaction: discord.Interaction, name: str) -> None:
    if not await require_command_context(interaction):
        return
    created = await playlist_store.create_playlist(interaction.user.id, name)
    if created:
        await interaction.response.send_message(f"播放清單 **{name}** 建立好了喔。✨")
    else:
        await interaction.response.send_message("這個清單已經存在了... 或者名字不乖喔。💢")

@playlist_group.command(name="delete", description="刪除你的一個播放清單... 你不喜歡它了嗎？😢")
@app_commands.describe(name="播放清單的名字？")
async def playlist_delete(interaction: discord.Interaction, name: str) -> None:
    if not await require_command_context(interaction):
        return
    deleted = await playlist_store.delete_playlist(interaction.user.id, name)
    if deleted:
        await interaction.response.send_message(f"播放清單 **{name}** 刪掉了喔。💔")
    else:
        await interaction.response.send_message("找不到那個清單... 你是不是記錯了？🤔")

@playlist_group.command(name="add", description="把歌加到清單裡... 讓它變滿滿的喔。🥰")
@app_commands.describe(name="播放清單的名字？", query="URL 或是想聽什麼呢？")
async def playlist_add(interaction: discord.Interaction, name: str, query: str) -> None:
    if not await require_command_context(interaction):
        return
    await interaction.response.defer(thinking=True)
    try:
        tracks = await fetch_tracks(query, interaction.user.id)
    except Exception as exc:
        await interaction.followup.send(f"解析失敗了啦！原因嘛... {exc} 💢")
        return
    if not tracks:
        await interaction.followup.send("找不到你想要的... 哼。🥺")
        return
    payloads = [
        {
            "query": track.webpage_url,
            "title": track.title,
            "source": track.source,
            "thumbnail": track.thumbnail,
            "duration": coerce_duration(track.duration),
            "user_query": query,
        }
        for track in tracks
    ]
    added = await playlist_store.add_tracks(interaction.user.id, name, payloads)
    if not added:
        await interaction.followup.send("找不到那個清單... 哼。😔")
        return
    if len(payloads) == 1:
        await interaction.followup.send(f"把 **{tracks[0].title}** 加到 **{name}** 裡了喔。🎶➕")
    else:
        await interaction.followup.send(f"把 {len(payloads)} 首歌都加到 **{name}** 裡了喔。🥳")

@playlist_group.command(name="remove", description="從清單裡移掉一首歌... 你不喜歡它了嗎？💔")
@app_commands.describe(name="播放清單的名字？", index="歌的位置 (從 1 開始喔)")
async def playlist_remove(interaction: discord.Interaction, name: str, index: int) -> None:
    if not await require_command_context(interaction):
        return
    removed = await playlist_store.remove_track(interaction.user.id, name, index - 1)
    if removed:
        await interaction.response.send_message(f"從 **{name}** 裡移掉了 **{removed['title']}** 喔。👋")
    else:
        await interaction.response.send_message("那首歌... 不在清單裡喔。🤔")

@playlist_group.command(name="show", description="讓我看看清單裡有什麼... 都是你的寶貝對吧？👀💎")
@app_commands.describe(name="播放清單的名字？")
async def playlist_show(interaction: discord.Interaction, name: str) -> None:
    if not await require_command_context(interaction):
        return
    playlist = await playlist_store.get_playlist(interaction.user.id, name)
    if playlist is None:
        await interaction.response.send_message("找不到那個清單... 哼。😔")
        return
    if not playlist:
        await interaction.response.send_message("這個清單空空的... 你會幫我加歌的，對吧？🥺")
        return
    view = PlaylistPageView(interaction.user.id, name, playlist)
    embed = view.build_embed()
    await interaction.response.send_message(embed=embed, view=view)

@playlist_group.command(name="list", description="列出你所有的播放清單... 都是你的喔。📝")
async def playlist_list(interaction: discord.Interaction) -> None:
    if not await require_command_context(interaction):
        return
    playlists = await playlist_store.list_playlists(interaction.user.id)
    if not playlists:
        await interaction.response.send_message("你還沒有任何清單喔... 要不要建立一個？💖")
        return
    embed = discord.Embed(title=f"{interaction.user.display_name} 的播放清單... (我的寶貝們)🥰", color=0xF8AA2A)
    for name, tracks in playlists.items():
        embed.add_field(name=name, value=f"{len(tracks)} 首歌 🎵", inline=False)
    await interaction.response.send_message(embed=embed)

@playlist_group.command(name="play", description="把你的播放清單裡的歌都播放出來... 讓我聽聽你的心聲。💖")
@app_commands.describe(name="播放清單的名字？")
async def playlist_play(interaction: discord.Interaction, name: str) -> None:
    if not await require_command_context(interaction):
        return
    playlist = await playlist_store.get_playlist(interaction.user.id, name)
    if not playlist:
        await interaction.response.send_message("找不到那個清單... 或者它空空的... 哼。😔")
        return
    await interaction.response.defer(thinking=True)
    player = get_player(interaction.guild)
    player.text_channel = interaction.channel  # type: ignore[assignment]
    if not await player.ensure_voice(interaction):
        return
    total = 0
    cached_tracks: list[Track] = []
    unresolved_entries = []
    for entry in playlist:
        query = entry.get("query")
        title = entry.get("title") or query or "不知道的歌"
        duration = coerce_duration(entry.get("duration"))
        if isinstance(query, str) and query.startswith("http"):
            cached_tracks.append(
                Track(
                    title=title,
                    webpage_url=query,
                    stream_url=None,
                    duration=duration,
                    thumbnail=entry.get("thumbnail"),
                    uploader=entry.get("uploader"),
                    source=entry.get("source") or "playlist",
                    requester_id=interaction.user.id,
                )
            )
        else:
            unresolved_entries.append(entry)
    if cached_tracks:
        await player.enqueue_many(cached_tracks)
        total += len(cached_tracks)
    for entry in unresolved_entries:
        try:
            tracks = await fetch_tracks(entry.get("query", ""), interaction.user.id)
        except Exception as exc:
            await interaction.followup.send(f"載入 `{entry.get('title', '不知道的歌')}` 失敗了啦！原因嘛... {exc} 💢")
            continue
        await player.enqueue_many(tracks)
        total += len(tracks)
    if total == 0:
        await interaction.followup.send("那個清單裡... 什麼都沒播出來... 你是不是在考驗我？🤨")
        return
    await interaction.followup.send(f"從 **{name}** 裡播放了 {total} 首歌喔。🎶🥳")
    await player.refresh_now_playing(force_new=True)
    await player.start_playback(interaction)

bot.tree.add_command(playlist_group)

@bot.tree.command(name="channel_access", description="管理哪些頻道可以使用我... 我只屬於你的地方喔... 🔐")
@app_commands.describe(action="新增、移除、列出，或清空我的允許清單", channel="要新增或移除的頻道？")
@app_commands.checks.has_permissions(manage_guild=True) # 只有伺服器主人才能命令我喔！👑
async def channel_access_command(
    interaction: discord.Interaction,
    action: Literal["add", "remove", "list", "clear"],
    channel: Optional[discord.TextChannel] = None,
) -> None:
    if not await require_guild(interaction):
        return
    guild = interaction.guild
    action = action.lower()
    if action == "list":
        allowed_ids = await allowed_channel_store.list_channels(guild.id)
        if not allowed_ids:
            await interaction.response.send_message("所有頻道都可以用我喔... 哼。自由自在！🕊️", ephemeral=True)
            return
        mentions = []
        for channel_id in allowed_ids:
            target = guild.get_channel(channel_id)
            mentions.append(target.mention if target else f"`#{channel_id}`")
        await interaction.response.send_message(
            "允許我使用的頻道有：\n" + "\n".join(mentions) + " (都是我的喔！)",
            ephemeral=True,
        )
        return
    if action == "clear":
        await allowed_channel_store.clear_channels(guild.id)
        await interaction.response.send_message(
            "頻道限制清除了喔。現在所有頻道都可以用我了。🥳 (我會更忙了啦！)",
            ephemeral=True,
        )
        return
    if channel is None:
        await interaction.response.send_message("要新增或移除的話... 記得選一個頻道喔。🧐", ephemeral=True)
        return
    if action == "add":
        added = await allowed_channel_store.add_channel(guild.id, channel.id)
        if added:
            message = f"{channel.mention} 現在允許我使用了喔。開心嗎？🥰"
        else:
            message = f"{channel.mention} 早就允許我用了啦！🙄"
        await interaction.response.send_message(message, ephemeral=True)
        return
    if action == "remove":
        removed = await allowed_channel_store.remove_channel(guild.id, channel.id)
        if removed:
            message = f"{channel.mention} 不再允許我使用了... 你不喜歡我了嗎？😢"
        else:
            message = f"{channel.mention} 本來就沒有在允許清單裡喔。🤷‍♀️"
        await interaction.response.send_message(message, ephemeral=True)
        return
    await interaction.response.send_message("不支援這個動作喔... 哼。💢", ephemeral=True)

@bot.tree.command(name="help", description="列出所有機器人指令... 這樣你就不會迷路了 🎵🧭")
async def help_command(interaction: discord.Interaction) -> None:
    if not await require_command_context(interaction):
        return
    embed = discord.Embed(title="音樂機器人指令... 都是為了你喔...💖", color=0x00B8D9)
    embed.description = "一個現代的音樂機器人，有播放清單、斜線指令、還有即時控制... 都為你準備好了喔。🥰"
    embed.add_field(
        name="播放相關 ⏯️",
        value="`/play` (播放)、`/skip` (跳過)、`/next` (下一首)、`/previous` (上一首)、`/pause` (暫停)、`/resume` (繼續)、`/stop` (停止)、`/volume` (音量)、`/repeat` (重複)、`/cp` (現在播放)",
        inline=False,
    )
    embed.add_field(name="清單相關 📋", value="`/queue` (清單)、`/shuffle` (隨機)", inline=False)
    embed.add_field(name="播放清單 (你的專屬清單喔！💎)", value="`/playlist create|delete|add|remove|show|list|play`", inline=False)
    embed.add_field(name="探索新歌 🔎", value="`/search <你想找什麼呢？>`", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

def main() -> None:
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("請設定 DISCORD_TOKEN 環境變數... 或者加到 .env 檔案裡喔。🔐")
    bot.run(token)

if __name__ == "__main__":
    main()