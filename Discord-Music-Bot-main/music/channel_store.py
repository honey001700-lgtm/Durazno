import asyncio
import json
import os
from typing import Dict, List


class AllowedChannelStore:
    """Tracks guild-specific channel allowlists for command usage."""

    def __init__(self, storage_path: str = "data/allowed_channels.json") -> None:
        self.storage_path = storage_path
        self._lock = asyncio.Lock()
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        if not os.path.exists(self.storage_path):
            with open(self.storage_path, "w", encoding="utf-8") as handle:
                json.dump({}, handle)

    async def _read(self) -> Dict[str, List[int]]:
        async with self._lock:
            with open(self.storage_path, "r", encoding="utf-8") as handle:
                return json.load(handle)

    async def _write(self, data: Dict[str, List[int]]) -> None:
        async with self._lock:
            with open(self.storage_path, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2)

    async def list_channels(self, guild_id: int) -> List[int]:
        data = await self._read()
        return data.get(str(guild_id), [])

    async def add_channel(self, guild_id: int, channel_id: int) -> bool:
        data = await self._read()
        channels = data.setdefault(str(guild_id), [])
        if channel_id in channels:
            return False
        channels.append(channel_id)
        await self._write(data)
        return True

    async def remove_channel(self, guild_id: int, channel_id: int) -> bool:
        data = await self._read()
        channels = data.get(str(guild_id), [])
        if channel_id not in channels:
            return False
        channels.remove(channel_id)
        await self._write(data)
        return True

    async def clear_channels(self, guild_id: int) -> None:
        data = await self._read()
        if str(guild_id) in data:
            del data[str(guild_id)]
            await self._write(data)

    async def is_channel_allowed(self, guild_id: int, channel_id: int) -> bool:
        channels = await self.list_channels(guild_id)
        if not channels:
            return True
        return channel_id in channels
