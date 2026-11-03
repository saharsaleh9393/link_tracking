"""Bounded local load probe. It creates real click events: use only a disposable campaign."""

import argparse
import math
import statistics
from concurrent.futures import ThreadPoolExecutor
from time import perf_counter

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="Your authorized local/staging tracking URL")
    parser.add_argument("--requests", type=int, default=500)
    parser.add_argument("--concurrency", type=int, default=10)
    args = parser.parse_args()
    if not 1 <= args.requests <= 100000 or not 1 <= args.concurrency <= 100:
        parser.error("Use 1–100000 requests and 1–100 concurrent requests")
    with httpx.Client(follow_redirects=False, timeout=10) as client:

        def click(_):
            start = perf_counter()
            try:
                status = client.get(
                    args.url, headers={"User-Agent": "TrackerLoadProbe/1.0"}
                ).status_code
            except httpx.HTTPError:
                status = 0
            return perf_counter() - start, status

        start = perf_counter()
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            results = list(pool.map(click, range(args.requests)))
        elapsed = perf_counter() - start
    durations = sorted(row[0] * 1000 for row in results)
    print(
        {
            "requests": len(results),
            "redirects": sum(row[1] == 302 for row in results),
            "requests_per_second": round(len(results) / elapsed, 1),
            "median_ms": round(statistics.median(durations), 2),
            "p95_ms": round(durations[math.ceil(len(durations) * 0.95) - 1], 2),
        }
    )
    if any(row[1] != 302 for row in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
