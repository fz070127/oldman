"""系统启动后的核心功能验收：健康检查、登录、权限、看板、事件、告警、模型监控、前端页面。

仅用标准库。从环境变量或本地 .env 读取演示账号密码。
输出 logs/verify_system.json；任一检查失败返回非零退出码。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "logs" / "verify_system.json"


def seed_password(env_file):
    configured = os.environ.get("DEMO_SEED_PASSWORD")
    if configured:
        return configured
    for path in (env_file,) if env_file else (ROOT / "deploy/.env", ROOT / "backend/.env"):
        if path.is_file():
            for line in path.read_text(encoding="utf-8-sig").splitlines():
                key, _, value = line.partition("=")
                if key.strip() == "DEMO_SEED_PASSWORD":
                    return value.strip().strip("'\"")
    raise RuntimeError("请配置 DEMO_SEED_PASSWORD 或指定 --env-file")


def call(url, method="GET", body=None, token=None, timeout=10):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", "replace")
            status = response.status
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8", "replace")
        status = error.code
    except Exception as error:
        return {"status": 0, "error": type(error).__name__, "body": str(error)}
    try:
        payload = json.loads(raw) if raw.strip().startswith("{") else None
    except json.JSONDecodeError:
        payload = None
    return {"status": status, "json": payload, "text_len": len(raw)}


def upload(url, path, token=None, timeout=60):
    boundary = "----verify-system-boundary"
    payload = path.read_bytes()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
        "Content-Type: image/png\r\n\r\n"
    ).encode("utf-8") + payload + f"\r\n--{boundary}--\r\n".encode("utf-8")
    headers = {"Accept": "application/json", "Content-Type": f"multipart/form-data; boundary={boundary}"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", "replace")
            status = response.status
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8", "replace")
        status = error.code
    except Exception as error:
        return {"status": 0, "error": type(error).__name__, "body": str(error)}
    try:
        payload_json = json.loads(raw) if raw.strip().startswith("{") else None
    except json.JSONDecodeError:
        payload_json = None
    return {"status": status, "json": payload_json}


def api_ok(result):
    if result.get("status") != 200:
        return False
    payload = result.get("json")
    if payload is None:
        return True
    if "detail" in payload or "error" in payload:
        return False
    return payload.get("code") == 0 or "code" not in payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", default="http://localhost:8000")
    parser.add_argument("--frontend", default="http://localhost:8080")
    parser.add_argument("--env-file", type=Path)
    args = parser.parse_args()

    checks = {}
    password = seed_password(args.env_file)

    health = call(f"{args.backend}/health")
    # /health 返回统一响应体 {code, message, data:{status, db, redis, mqtt}}
    health_json = health.get("json") or {}
    health_data = health_json.get("data") or {}
    checks["health"] = {
        "ok": health.get("status") == 200 and health_data.get("status") == "up",
        "status": health.get("status"),
        "db": health_data.get("db"),
        "redis": health_data.get("redis"),
        "mqtt": health_data.get("mqtt"),
    }

    login = call(f"{args.backend}/api/v1/auth/login", "POST",
                 {"username": "admin", "password": password})
    data = (login.get("json") or {}).get("data") or {}
    token = data.get("accessToken") or data.get("access_token")
    checks["admin_login"] = {"ok": api_ok(login) and bool(token),
                             "status": login.get("status"),
                             "code": (login.get("json") or {}).get("code"),
                             "role": data.get("user", {}).get("roleCode")
                             if isinstance(data.get("user"), dict) else None}

    if token:
        me = call(f"{args.backend}/api/v1/auth/me", token=token)
        checks["auth_me"] = {"ok": api_ok(me), "status": me.get("status")}
        endpoints = {
            "dashboard_overview": "/api/v1/dashboard/overview",
            "dashboard_trend": "/api/v1/dashboard/trend",
            "dashboard_distribution": "/api/v1/dashboard/distribution",
            "dashboard_realtime": "/api/v1/dashboard/realtime",
            "dashboard_device_status": "/api/v1/dashboard/device-status",
            "devices": "/api/v1/devices",
            "events": "/api/v1/events",
            "events_stats": "/api/v1/events/stats",
            "alarms": "/api/v1/alarms",
            "alarms_pending_count": "/api/v1/alarms/pending-count",
            "alarms_stats": "/api/v1/alarms/stats",
            "model_monitor_snapshot": "/api/v1/model-monitor/snapshot",
            "system_users": "/api/v1/system/users?page=1&pageSize=3",
            "system_roles": "/api/v1/system/roles",
            "system_communities": "/api/v1/system/communities?page=1&pageSize=3",
            "system_guardians": "/api/v1/system/guardians?page=1&pageSize=3",
        }
        for name, path in endpoints.items():
            result = call(f"{args.backend}{path}", token=token)
            checks[name] = {"ok": api_ok(result), "status": result.get("status"),
                            "code": (result.get("json") or {}).get("code")}

        users_result = call(f"{args.backend}/api/v1/system/users?page=1&pageSize=1", token=token)
        users_payload = (users_result.get("json") or {}).get("data") or {}
        first_user = (users_payload.get("list") or [{}])[0]
        checks["system_user_camel_fields"] = {
            "ok": api_ok(users_result) and all(
                key in first_user for key in ("roleCode", "communityName", "lastLoginAt")
            ),
            "fields": sorted(first_user.keys()),
        }

        samples = ROOT / "frontend" / "public" / "samples"
        for name, filename, expected in (
            ("image_detection_fall", "fall-130.png", "FALL"),
            ("image_detection_normal", "normal-060.png", "NORMAL"),
        ):
            result = upload(f"{args.backend}/api/v1/detection/image",
                            samples / filename, token=token)
            data = (result.get("json") or {}).get("data") or {}
            checks[name] = {
                "ok": api_ok(result) and data.get("status") == expected
                and len(data.get("keypoints") or []) == 17,
                "status": result.get("status"),
                "detected": data.get("status"),
                "score": data.get("score"),
            }

        guardian = call(f"{args.backend}/api/v1/auth/login", "POST",
                        {"username": "guardian01", "password": password})
        gdata = (guardian.get("json") or {}).get("data") or {}
        gtoken = gdata.get("accessToken") or gdata.get("access_token")
        checks["guardian_login"] = {"ok": api_ok(guardian) and bool(gtoken),
                                    "status": guardian.get("status")}
        if gtoken:
            for name, path, code in (
                ("guardian_system_denied", "/api/v1/system/users", 1003),
                ("guardian_dashboard_denied", "/api/v1/dashboard/overview", 1003),
                ("guardian_events", "/api/v1/events", 0),
            ):
                result = call(f"{args.backend}{path}", token=gtoken)
                response_code = (result.get("json") or {}).get("code")
                checks[name] = {"ok": response_code == code, "code": response_code}

    for name, path in (("frontend_root", "/"), ("frontend_demo_detect", "/demo/detect"),
                       ("frontend_image_detect", "/demo/image-detect"),
                       ("frontend_sample_image", "/samples/fall-130.png")):
        result = call(f"{args.frontend}{path}")
        checks[name] = {"ok": result.get("status") == 200,
                        "status": result.get("status")}

    failed = [k for k, v in checks.items() if not v.get("ok")]
    report = {"backend": args.backend, "frontend": args.frontend,
              "checks": checks, "failed": failed,
              "all_ok": not failed, "n_checks": len(checks)}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"all_ok": report["all_ok"], "n_checks": len(checks),
                      "failed": failed, "health": checks.get("health"),
                      "admin_login": checks.get("admin_login")},
                     ensure_ascii=False, indent=2))
    return 0 if report["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
