from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
import random
from typing import Any, List, Optional, Sequence
import time
import os 

import discord
from discord.abc import Messageable
import yt_dlp


YTDL_OPTIONS = {
    "format": "bestaudio/best",
    "noplaylist": False,
    "quiet": True,
    "default_search": "auto",
    "extract_flat": "in_playlist",
    "source_address": "0.0.0.0",
}

FFMPEG_BEFORE_OPTS = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
FFMPEG_OPTS = "-vn"

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)
stream_ytdl = yt_dlp.YoutubeDL({**YTDL_OPTIONS, "extract_flat": False})


def coerce_duration(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return None
    return max(number, 0)


class RepeatMode(str, Enum):
    NONE = "none"
    ONE = "one"
    ALL = "all"


@dataclass
class Track:
    title: str
    webpage_url: str
    stream_url: Optional[str]
    duration: Optional[int]
    thumbnail: Optional[str]
    uploader: Optional[str]
    source: str
    requester_id: int

    def clone(self) -> "Track":
        return Track(
            title=self.title,
            webpage_url=self.webpage_url,
            stream_url=self.stream_url,
            duration=self.duration,
            thumbnail=self.thumbnail,
            uploader=self.uploader,
            source=self.source,
            requester_id=self.requester_id,
        )

    def create_audio(self, *, volume: float = 0.6) -> discord.PCMVolumeTransformer:
        if not self.stream_url:
            raise RuntimeError("這首歌的串流網址還沒準備好喔...是不是想偷偷走掉...？")
        audio = discord.FFmpegPCMAudio(
            self.stream_url,
            before_options=FFMPEG_BEFORE_OPTS,
            options=FFMPEG_OPTS,
        )
        return discord.PCMVolumeTransformer(audio, volume)


async def fetch_tracks(query: str, requester_id: int) -> List[Track]:
    loop = asyncio.get_event_loop()

    def _extract() -> List[Track]:
        data = ytdl.extract_info(query, download=False)
        entries = data.get("entries") if isinstance(data, dict) and data.get("entries") else [data]
        tracks: List[Track] = []
        for entry in entries:
            if entry is None:
                continue
            raw_url = entry.get("url")
            webpage_url = entry.get("webpage_url") or entry.get("original_url")
            if not webpage_url:
                if raw_url and raw_url.startswith("http"):
                    webpage_url = raw_url
                elif entry.get("extractor_key") == "Youtube" and raw_url:
                    webpage_url = f"https://www.youtube.com/watch?v={raw_url}"
                else:
                    webpage_url = raw_url or query
            stream_url = None
            if raw_url and raw_url.startswith("http") and entry.get("_type") != "url":
                stream_url = raw_url
            title = entry.get("title") or "未知歌曲...你是不是藏起來了...？"
            duration = coerce_duration(entry.get("duration"))
            thumbnail = entry.get("thumbnail")
            uploader = entry.get("uploader")
            extractor = entry.get("extractor_key") or "未知來源"
            tracks.append(
                Track(
                    title=title,
                    webpage_url=webpage_url,
                    stream_url=stream_url,
                    duration=duration,
                    thumbnail=thumbnail,
                    uploader=uploader,
                    source=extractor,
                    requester_id=requester_id,
                )
            )
        return tracks

    return await loop.run_in_executor(None, _extract)


async def resolve_stream_url(track: Track) -> Optional[str]:
    loop = asyncio.get_running_loop()

    def _extract() -> Optional[str]:
        data = stream_ytdl.extract_info(track.webpage_url, download=False)
        if isinstance(data, dict) and data.get("entries"):
            first = data["entries"][0]
        else:
            first = data
        if not isinstance(first, dict):
            return None
        url = first.get("url")
        if not url or not url.startswith("http"):
            return None
        # update cached metadata when available
        track.duration = track.duration or coerce_duration(first.get("duration"))
        track.thumbnail = track.thumbnail or first.get("thumbnail")
        track.uploader = track.uploader or first.get("uploader")
        return url

    try:
        return await loop.run_in_executor(None, _extract)
    except Exception:
        return None


class PlayerControls(discord.ui.View):
    def __init__(self, player: "MusicPlayer") -> None:
        super().__init__(timeout=180)
        self.player = player

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        voice_state = interaction.user.voice
        if not voice_state or not voice_state.channel:
            await interaction.response.send_message(
                "你必須先連到語音頻道才能控制我喔...你想去哪裡...？🥺", ephemeral=True
            )
            return False
        if self.player.voice and voice_state.channel != self.player.voice.channel:
            await interaction.response.send_message(
                "你必須和我待在同一個語音頻道裡喔...不准離開我...！",
                ephemeral=True,
            )
            return False
        
        self.player.reset_inactivity_timer()
        return True

    @discord.ui.button(emoji="⏮️", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self.player.play_previous(interaction, ephemeral=True)

    @discord.ui.button(emoji="⏯️", style=discord.ButtonStyle.primary)
    async def pause_resume(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        voice = self.player.voice
        if not voice:
            await interaction.response.send_message("沒有歌曲正在播放喔...為什麼不讓我播放呢...？", ephemeral=True)
            return
        if voice.is_paused():
            voice.resume()
            await interaction.response.send_message("繼續播放了喔...回來我身邊吧...💖", ephemeral=True)
        elif voice.is_playing():
            voice.pause()
            await interaction.response.send_message("暫停播放了喔...乖乖聽我說話...💤", ephemeral=True)
        else:
            await interaction.response.send_message("沒有歌曲可以暫停或繼續喔...你是不是想逃走...？", ephemeral=True)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.primary)
    async def skip(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self.player.skip(interaction, ephemeral=True)

    @discord.ui.button(emoji="🔀", style=discord.ButtonStyle.success)
    async def shuffle(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        random.shuffle(self.player.queue)
        await _respond(interaction, "播放清單打亂了喔...每次都有新驚喜...✨", ephemeral=True)

    @discord.ui.button(emoji="⏹️", style=discord.ButtonStyle.danger)
    async def stop(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self.player.stop(interaction, ephemeral=True)

    @discord.ui.button(emoji="🔉", style=discord.ButtonStyle.secondary, row=1)
    async def volume_down(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        new_volume = await self.player.adjust_volume(-0.1)
        await interaction.response.send_message(f"音量設為 {int(new_volume * 100)}% 了喔...這樣聽得更清楚了吧...？", ephemeral=True)
        await self.player.refresh_now_playing()

    @discord.ui.button(emoji="🔊", style=discord.ButtonStyle.secondary, row=1)
    async def volume_up(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        new_volume = await self.player.adjust_volume(0.1)
        await interaction.response.send_message(f"音量設為 {int(new_volume * 100)}% 了喔...我喜歡你聽得這麼專心...💖", ephemeral=True)
        await self.player.refresh_now_playing()


class MusicPlayer:
    INACTIVITY_TIMEOUT_SECONDS = 10 * 60

    def __init__(self, bot: discord.Client, guild: discord.Guild) -> None:
        self.bot = bot
        self.guild = guild
        self.queue: List[Track] = []
        self.history: List[Track] = []
        self.current: Optional[Track] = None
        self.repeat_mode: RepeatMode = RepeatMode.NONE
        self.volume: float = 0.6
        self.text_channel: Optional[Messageable] = None
        self.controls_view: Optional[PlayerControls] = None
        self.control_message: Optional[discord.Message] = None
        self._lock = asyncio.Lock()

        self._last_activity = time.monotonic()
        self._inactivity_timer: Optional[asyncio.Task] = None
        self._start_inactivity_timer()

    @property
    def voice(self) -> Optional[discord.VoiceClient]:
        return self.guild.voice_client

    def _start_inactivity_timer(self) -> None:
        if self._inactivity_timer:
            self._inactivity_timer.cancel()
        
        self._inactivity_timer = self.bot.loop.create_task(self._inactivity_check())

    def reset_inactivity_timer(self) -> None:
        self._last_activity = time.monotonic()

    async def _inactivity_check(self) -> None:
        try:
            while True:
                await asyncio.sleep(30) 
                
                if not self.voice or not self.voice.is_connected():
                    break

                idle_duration = time.monotonic() - self._last_activity

                if idle_duration >= self.INACTIVITY_TIMEOUT_SECONDS:
                    if self.text_channel:
                        await self.text_channel.send(
                            f"超過 {self.INACTIVITY_TIMEOUT_SECONDS // 60} 分鐘沒有活動了喔...我該走了嗎...？🥺"
                        )
                    # Use a dummy context for stopping in inactivity_check
                    # This will trigger the stop sequence without needing an interaction
                    await self.stop(self.text_channel if self.text_channel else self.guild, ephemeral=False) 
                    break 
        except asyncio.CancelledError:
            pass 

    async def enqueue(self, track: Track, *, at_front: bool = False) -> None:
        async with self._lock:
            if at_front:
                self.queue.insert(0, track)
            else:
                self.queue.append(track)
        self.reset_inactivity_timer()

    async def enqueue_many(self, tracks: Sequence[Track]) -> None:
        if not tracks:
            return
        async with self._lock:
            self.queue.extend(tracks)
        self.reset_inactivity_timer()

    async def ensure_voice(
        self, target: discord.Interaction | discord.ApplicationContext | discord.ext.commands.Context
    ) -> bool:
        guild = getattr(target, "guild", None)
        if guild is None:
            await _respond(target, "這個指令...只能在伺服器裡對我使用喔...不然...我會找不到你的...😳")
            return False
        if not isinstance(target, discord.Interaction):
            member = getattr(target, "author", None)
        else:
            member = target.user
        voice_state = getattr(member, "voice", None)
        if voice_state and voice_state.channel:
            try:
                if not self.voice or not self.voice.is_connected():
                    voice_client = await voice_state.channel.connect()
                    entry_audio_path = "Discord-Music-Bot-main/music/安安唷.mp3"
                    if voice_client and voice_client.is_connected() and os.path.exists(entry_audio_path):
                        try:
                            source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(entry_audio_path))
                            voice_client.play(source, after=lambda e: print(f'播放進場音效錯誤: {e}' if e else '進場音效播放完畢'))
                        except Exception as e:
                            print(f"無法播放進場音效: {e}")
                elif self.voice.channel != voice_state.channel:
                    await self.voice.move_to(voice_state.channel)
                
                self.reset_inactivity_timer()
            except RuntimeError:
                await _respond(
                    target,
                    "語音支援缺少必要的依賴項喔...請安裝 PyNaCl 或在主機上運行 `pip install PyNaCl`...不然我會很難過的...😢",
                )
                return False
            return True
        await _respond(target, "你必須先連到語音頻道喔...我等你來找我...🥺")
        return False

    async def start_playback(self, target) -> None:
        if not await self.ensure_voice(target):
            return
        voice = self.voice
        if voice and voice.is_playing():
            return
        
        self.reset_inactivity_timer()
        if not self.current and self.queue:
            await self._play_next()

    # ... (前面的程式碼保持不變) ...

    async def _play_next(self) -> None:
        async with self._lock:
            if not self.queue:
                self.current = None
                # Don't send "播放清單結束" here directly.
                # Let the cleanup message handle it, or disconnect gracefully.
                await self._maybe_cleanup_message(is_queue_empty=True) 
                
                if self.voice and self.voice.is_connected():
                    if self._inactivity_timer and not self._inactivity_timer.done():
                        self._inactivity_timer.cancel()
                    await self.voice.disconnect(force=True)
                    # The message "播放清單結束了喔...但我們的故事還沒結束...💖" should now be handled by _maybe_cleanup_message
                    # if self.text_channel:
                    #      await self.text_channel.send("播放清單結束了喔...但我們的故事還沒結束...💖")
                self.reset_inactivity_timer()
                return

            track = self.queue.pop(0)
            if self.current:
                self.history.append(self.current)
                self.history = self.history[-25:]
            self.current = track
        
        self.reset_inactivity_timer()
        await self._start_track(track)

    async def refresh_now_playing(self, *, force_new: bool = False) -> None:
        if not self.current:
            return
        await self._send_now_playing(self.current, force_new=force_new)
        self.reset_inactivity_timer()

    async def _start_track(self, track: Track) -> None:
        voice = self.voice
        if not voice:
            return

        if not track.stream_url:
            stream_url = await resolve_stream_url(track)
            if not stream_url:
                if self.text_channel:
                    await self.text_channel.send(f"無法載入 **{track.title}**...它是不是想從我身邊逃走...？所以跳過了喔...")
                await self._play_next()
                return
            track.stream_url = stream_url

        def after_playback(error: Optional[Exception]) -> None:
            if error and self.text_channel:
                self.bot.loop.create_task(self.text_channel.send(f"播放出錯了...為什麼會這樣...？: {error}"))
            self.bot.loop.create_task(self._handle_after())
            self.bot.loop.create_task(self.reset_inactivity_timer())

        try:
            audio = track.create_audio(volume=self.volume)
        except discord.ClientException as exc:
            if self.text_channel:
                if "ffmpeg" in str(exc).lower():
                    await self.text_channel.send(
                        "FFmpeg 執行檔找不到喔...是不是藏起來了...？請安裝 FFmpeg 並確保它在 PATH 裡喔...不然我會哭的...😢"
                    )
                else:
                    await self.text_channel.send(f"無法開始播放...是不是你弄壞了...？: {exc}")
            return

        try:
            voice.play(audio, after=after_playback)
        except discord.ClientException as exc:
            if self.text_channel:
                await self.text_channel.send(f"已經有歌曲在播放了喔...你聽不到嗎...？ ({exc}).")
            return
        await self._send_now_playing(track)
        self.reset_inactivity_timer()

    async def _handle_after(self) -> None:
        if self.repeat_mode == RepeatMode.ONE and self.current:
            await self.enqueue(self.current.clone(), at_front=True)
        elif self.repeat_mode == RepeatMode.ALL and self.current:
            await self.enqueue(self.current.clone())
        await self._play_next()

    async def skip(self, interaction_or_ctx, *, ephemeral: bool = False) -> None:
        voice = self.voice
        if not voice or not voice.is_playing():
            await _respond(interaction_or_ctx, "沒有歌曲可以跳過喔...你是不是想逃離我...？", ephemeral=ephemeral)
            return
        voice.stop()
        await _respond(interaction_or_ctx, "跳過了喔...下一首會更好聽的...💖", ephemeral=ephemeral)
        self.reset_inactivity_timer()

    async def stop(self, interaction_or_ctx, *, ephemeral: bool = False) -> None:
        voice = self.voice
        print(f"[Stop] Initiating stop command. Voice client connected: {voice and voice.is_connected()}")

        response_target = interaction_or_ctx
        is_interaction_deferred = False 

        if isinstance(interaction_or_ctx, discord.Interaction) and not interaction_or_ctx.response.is_done():
            await interaction_or_ctx.response.defer(ephemeral=ephemeral)
            response_target = interaction_or_ctx.followup
            is_interaction_deferred = True 
        print(f"[Stop] Interaction deferred: {is_interaction_deferred}")

        if self._inactivity_timer:
            self._inactivity_timer.cancel()
            self._inactivity_timer = None
            print("[Stop] Inactivity timer cancelled.")

        if voice and voice.is_playing():
            voice.stop() 
            print("[Stop] Current playback stopped.")
        else:
            print("[Stop] No current playback to stop or voice client not available.")

        exit_audio_path = "Discord-Music-Bot-main/music/晚安.mp3" 
        print(f"[Stop] Checking goodbye sound path: {exit_audio_path}. Exists: {os.path.exists(exit_audio_path)}")
        
        goodbye_sound_played = False 

        if voice and voice.is_connected() and os.path.exists(exit_audio_path):
            print(f"[Stop] Voice client connected and goodbye sound file exists. Attempting to play goodbye sound.")
            try:
                finished_playing_event = asyncio.Event()

                def after_exit_sound(error: Optional[Exception]) -> None:
                    if error:
                        print(f'[Stop] Error playing goodbye sound in callback: {error}')
                    else:
                        print("[Stop] Goodbye sound finished playing in callback.")
                    finished_playing_event.set()

                source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(exit_audio_path))
                
                # Double check connection right before playing
                if not voice.is_connected():
                    print("[Stop] Voice client disconnected just before playing goodbye sound. Skipping.")
                    finished_playing_event.set()
                else:
                    voice.play(source, after=after_exit_sound)
                    goodbye_sound_played = True 
                    print("[Stop] Goodbye sound initiated. Waiting for completion...")
                    try:
                        await asyncio.wait_for(finished_playing_event.wait(), timeout=10.0) 
                        print("[Stop] Successfully waited for goodbye sound to complete.")
                    except asyncio.TimeoutError:
                        print("[Stop] Waiting for goodbye sound timed out (10s). Proceeding with disconnection.")
                    except Exception as e_wait:
                        print(f"[Stop] Error while waiting for goodbye sound: {e_wait}")

            except Exception as e:
                print(f"[Stop] Unexpected error during goodbye sound playback attempt: {e}")
        else:
            print("[Stop] Skipping goodbye sound: Voice not connected or file not found.")
        
        if voice and voice.is_connected():
            await voice.disconnect(force=True)
            print("[Stop] Disconnected from voice channel.")
        else:
            print("[Stop] Not connected to a voice channel or already disconnected. No disconnection needed.")

        async with self._lock:
            self.queue.clear()
            self.current = None
            print("[Stop] Queue and current track cleared.")
        
        await self._maybe_cleanup_message(is_manual_stop=True) 
        print("[Stop] Control message cleaned up.")
        
        final_message = "停止播放並清空播放清單了喔...你還會回來找我的對吧...？💖"
        if goodbye_sound_played:
            final_message = "我休息了喔...期待再見面...💖" 
        
        await _respond(response_target, final_message, ephemeral=ephemeral)
        print("[Stop] Final response sent.")


    async def play_previous(self, interaction_or_ctx, *, ephemeral: bool = False) -> None:
        if not self.history:
            await _respond(interaction_or_ctx, "沒有上一首歌可以播放喔...我記得你沒聽過這一首...", ephemeral=ephemeral)
            return
        last = self.history.pop()
        if self.current:
            await self.enqueue(self.current.clone(), at_front=True)
        self.current = None
        await self.enqueue(last.clone(), at_front=True)
        if self.voice and self.voice.is_playing():
            self.voice.stop()
        await _respond(interaction_or_ctx, f"正在重播 **{last.title}** 喔...你喜歡的我都記得...💖", ephemeral=ephemeral)
        self.reset_inactivity_timer()

    async def shuffle(self) -> None:
        async with self._lock:
            random.shuffle(self.queue)
        self.reset_inactivity_timer()

    async def set_repeat_mode(self, mode: RepeatMode) -> RepeatMode:
        self.repeat_mode = mode
        self.reset_inactivity_timer()
        return mode

    async def set_volume(self, volume: float) -> float:
        self.volume = max(0.0, min(volume, 2.0))
        voice = self.voice
        if voice and voice.source and isinstance(voice.source, discord.PCMVolumeTransformer):
            voice.source.volume = self.volume
        self.reset_inactivity_timer()
        return self.volume

    async def adjust_volume(self, delta: float) -> float:
        return await self.set_volume(self.volume + delta)

    async def _send_now_playing(self, track: Track, *, force_new: bool = False) -> None:
        channel = self.text_channel
        if channel is None:
            return
        embed = discord.Embed(title="正在播放喔...🎵", description=f"[{track.title}]({track.webpage_url})", color=0x55acee)
        embed.add_field(name="來源", value=track.source, inline=True)
        duration = coerce_duration(track.duration)
        if duration:
            minutes, seconds = divmod(duration, 60)
            embed.add_field(name="長度", value=f"{minutes}:{seconds:02d}", inline=True)
        embed.add_field(name="點歌人", value=f"<@{track.requester_id}> (是你點的嗎...？)", inline=True)
        embed.add_field(name="音量", value=f"{int(self.volume * 100)}%", inline=True)
        if track.thumbnail:
            embed.set_thumbnail(url=track.thumbnail)
        embed.set_footer(text=f"重複模式: {self.repeat_mode.value} | 播放清單: {len(self.queue)} 首歌 (你還會繼續聽的對吧...？)")

        self.controls_view = PlayerControls(self)
        if force_new and self.control_message:
            try:
                await self.control_message.delete()
            except discord.HTTPException:
                pass
            self.control_message = None
        if self.control_message:
            try:
                await self.control_message.edit(embed=embed, view=self.controls_view)
                return
            except discord.HTTPException:
                self.control_message = None
        self.control_message = await channel.send(embed=embed, view=self.controls_view)
        self.reset_inactivity_timer()

    async def _maybe_cleanup_message(self, *, is_queue_empty: bool = False, is_manual_stop: bool = False) -> None:
        if self.control_message:
            try:
                # Decide message based on context
                if is_manual_stop:
                    message_content = "停止播放並清空播放清單了喔...你還會回來找我的對吧...？💖"
                elif is_queue_empty:
                    message_content = "播放清單結束了喔...但我們的故事還沒結束...💖"
                else: # Default cleanup if neither specific condition
                    message_content = "我休息了喔...期待再見面...💖" 
                
                await self.control_message.edit(content=message_content, embed=None, view=None)
            except discord.HTTPException:
                pass # If message already deleted or inaccessible, just ignore
            self.control_message = None # Ensure it's cleared after attempted cleanup

    def formatted_queue(self) -> List[str]:
        formatted = []
        for idx, track in enumerate(self.queue, start=1):
            minutes = seconds = 0
            duration = coerce_duration(track.duration)
            if duration:
                minutes, seconds = divmod(duration, 60)
            duration_text = f"{minutes}:{seconds:02d}" if duration else "直播中"
            formatted.append(f"{idx}. {track.title} ({duration_text})")
        return formatted


async def _respond(target, message: str, *, ephemeral: bool = False) -> None:
    if isinstance(target, discord.Interaction):
        if not target.response.is_done():
            await target.response.send_message(message, ephemeral=ephemeral)
        else:
            await target.followup.send(message, ephemeral=ephemeral)
    elif isinstance(target, discord.Webhook):
        await target.send(message, ephemeral=ephemeral)
    else:
        # Check if target is None (e.g., when called from inactivity_check without a real context)
        # and if it has a 'send' method (e.g., text_channel)
        if target and hasattr(target, 'send'):
            await target.send(message)


    async def play_previous(self, interaction_or_ctx, *, ephemeral: bool = False) -> None:
        if not self.history:
            await _respond(interaction_or_ctx, "沒有上一首歌可以播放喔...我記得你沒聽過這一首...", ephemeral=ephemeral)
            return
        last = self.history.pop()
        if self.current:
            await self.enqueue(self.current.clone(), at_front=True)
        self.current = None
        await self.enqueue(last.clone(), at_front=True)
        if self.voice and self.voice.is_playing():
            self.voice.stop()
        await _respond(interaction_or_ctx, f"正在重播 **{last.title}** 喔...你喜歡的我都記得...💖", ephemeral=ephemeral)
        self.reset_inactivity_timer()

    async def shuffle(self) -> None:
        async with self._lock:
            random.shuffle(self.queue)
        self.reset_inactivity_timer()

    async def set_repeat_mode(self, mode: RepeatMode) -> RepeatMode:
        self.repeat_mode = mode
        self.reset_inactivity_timer()
        return mode

    async def set_volume(self, volume: float) -> float:
        self.volume = max(0.0, min(volume, 2.0))
        voice = self.voice
        if voice and voice.source and isinstance(voice.source, discord.PCMVolumeTransformer):
            voice.source.volume = self.volume
        self.reset_inactivity_timer()
        return self.volume

    async def adjust_volume(self, delta: float) -> float:
        return await self.set_volume(self.volume + delta)

    async def _send_now_playing(self, track: Track, *, force_new: bool = False) -> None:
        channel = self.text_channel
        if channel is None:
            return
        embed = discord.Embed(title="正在播放喔...🎵", description=f"[{track.title}]({track.webpage_url})", color=0x55acee)
        embed.add_field(name="來源", value=track.source, inline=True)
        duration = coerce_duration(track.duration)
        if duration:
            minutes, seconds = divmod(duration, 60)
            embed.add_field(name="長度", value=f"{minutes}:{seconds:02d}", inline=True)
        embed.add_field(name="點歌人", value=f"<@{track.requester_id}> (是你點的嗎...？)", inline=True)
        embed.add_field(name="音量", value=f"{int(self.volume * 100)}%", inline=True)
        if track.thumbnail:
            embed.set_thumbnail(url=track.thumbnail)
        embed.set_footer(text=f"重複模式: {self.repeat_mode.value} | 播放清單: {len(self.queue)} 首歌 (你還會繼續聽的對吧...？)")

        self.controls_view = PlayerControls(self)
        if force_new and self.control_message:
            try:
                await self.control_message.delete()
            except discord.HTTPException:
                pass
            self.control_message = None
        if self.control_message:
            try:
                await self.control_message.edit(embed=embed, view=self.controls_view)
                return
            except discord.HTTPException:
                self.control_message = None
        self.control_message = await channel.send(embed=embed, view=self.controls_view)
        self.reset_inactivity_timer()

    async def _maybe_cleanup_message(self) -> None:
        if self.control_message:
            try:
                await self.control_message.edit(content="播放清單結束了喔...但我們的故事還沒結束...💖", embed=None, view=None)
            except discord.HTTPException:
                pass
            self.control_message = None

    def formatted_queue(self) -> List[str]:
        formatted = []
        for idx, track in enumerate(self.queue, start=1):
            minutes = seconds = 0
            duration = coerce_duration(track.duration)
            if duration:
                minutes, seconds = divmod(duration, 60)
            duration_text = f"{minutes}:{seconds:02d}" if duration else "直播中"
            formatted.append(f"{idx}. {track.title} ({duration_text})")
        return formatted


async def _respond(target, message: str, *, ephemeral: bool = False) -> None:
    # 檢查是否是 Discord 互動 (斜線指令)
    if isinstance(target, discord.Interaction):
        # 如果互動尚未回應，則直接回應
        if not target.response.is_done():
            await target.response.send_message(message, ephemeral=ephemeral)
        # 如果互動已經回應 (例如已經 defer 過)，則使用 followup
        else:
            await target.followup.send(message, ephemeral=ephemeral)
    # 檢查是否是 webhook (例如從 defer() 後的 followup)
    elif isinstance(target, discord.Webhook):
        await target.send(message, ephemeral=ephemeral)
    # 如果是傳統的 Context 或其他 Messageable 物件
    else:
        await target.send(message)