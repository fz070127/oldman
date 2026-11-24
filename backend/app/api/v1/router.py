from fastapi import APIRouter

from app.api.v1.alarms import router as alarms_router
from app.api.v1.auth import router as auth_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.detection import router as detection_router
from app.api.v1.devices import router as devices_router
from app.api.v1.elders import router as elders_router
from app.api.v1.events import router as events_router
from app.api.v1.model_monitor import router as model_monitor_router
from app.api.v1.system import router as system_router
from app.api.v1.ws import router as ws_router

router = APIRouter(prefix="/api/v1")
router.include_router(auth_router)
router.include_router(elders_router)
router.include_router(devices_router)
router.include_router(events_router)
router.include_router(alarms_router)
router.include_router(dashboard_router)
router.include_router(detection_router)
router.include_router(model_monitor_router)
router.include_router(system_router)
router.include_router(ws_router)
