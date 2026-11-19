import asyncio
from collections import defaultdict
from dataclasses import dataclass, field

import structlog
from fastapi import WebSocket

from app.models import User
from app.models.enums import RoleCode

log = structlog.get_logger()


@dataclass
class Connection:
    user_id: str
    community_id: str | None
    admin: bool
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class ConnectionManager:
    def __init__(self) -> None:
        self.by_user: dict[str, set[WebSocket]] = defaultdict(set)
        self.by_community: dict[str, set[WebSocket]] = defaultdict(set)
        self.all: dict[WebSocket, Connection] = {}

    async def connect(self, ws: WebSocket, user: User) -> None:
        await ws.accept()
        community_id = (
            user.community_id
            if user.role_code in (RoleCode.COMMUNITY_ADMIN, RoleCode.VIEWER)
            else None
        )
        self.all[ws] = Connection(user.id, community_id, user.role_code == RoleCode.ADMIN)
        self.by_user[user.id].add(ws)
        if community_id is not None:
            self.by_community[community_id].add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        connection = self.all.pop(ws, None)
        if connection is None:
            return
        for index, key in (
            (self.by_user, connection.user_id),
            (self.by_community, connection.community_id),
        ):
            if key is not None:
                index[key].discard(ws)
                if not index[key]:
                    del index[key]

    async def send(self, ws: WebSocket, msg: dict) -> bool:
        connection = self.all.get(ws)
        if connection is None:
            return False
        try:
            async with asyncio.timeout(2), connection.lock:
                if ws not in self.all:
                    return False
                await ws.send_json(msg)
        except Exception:
            log.debug("ws_send_failed", user_id=connection.user_id, exc_info=True)
            self.disconnect(ws)
            return False
        return True

    async def broadcast_to_user(self, user_id: str, msg: dict) -> int:
        return await self._broadcast(self.by_user.get(user_id, ()), msg)

    async def broadcast_to_community(self, community_id: str, msg: dict) -> int:
        return await self._broadcast(self.by_community.get(community_id, ()), msg)

    async def broadcast_all(self, msg: dict) -> int:
        return await self._broadcast(self.all, msg)

    async def broadcast_scoped(
        self, community_id: str | None, msg: dict, *, user_ids=(), exclude_user_id=None
    ) -> int:
        sockets = {ws for ws, connection in self.all.items() if connection.admin}
        sockets.update(self.by_community.get(community_id, ()))
        for user_id in user_ids:
            sockets.update(self.by_user.get(user_id, ()))
        sockets.difference_update(self.by_user.get(exclude_user_id, ()))
        return await self._broadcast(sockets, msg)

    async def _broadcast(self, sockets, msg: dict) -> int:
        return sum(await asyncio.gather(*(self.send(ws, msg) for ws in sockets)))
