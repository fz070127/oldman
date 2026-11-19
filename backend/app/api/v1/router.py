from fastapi import APIRouter

from app.api.v1.alarms import router as alarms_router
from app.api.v1.auth import router as auth_router
from app.api.v1.devices import router as devices_router
from app.api.v1.elders import router as elders_router
from app.api.v1.events import router as events_router

router = APIRouter(prefix="/api/v1")
router.include_router(auth_router)
router.include_router(elders_router)
router.include_router(devices_router)
router.include_router(events_router)
router.include_router(alarms_router)
