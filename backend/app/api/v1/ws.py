import asyncio
import json
from contextlib import suppress

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.exceptions import BizException
from app.core.tokens import AccessClaims, TokenIssuer
from app.services.auth_redis import AuthRedis
from app.services.auth_service import get_active_user

router = APIRouter()
IDLE_SECONDS = 60


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    state = ws.app.state
    try:
        token = TokenIssuer(state.settings).decode(ws.query_params.get("token", ""), AccessClaims)
        if await AuthRedis(state.redis).is_revoked(token):
            raise BizException(1002, "登录凭证已失效")
        async with state.db_sessionmaker() as db:
            user = await get_active_user(db, token.sub)
    except BizException:
        await ws.accept()
        await ws.close(code=4401)
        return

    manager = state.connections
    await manager.connect(ws, user)
    try:
        while True:
            async with asyncio.timeout(IDLE_SECONDS):
                message = await ws.receive()
            if message["type"] == "websocket.disconnect":
                break
            raw = message.get("text") or message.get("bytes") or ""
            try:
                data = json.loads(raw)
            except ValueError:
                continue
            if (
                isinstance(data, dict)
                and data.get("type") == "PING"
                and not await manager.send(ws, {"type": "PONG"})
            ):
                break
    except TimeoutError:
        manager.disconnect(ws)
        with suppress(WebSocketDisconnect, OSError, RuntimeError):
            await ws.close(code=4408)
    finally:
        manager.disconnect(ws)
