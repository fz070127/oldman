from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.core.deps import require_permission
from app.core.response import R
from app.schemas.responses import Response
from app.services import model_monitor

router = APIRouter(prefix="/model-monitor", tags=["模型监控"])
read_dashboard = Depends(require_permission("dashboard:read"))
record_monitor = Depends(require_permission("model-monitor:record"))
manage_monitor = Depends(require_permission("model-monitor:write"))


class InferenceRecordIn(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    deviceNo: str = Field(min_length=1, max_length=64)
    score: float = Field(ge=0, le=1)
    latencyMs: float = Field(ge=0)
    level: str = Field(default="P1", max_length=8)


class BaselineIn(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    scoreMean: float = Field(ge=0, le=1)
    scoreStd: float = Field(ge=1e-6, le=1)
    latencyP95Ms: float = Field(gt=0)


@router.get("/snapshot", dependencies=[read_dashboard], response_model=Response[dict])
async def snapshot():
    return R.ok(model_monitor.snapshot())


@router.post("/record", dependencies=[record_monitor], response_model=Response[dict])
async def add_record(payload: InferenceRecordIn):
    model_monitor.record(payload.deviceNo, payload.score, payload.latencyMs, payload.level)
    return R.ok(model_monitor.snapshot())


@router.post("/baseline", dependencies=[manage_monitor], response_model=Response[dict[str, float]])
async def set_baseline(payload: BaselineIn):
    baseline = model_monitor.configure_baseline(
        payload.scoreMean, payload.scoreStd, payload.latencyP95Ms
    )
    return R.ok(baseline)


@router.post("/reset", dependencies=[manage_monitor], response_model=Response[dict])
async def reset():
    model_monitor.reset()
    return R.ok(model_monitor.snapshot())
