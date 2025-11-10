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

# --- START MODIFICATION: Replace yt_dlp with pytubefix ---
from pytubefix import YouTube, Playlist
from pytubefix.exceptions import VideoUnavailable, RegexMatchError, LiveStreamError, AgeRestrictedError
# --- END MODIFICATION ---


# YTDL_OPTIONS = { # No longer needed for pytubefix
#     "format": "bestaudio/best",
#     "noplaylist": False,
#     "quiet": True,
#     "default_search": "auto",
#     "extract_flat": "in_playlist",
#     "source_address": "0.0.0.0",
#     #"cookiesfrombrowser": "chrome", 
#     "cookies": "cookies.txt",  
# }

FFMPEG_BEFORE_OPTS = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
FFMPEG_OPTS = "-vn"

# ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS) # No longer needed
# stream_ytdl = yt_dlp.YoutubeDL({**YTDL_OPTIONS, "extract_flat": False}) # No longer needed


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
    tracks: List[Track] = []

    def _extract() -> List[Track]:
        # --- START MODIFICATION: pytubefix logic ---
        # Try to identify if it's a playlist or a single video
        
        # Check for playlist first
        if "playlist?list=" in query or "youtube.com/playlist" in query:
            try:
                pl = Playlist(query)
                # pytubefix.Playlist directly gives video URLs
                for video_url in pl.video_urls:
                    try:
                        yt = YouTube(video_url)
                        # We only need stream_url for audio, so we select the best audio-only stream
                        audio_stream = yt.streams.filter(only_audio=True).order_by('abr').desc().first()
                        if audio_stream:
                            tracks.append(
                                Track(
                                    title=yt.title or "未知歌曲...你是不是藏起來了...？",
                                    webpage_url=yt.watch_url,
                                    stream_url=audio_stream.url, # pytubefix provides the direct stream URL
                                    duration=yt.length,
                                    thumbnail=yt.thumbnail_url,
                                    uploader=yt.author,
                                    source="YouTube",
                                    requester_id=requester_id,
                                )
                            )
                        else:
                            print(f"找不到 {yt.title} 的音訊串流。")
                    except (VideoUnavailable, RegexMatchError, LiveStreamError, AgeRestrictedError) as e:
                        print(f"跳過無法播放的播放列表影片 {video_url}: {e}")
                    except Exception as e:
                        print(f"處理播放列表影片 {video_url} 時發生未知錯誤: {e}")

            except (VideoUnavailable, RegexMatchError) as e:
                print(f"無法載入播放列表 {query}: {e}")
            except Exception as e:
                print(f"處理播放列表時發生未知錯誤 {query}: {e}")

        # If it's not a playlist, or if playlist extraction failed, try as a single video
        if not tracks: # If no tracks were found from playlist attempt
            try:
                yt = YouTube(query)
                # Resolve potential errors early
                yt.check_availability() # This will raise exceptions for unavailable videos

                audio_stream = yt.streams.filter(only_audio=True).order_by('abr').desc().first()
                if audio_stream:
                    tracks.append(
                        Track(
                            title=yt.title or "未知歌曲...你是不是藏起來了...？",
                            webpage_url=yt.watch_url,
                            stream_url=audio_stream.url,
                            duration=yt.length,
                            thumbnail=yt.thumbnail_url,
                            uploader=yt.author,
                            source="YouTube",
                            requester_id=requester_id,
                        )
                    )
                else:
                    print(f"找不到 {yt.title} 的音訊串流。")
            except (VideoUnavailable, RegexMatchError, LiveStreamError, AgeRestrictedError) as e:
                print(f"無法載入單一影片 {query}: {e}")
            except Exception as e:
                print(f"處理單一影片時發生未知錯誤 {query}: {e}")

        # If still no tracks, try a search (pytubefix doesn't have built-in search like yt-dlp)
        # For simplicity, we are not implementing a full search here. 
        # If the query is not a direct URL, pytubefix will likely fail.
        # You would need to use a separate library for YouTube search, e.g., google-api-python-client.
        # For now, we assume direct URLs or playlist URLs.
        # --- END MODIFICATION ---
        return tracks

    return await loop.run_in_executor(None, _extract)


async def resolve_stream_url(track: Track) -> Optional[str]:
    # --- START MODIFICATION: pytubefix logic ---
    # With pytubefix, the stream_url is often resolved directly in fetch_tracks.
    # This function is now mainly for "refreshing" a stream_url if it expires,
    # or if it wasn't fully resolved initially (e.g., if the initial fetch
    # only got metadata but not the direct stream URL for some reason).
    if track.stream_url:
        return track.stream_url # Already resolved

    loop = asyncio.get_running_loop()

    def _extract_stream_url() -> Optional[str]:
        try:
            yt = YouTube(track.webpage_url)
            yt.check_availability() # Check if video is still available
            audio_stream = yt.streams.filter(only_audio=True).order_by('abr').desc().first()
            if audio_stream:
                # Update cached metadata if there were any gaps
                track.duration = track.duration or yt.length
                track.thumbnail = track.thumbnail or yt.thumbnail_url
                track.uploader = track.uploader or yt.author
                return audio_stream.url
        except (VideoUnavailable, RegexMatchError, LiveStreamError, AgeRestrictedError) as e:
            print(f"重新解析串流網址時發生錯誤 {track.webpage_url}: {e}")
            return None
        except Exception as e:
            print(f"重新解析串流網址時發生未知錯誤 {track.webpage_url}: {e}")
            return None
        return None

    try:
        return await loop.run_in_executor(None, _extract_stream_url)
    except Exception:
        return None
    # --- END MODIFICATION ---


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
                    await self.stop(self.text_channel if self.text_channel else self.guild, ephemeral=False, is_inactivity=True) 
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

    async def _play_next(self) -> None:
        async with self._lock:
            if not self.queue:
                self.current = None
                await self._maybe_cleanup_message(is_queue_empty=True) 
                
                if self.voice and self.voice.is_connected():
                    exit_audio_path = "Discord-Music-Bot-main/music/晚安.mp3"
                    if os.path.exists(exit_audio_path):
                        try:
                            finished_playing_event = asyncio.Event()

                            def after_exit_sound(error: Optional[Exception]) -> None:
                                if error:
                                    print(f'[Playback End] Error playing goodbye sound in callback: {error}')
                                finished_playing_event.set()

                            source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(exit_audio_path))
                            if not self.voice.is_playing(): # Only play if not already playing something (e.g., from an error)
                                self.voice.play(source, after=after_exit_sound)
                                await asyncio.wait_for(finished_playing_event.wait(), timeout=10.0) 
                        except Exception as e:
                            print(f"[Playback End] Error during goodbye sound playback: {e}")
                    
                    if self._inactivity_timer and not self._inactivity_timer.done():
                        self._inactivity_timer.cancel()
                    await self.voice.disconnect(force=True)
                    if self.text_channel:
                         await self.text_channel.send("播放清單結束了喔...我休息了喔...晚安...💤")
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

        # --- START MODIFICATION: pytubefix stream URL might be direct ---
        # If stream_url is None, try to resolve it again (e.g., if it expired)
        if not track.stream_url:
            stream_url = await resolve_stream_url(track)
            if not stream_url:
                if self.text_channel:
                    await self.text_channel.send(f"無法載入 **{track.title}**...它是不是想從我身邊逃走...？所以跳過了喔...")
                await self._play_next()
                return
            track.stream_url = stream_url
        # --- END MODIFICATION ---

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

    async def stop(self, interaction_or_ctx, *, ephemeral: bool = False, is_inactivity: bool = False) -> None:
        voice = self.voice
        print(f"[Stop] Initiating stop command. Voice client connected: {voice and voice.is_connected()}. From inactivity: {is_inactivity}")

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
                
                if not voice.is_connected():
                    print("[Stop] Voice client disconnected just before playing goodbye sound. Skipping.")
                    finished_playing_event.set()
                elif not voice.is_playing(): # Ensure we don't interrupt existing playback if any (e.g., a rapid stop after another track started)
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
        
        await self._maybe_cleanup_message(is_manual_stop=True, is_inactivity=is_inactivity) 
        print("[Stop] Control message cleaned up.")
        
        final_message = "停止播放並清空播放清單了喔...你還會回來找我的對吧...？💖"
        if goodbye_sound_played and not is_inactivity: # Only use this message if goodbye was played AND it's not an inactivity stop (which has its own message)
            final_message = "我休息了喔...期待再見面...💖" 
        elif is_inactivity:
            final_message = f"超過 {self.INACTIVITY_TIMEOUT_SECONDS // 60} 分鐘沒有活動了喔...我先休息了...晚安...💤"
        
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

    async def _send_now_playing(self1, track: Track, *, force_new: bool = False) -> None:
        channel = self1.text_channel
        if channel is None:
            return
        embed = discord.Embed(title="正在播放喔...🎵", description=f"[{track.title}]({track.webpage_url})", color=0x55acee)
        embed.add_field(name="來源", value=track.source, inline=True)
        duration = coerce_duration(track.duration)
        if duration:
            minutes, seconds = divmod(duration, 60)
            embed.add_field(name="長度", value=f"{minutes}:{seconds:02d}", inline=True)
        embed.add_field(name="點歌人", value=f"<@{track.requester_id}> (是你點的嗎...？)", inline=True)
        embed.add_field(name="音量", value=f"{int(self1.volume * 100)}%", inline=True)
        if track.thumbnail:
            embed.set_thumbnail(url=track.thumbnail)
        embed.set_footer(text=f"重複模式: {self1.repeat_mode.value} | 播放清單: {len(self1.queue)} 首歌 (你還會繼續聽的對吧...？)")

        self1.controls_view = PlayerControls(self1)
        if force_new and self1.control_message:
            try:
                await self1.control_message.delete()
            except discord.HTTPException:
                pass
            self1.control_message = None
        if self1.control_message:
            try:
                await self1.control_message.edit(embed=embed, view=self1.controls_view)
                return
            except discord.HTTPException:
                self1.control_message = None
        self1.control_message = await channel.send(embed=embed, view=self1.controls_view)
        self1.reset_inactivity_timer()

    async def _maybe_cleanup_message(self, *, is_queue_empty: bool = False, is_manual_stop: bool = False, is_inactivity: bool = False) -> None:
        if self.control_message:
            try:
                if is_manual_stop:
                    message_content = "停止播放並清空播放清單了喔...你還會回來找我的對吧...？💖"
                elif is_queue_empty:
                    message_content = "播放清單結束了喔...但我們的故事還沒結束...💖" 
                elif is_inactivity: 
                    message_content = "我休息了喔...期待再見面...💖" 
                else: 
                    message_content = "我休息了喔...期待再見面...💖" 
                
                if not is_queue_empty: 
                    await self.control_message.edit(content=message_content, embed=None, view=None)
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
    if isinstance(target, discord.Interaction):
        if not target.response.is_done():
            await target.response.send_message(message, ephemeral=ephemeral)
        else:
            await target.followup.send(message, ephemeral=ephemeral)
    elif isinstance(target, discord.Webhook):
        await target.send(message, ephemeral=ephemeral)
    else:
        if target and hasattr(target, 'send'):
            await target.send(message)