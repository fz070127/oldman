"""图片上传的人体状态检测接口。"""

from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.core.deps import require_permission
from app.core.exceptions import BizException
from app.core.response import R
from app.schemas.responses import Response
from app.services.image_detection import MAX_IMAGE_BYTES, detect_bytes

router = APIRouter(prefix="/detection", tags=["图片检测"])


@router.post(
    "/image",
    dependencies=[Depends(require_permission("dashboard:read"))],
    response_model=Response[dict],
)
async def detect_image(file: Annotated[UploadFile, File(description="待检测图片")]) -> dict:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise BizException(1001, "请上传图片文件（JPEG / PNG / WEBP）")
    data = await file.read(MAX_IMAGE_BYTES + 1)
    try:
        result = await run_in_threadpool(detect_bytes, data)
    except ValueError as error:
        raise BizException(1001, str(error)) from error
    except FileNotFoundError as error:
        raise BizException(5001, "图片检测缺少 YOLOv8n-pose 权重，请配置姿态模型") from error
    return R.ok(result)
