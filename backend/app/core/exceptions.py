import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from starlette.middleware.exceptions import ExceptionMiddleware

from app.core.response import R

log = structlog.get_logger()


class BizException(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


async def business_error(request: Request, exc: BizException) -> JSONResponse:
    return JSONResponse(R.fail(exc.code, exc.message))


async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    reasons = {"missing": "缺少必填值", "int_parsing": "应为整数", "json_invalid": "JSON 格式错误"}
    problems = []
    for error in exc.errors():
        field = ".".join(str(part) for part in error["loc"]) or "请求"
        reason = reasons.get(error["type"], "值不符合要求")
        problems.append(f"{field}（{reason}）")
    return JSONResponse(R.fail(1001, "参数校验失败：" + "、".join(problems)))


async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
    errors = {
        401: (1002, "未登录"),
        403: (1003, "无权限"),
        404: (1004, "资源不存在"),
        405: (1001, "请求方法不支持"),
        409: (1005, "状态冲突"),
        429: (1006, "请求过于频繁"),
        503: (5001, "下游依赖不可用"),
    }
    code, message = errors.get(exc.status_code, (1001, "请求参数错误"))
    return JSONResponse(R.fail(code, message), headers=exc.headers)


async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    log.error("请求处理异常", method=request.method, path=request.url.path, exc_info=exc)
    return JSONResponse(R.fail(5000, "服务器内部错误"), status_code=500)


def register_handlers(app: FastAPI) -> None:
    app.add_exception_handler(BizException, business_error)
    app.add_exception_handler(RequestValidationError, validation_error)
    app.add_exception_handler(HTTPException, http_error)
    # 兜底处理放在追踪和 CORS 中间件内层，500 也使用同一请求上下文和响应头。
    app.add_middleware(ExceptionMiddleware, handlers={Exception: unexpected_error})
