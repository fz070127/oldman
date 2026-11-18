from fastapi import APIRouter

router = APIRouter(prefix="/api/v1")

# 认证、老人、设备、事件、告警等模块后续通过 router.include_router 挂到此前缀。
