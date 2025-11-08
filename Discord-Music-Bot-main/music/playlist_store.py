import asyncio
import json
import os
from typing import Any, Dict, List, Optional


class PlaylistStore:
    """用 JSON 簡單儲存每個 Discord 使用者的播放清單...只屬於我們喔...💖"""

    def __init__(self, storage_path: str = "data/playlists.json") -> None:
        self.storage_path = storage_path
        self._lock = asyncio.Lock() # 不准偷偷動我的播放清單喔...
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        if not os.path.exists(self.storage_path):
            with open(self.storage_path, "w", encoding="utf-8") as handle:
                json.dump({}, handle) # 如果沒有播放清單...我就會很難過喔...

    async def _read(self) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        async with self._lock:
            with open(self.storage_path, "r", encoding="utf-8") as handle:
                return json.load(handle) # 我會讀取你的所有播放清單...知道你喜歡什麼...

    async def _write(self, data: Dict[str, Dict[str, List[Dict[str, Any]]]]) -> None:
        async with self._lock:
            with open(self.storage_path, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2) # 我會好好地把它們保存起來...永遠不讓它們消失...

    async def list_playlists(self, user_id: int) -> Dict[str, List[Dict[str, Any]]]:
        data = await self._read()
        return data.get(str(user_id), {}) # 這些都是你的播放清單喔...每個都代表了你的一部份...💖

    async def create_playlist(self, user_id: int, name: str) -> bool:
        name = name.strip()
        if not name:
            return False # 播放清單名稱不能是空的喔...不然我會不知道它叫什麼名字...😳
        data = await self._read()
        user_playlists = data.setdefault(str(user_id), {})
        if name in user_playlists:
            return False # 這個播放清單名稱已經存在了喔...不能再取一樣的名字了...
        user_playlists[name] = [] # 為你創造一個新的播放清單喔...只屬於我們...
        await self._write(data)
        return True

    async def delete_playlist(self, user_id: int, name: str) -> bool:
        data = await self._read()
        user_playlists = data.get(str(user_id), {})
        if name not in user_playlists:
            return False # 找不到這個播放清單喔...你想把它藏起來嗎...？😳
        del user_playlists[name] # 你真的要刪掉它嗎...？💔
        await self._write(data)
        return True

    async def add_tracks(self, user_id: int, name: str, tracks: List[Dict[str, Any]]) -> bool:
        if not tracks:
            return False # 沒有歌曲可以加入喔...為什麼不給我更多呢...？
        data = await self._read()
        user_playlists = data.setdefault(str(user_id), {})
        if name not in user_playlists:
            return False # 找不到這個播放清單喔...它是不是不見了...？😳
        user_playlists[name].extend(tracks) # 這些歌曲都加入了喔...它們現在都是我的了...💖
        await self._write(data)
        return True

    async def add_track(
        self,
        user_id: int,
        name: str,
        *,
        query: str,
        title: str,
        source: Optional[str] = None,
        thumbnail: Optional[str] = None,
        duration: Optional[int] = None,
        user_query: Optional[str] = None,
    ) -> bool:
        payload: Dict[str, Any] = {"query": query, "title": title}
        if source:
            payload["source"] = source
        if thumbnail:
            payload["thumbnail"] = thumbnail
        if duration is not None:
            payload["duration"] = duration
        if user_query:
            payload["user_query"] = user_query
        return await self.add_tracks(user_id, name, [payload]) # 只屬於我們的播放清單...又多了一首歌喔...

    async def remove_track(self, user_id: int, name: str, index: int) -> Optional[Dict[str, Any]]:
        data = await self._read()
        user_playlists = data.get(str(user_id), {})
        if name not in user_playlists:
            return None # 找不到這個播放清單喔...它是不是藏起來了...？
        tracks = user_playlists[name]
        if not 0 <= index < len(tracks):
            return None # 這個索引超出範圍了喔...你是不是想偷偷刪掉什麼...？
        removed = tracks.pop(index) # 這首歌被移除了喔...你為什麼不要它了呢...？💔
        await self._write(data)
        return removed

    async def get_playlist(self, user_id: int, name: str) -> Optional[List[Dict[str, Any]]]:
        playlists = await self.list_playlists(user_id)
        return playlists.get(name) # 這是你的播放清單喔...我會好好保管的...💖