#!/usr/bin/env python3
"""Run a small, bounded HTTP smoke load against an approved endpoint."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Result:
    status: int | None
    elapsed_ms: float
    error: str | None = None


def bounded_int(minimum: int, maximum: int):
    def parse(value: str) -> int:
        number = int(value)
        if not minimum <= number <= maximum:
            raise argparse.ArgumentTypeError(
                f"must be between {minimum} and {maximum}"
            )
        return number

    return parse


def percentile(values: list[float], percentage: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * percentage) - 1)
    return ordered[index]


def validate_target(url: str, allow_remote: bool) -> str:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("target must be an absolute HTTP or HTTPS URL")
    local_hosts = {"localhost", "127.0.0.1", "::1"}
    if not allow_remote and parsed.hostname.lower() not in local_hosts:
        raise ValueError(
            "remote targets require the explicit --allow-remote flag"
        )
    if parsed.username or parsed.password:
        raise ValueError("credentials must not be embedded in the target URL")
    return url


def request_once(url: str, timeout: float) -> Result:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "CodeLabX-load-smoke/1.0"},
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read(1024)
            status = response.status
        return Result(
            status=status,
            elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
        )
    except urllib.error.HTTPError as exc:
        return Result(
            status=exc.code,
            elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
            error=f"HTTP {exc.code}",
        )
    except Exception as exc:
        return Result(
            status=None,
            elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
            error=type(exc).__name__,
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a bounded smoke load; this is not a capacity benchmark."
    )
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8000/health/",
    )
    parser.add_argument(
        "--requests",
        type=bounded_int(1, 500),
        default=20,
    )
    parser.add_argument(
        "--concurrency",
        type=bounded_int(1, 50),
        default=4,
    )
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--max-p95-ms", type=float, default=1000.0)
    parser.add_argument("--allow-remote", action="store_true")
    args = parser.parse_args()

    if args.timeout <= 0 or args.max_p95_ms <= 0:
        parser.error("timeouts and latency budgets must be positive")
    try:
        target = validate_target(args.url, args.allow_remote)
    except ValueError as exc:
        parser.error(str(exc))

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=min(args.concurrency, args.requests)
    ) as executor:
        futures = [
            executor.submit(request_once, target, args.timeout)
            for _ in range(args.requests)
        ]
        results = [future.result() for future in futures]

    timings = [result.elapsed_ms for result in results]
    failures = [
        result
        for result in results
        if result.error is not None
        or result.status is None
        or not 200 <= result.status < 300
    ]
    summary = {
        "target": target,
        "requests": len(results),
        "failures": len(failures),
        "min_ms": min(timings),
        "median_ms": percentile(timings, 0.50),
        "p95_ms": percentile(timings, 0.95),
        "max_ms": max(timings),
        "budget_ms": args.max_p95_ms,
    }
    if failures:
        summary["failure_samples"] = [
            asdict(result) for result in failures[:5]
        ]
    print(json.dumps(summary, indent=2, sort_keys=True))

    return int(bool(failures) or summary["p95_ms"] > args.max_p95_ms)


if __name__ == "__main__":
    raise SystemExit(main())
