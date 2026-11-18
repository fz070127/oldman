from typing import Any

from app.core.logging import trace_id


class R:
    @staticmethod
    def ok(data: Any = None, message: str = "ok") -> dict:
        return {"code": 0, "message": message, "data": data, "traceId": trace_id.get()}

    @staticmethod
    def page(list: list, total: int, page: int = 1, pageSize: int = 20) -> dict:
        if page < 1 or not 1 <= pageSize <= 100:
            raise ValueError("页码须大于零，每页条数须在 1 到 100 之间")
        return R.ok({"list": list, "total": total, "page": page, "pageSize": pageSize})

    @staticmethod
    def fail(code: int, message: str) -> dict:
        return {"code": code, "message": message, "data": None, "traceId": trace_id.get()}
