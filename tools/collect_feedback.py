"""Export reviewed fall events as a feedback dataset for the next training round.

Only events with handleResult TRUE_FALL or FALSE_POSITIVE are exported.
The script never edits existing labels or splits; it writes a review queue
under algo/data/feedback/ for human confirmation before re-labeling.
"""

from __future__ import annotations

import argparse
import csv
import getpass
import json
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "algo/data/feedback"
ACCEPTED = {"TRUE_FALL": 1, "FALSE_POSITIVE": 0}


def request_json(url, payload=None, token=None, method=None):
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        url, data=data, headers=headers, method=method or ("POST" if payload is not None else "GET")
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def login(base_url, username, password):
    body = request_json(f"{base_url}/api/v1/auth/login", {"username": username, "password": password})
    if body.get("code") != 0:
        raise RuntimeError(f"login failed: {body.get('message')}")
    return body["data"]["accessToken"]


def fetch_events(base_url, token, max_records):
    items, page, page_size = [], 1, min(100, max_records)
    while len(items) < max_records:
        query = urllib.parse.urlencode({"page": page, "pageSize": page_size})
        body = request_json(f"{base_url}/api/v1/events?{query}", token=token)
        if body.get("code") != 0:
            raise RuntimeError(f"fetch events failed: {body.get('message')}")
        batch = body["data"]["list"]
        items.extend(batch)
        if len(batch) < page_size or len(items) >= body["data"]["total"]:
            break
        page += 1
    return items[:max_records]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", help="省略时交互输入，使用 --token 时无需密码")
    parser.add_argument("--token")
    parser.add_argument("--max-records", type=int, default=1000)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    if args.max_records < 1:
        parser.error("--max-records 必须为正整数")
    base_url = args.base_url.rstrip("/")
    token = args.token or login(base_url, args.username, args.password or getpass.getpass())
    events = fetch_events(base_url, token, args.max_records)
    selected = [e for e in events if e.get("type") == "FALL" and e.get("handleResult") in ACCEPTED]

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    manifest = output / "feedback_manifest.csv"
    jsonl = output / "events.jsonl"
    with manifest.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "feedback_id", "seq_id", "label", "source", "clip_url", "snapshot_url",
            "confidence", "occurred_at", "device_no", "elder_id", "review_status",
        ])
        for event in selected:
            writer.writerow([
                event["eventId"], event["eventId"], ACCEPTED[event["handleResult"]], "online_event",
                event.get("clipUrl") or "", event.get("snapshotUrl") or "",
                event.get("confidence", ""), event.get("occurredAt", ""),
                event.get("deviceNo", ""), event.get("elderId", ""), "confirmed",
            ])
    jsonl.write_text(
        "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in selected), encoding="utf-8"
    )
    print(f"events scanned: {len(events)}")
    print(f"feedback exported: {len(selected)}")
    print(f"manifest: {manifest}")
    print(f"events: {jsonl}")
    print("next: human-review clip_url, extract keypoints, rebuild windows, then retrain with --scheduler plateau")


if __name__ == "__main__":
    main()
