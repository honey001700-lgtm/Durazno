# Repository Guidelines

## Project Structure & Module Organization
- `bot.py` hosts slash commands, Discord intents, and playlist orchestration.
- `music/` contains reusable helpers: `player.py` for queue/audio logic and `playlist_store.py` for JSON-backed user playlists in `data/playlists.json`.
- `requirements.txt` tracks runtime dependencies; `README.md` explains setup; `AGENTS.md` (this file) is the contributor quick-start.

## Build, Test, and Development Commands
- `python -m venv .venv && source .venv/bin/activate` – create and enter an isolated environment (Windows PowerShell: `.venv\Scripts\Activate.ps1`).
- `pip install -r requirements.txt` – install discord.py, yt-dlp, PyNaCl, python-dotenv, and supporting libraries.
- `python bot.py` – run the bot locally; slash commands auto-sync on startup. Watch the console for Discord/ytdlp warnings.

## Coding Style & Naming Conventions
- Use Python 3.10+ with 4-space indentation and type hints where practical.
- Favor descriptive snake_case for functions/variables, PascalCase for classes, and UPPER_SNAKE_CASE for constants (e.g., `FFMPEG_BEFORE_OPTS`).
- Keep public helpers documented inline only when behavior is non-obvious; avoid noisy comments.

## Testing Guidelines
- No automated tests exist yet. When adding features, include lightweight sanity scripts (e.g., guild mocks) under `tests/` or as standalone modules, then document how to run them in PRs.
- Exercise manual QA: `/play`, `/playlist play`, `/queue`, `/cp`, `/repeat`. Validate edge cases like empty queues, voice move, and missing FFmpeg/PyNaCl paths.

## Commit & Pull Request Guidelines
- Follow conventional, action-oriented commit summaries (e.g., "Add slash command playlist group"). Wrap at ~72 chars where possible.
- Each PR should describe the change, list tested commands, outline manual/automated validation, and note any breaking behavior for bot operators. Include screenshots of embeds if UI changes occur.
- Reference related GitHub issues using "Fixes #123" style, and request review from maintainers responsible for bot ops.

## Security & Configuration Tips
- Never hardcode `DISCORD_TOKEN`; rely on `.env` + `load_dotenv()`.
- Update `requirements.txt` when yt-dlp or discord.py patches are needed, then mention version bumps and audit considerations in PR notes.
