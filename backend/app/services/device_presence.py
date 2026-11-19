import asyncio
from datetime import timedelta

import structlog
from sqlalchemy import func, select, update

from app.models import Device, Elder
from app.models.enums import DeviceStatus

log = structlog.get_logger()
HEARTBEAT_TTL = timedelta(seconds=90)
SCAN_INTERVAL = 30


class DevicePresence:
    def __init__(self, sessions, realtime):
        self.sessions = sessions
        self.realtime = realtime

    async def scan(self) -> None:
        community = select(Elder.community_id).where(Elder.id == Device.elder_id).scalar_subquery()
        async with self.sessions.begin() as db:
            rows = (
                await db.execute(
                    update(Device)
                    .where(
                        Device.status == DeviceStatus.ONLINE,
                        Device.last_heartbeat < func.now() - HEARTBEAT_TTL,
                    )
                    .values(status=DeviceStatus.OFFLINE)
                    .returning(
                        Device.id,
                        Device.device_no,
                        Device.status,
                        Device.last_heartbeat,
                        community.label("community_id"),
                    )
                )
            ).all()
        await asyncio.gather(*(self.realtime.device(row, row.community_id) for row in rows))

    async def run(self) -> None:
        while True:
            try:
                await self.scan()
            except Exception:
                log.exception("device_offline_scan_failed")
            await asyncio.sleep(SCAN_INTERVAL)
