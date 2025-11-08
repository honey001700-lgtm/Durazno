# Discord Music Bot

Modern Discord music bot with embeds, slash commands, and button controls inspired by bots such as Rythm. It streams tracks and playlists from YouTube and SoundCloud (via `yt-dlp`), keeps per-guild queues, and lets users save their own playlists.

## Features
- Play individual links, playlists, or search queries from YouTube / SoundCloud without logging in.
- Fully asynchronous queue per guild with shuffle, repeat (`none`, `one`, `all`), skip, previous, stop, and volume controls.
- Auto-updating "Now Playing" embed with pause/skip/shuffle/stop buttons.
- User-defined playlists stored on disk (`/playlist create|add|remove|show|list|play`).
- Helpful slash commands such as `/cp`, `/queue`, `/search`, and a custom embed-based `/help`.

## Requirements
- Python 3.10+
- FFmpeg available in your `PATH` (needed for audio streaming)
- PyNaCl installed (voice encryption backend)
- Discord bot token

### Installing FFmpeg
- **Windows**: download a static build from https://www.gyan.dev/ffmpeg/builds/, unzip it, and add the `bin` folder (containing `ffmpeg.exe`) to your `PATH`.
- **macOS**: `brew install ffmpeg`
- **Linux**: install via your package manager (e.g. `sudo apt install ffmpeg`)

Install Python requirements:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration
Create a `.env` file next to `bot.py`:

```
DISCORD_TOKEN=your_bot_token_here
```

(Optional) Customize command prefix or colors directly in `bot.py`.

## Running the Bot

```bash
python bot.py
```

Invite the bot to your server with the `bot` and `applications.commands` scopes plus permission to connect/speak in voice channels.

> Slash commands may take up to a minute to appear the first time the bot joins a server (Discord-side caching).

## Commands Overview
- `/play <url|search>` – queue a song/playlist (YouTube or SoundCloud)
- `/skip`, `/next`, `/previous`
- `/pause`, `/resume`, `/stop`, `/volume <1-200>`
- `/shuffle`, `/queue`, `/cp`, `/repeat <none|one|all>`
- `/playlist create|delete|add|remove|show|list|play`
- `/search <query>` – preview top YouTube results
- `/help` – embed with the core command list (sent ephemerally)

Each guild gets its own queue/player state. When a track changes, the bot posts (or updates) a rich embed that resembles premium music bots, keeping the channel informed without spamming plain text.
