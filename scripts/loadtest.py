"""Benchmark the authenticated alarm and event list endpoints over HTTP."""

import argparse
import asyncio
import math
import os
from collections import Counter
from time import perf_counter

import httpx

ENDPOINTS = ("/alarms", "/events")


def positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def check_response(response: httpx.Response) -> None:
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, dict) or body.get("code") != 0:
        code = body.get("code") if isinstance(body, dict) else None
        raise ValueError(f"business code {code}")


async def benchmark(
    client: httpx.AsyncClient,
    path: str,
    concurrency: int,
    duration: int,
) -> dict:
    check_response(await client.get(path))
    latencies = []
    errors = Counter()
    started = perf_counter()
    deadline = started + duration

    async def worker() -> None:
        while (sent := perf_counter()) < deadline:
            try:
                response = await client.get(path)
                elapsed_ms = (perf_counter() - sent) * 1000
                check_response(response)
            except httpx.HTTPStatusError as exc:
                errors[f"HTTP {exc.response.status_code}"] += 1
            except httpx.RequestError as exc:
                errors[type(exc).__name__] += 1
            except ValueError as exc:
                reason = str(exc)
                key = reason if reason.startswith("business code ") else "invalid JSON"
                errors[key] += 1
            else:
                latencies.append(elapsed_ms)

    await asyncio.gather(*(worker() for _ in range(concurrency)))
    elapsed = perf_counter() - started
    latencies.sort()
    total = len(latencies) + errors.total()

    def percentile(q: float) -> float:
        if not latencies:
            return float("nan")
        return latencies[math.ceil(len(latencies) * q) - 1]

    return {
        "total": total,
        "elapsed": elapsed,
        "qps": total / elapsed,
        "p50": percentile(0.50),
        "p95": percentile(0.95),
        "p99": percentile(0.99),
        "error_rate": 100 * errors.total() / total if total else float("nan"),
        "errors": errors,
    }


async def run(args: argparse.Namespace, token: str) -> int:
    limits = httpx.Limits(
        max_connections=args.concurrency, max_keepalive_connections=args.concurrency
    )
    passed = True
    async with httpx.AsyncClient(
        base_url=args.base_url,
        headers={"Authorization": f"Bearer {token}"},
        limits=limits,
        timeout=5,
        trust_env=False,
    ) as client:
        print(
            f"{args.concurrency} concurrent clients, {args.duration}s per endpoint",
            flush=True,
        )
        for endpoint in ENDPOINTS:
            result = await benchmark(client, endpoint, args.concurrency, args.duration)
            print(
                f"{endpoint}  {result['total']} requests in {result['elapsed']:.2f}s  "
                f"QPS {result['qps']:.2f}  P50 {result['p50']:.2f} ms  "
                f"P95 {result['p95']:.2f} ms  P99 {result['p99']:.2f} ms  "
                f"error rate {result['error_rate']:.2f}%",
                flush=True,
            )
            if result["errors"]:
                print(f"Errors: {dict(result['errors'])}", flush=True)
            passed &= not result["errors"] and result["p95"] < 300
    return 0 if passed else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/api/v1")
    parser.add_argument("--concurrency", type=positive_int, default=50)
    parser.add_argument(
        "--duration",
        type=positive_int,
        default=30,
        help="seconds per endpoint",
    )
    args = parser.parse_args()
    token = os.environ.get("LOADTEST_TOKEN")
    if not token:
        parser.error("set LOADTEST_TOKEN with alarm:read and event:read permissions")
    try:
        return asyncio.run(run(args, token))
    except (httpx.HTTPError, ValueError) as exc:
        parser.exit(2, f"Endpoint preflight failed: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
