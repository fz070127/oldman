from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.deps import DbSession, UserScope, require_permission
from app.core.response import R
from app.models import Community, User
from app.models.enums import RoleCode
from app.schemas.responses import (
    CommunityDistribution,
    DashboardDeviceStatus,
    DashboardOverview,
    ItemList,
    RealtimeEvent,
    Response,
    TrendDay,
)
from app.services import dashboard_service

read_dashboard = Depends(require_permission("dashboard:read"))
DashboardUser = Annotated[User, read_dashboard]
router = APIRouter(prefix="/dashboard", tags=["看板"], dependencies=[read_dashboard])


@router.get("/overview", response_model=Response[DashboardOverview])
async def overview(db: DbSession, scope: UserScope):
    return R.ok(await dashboard_service.overview(db, scope))


@router.get("/trend", response_model=Response[ItemList[TrendDay]])
async def trend(db: DbSession, scope: UserScope, days: Annotated[int, Query(ge=1, le=90)] = 7):
    return R.ok({"list": await dashboard_service.trend(db, scope, days)})


@router.get("/distribution", response_model=Response[ItemList[CommunityDistribution]])
async def distribution(db: DbSession, scope: UserScope, user: DashboardUser):
    community = None if user.role_code == RoleCode.ADMIN else Community.id == user.community_id
    return R.ok({"list": await dashboard_service.distribution(db, scope, community)})


@router.get("/realtime", response_model=Response[ItemList[RealtimeEvent]])
async def realtime(db: DbSession, scope: UserScope):
    return R.ok({"list": await dashboard_service.realtime(db, scope)})


@router.get("/device-status", response_model=Response[DashboardDeviceStatus])
async def device_status(db: DbSession, scope: UserScope):
    return R.ok(await dashboard_service.device_status(db, scope))
