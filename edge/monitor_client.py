"""Optional HTTP client for backend model runtime monitoring."""

import json
import urllib.request


def post_record(url, token, device_no, score, latency_ms, level="P1", timeout=2.0):
    payload = json.dumps({
        "deviceNo": device_no,
        "score": float(score),
        "latencyMs": float(latency_ms),
        "level": level,
    }).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.load(response)
        if result.get("code") != 0:
            raise ValueError(result.get("message", "model monitor rejected the record"))
