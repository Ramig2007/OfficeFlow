#!/usr/bin/env python3
"""Probe OfficeFlow readiness from an independent monitoring host and append JSONL."""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen


def build_probe_url(base_url: str, *, allow_http: bool = False) -> str:
    base_url = base_url.strip()
    parsed = urlsplit(base_url)
    allowed_schemes = {"https", "http"} if allow_http else {"https"}
    if (
        parsed.scheme not in allowed_schemes
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        expected = "HTTP(S)" if allow_http else "HTTPS"
        raise ValueError(
            f"OFFICEFLOW_URL must be a valid {expected} base URL without credentials, query, or fragment"
        )
    try:
        _ = parsed.port
    except ValueError as exc:
        raise ValueError("OFFICEFLOW_URL contains an invalid port") from exc
    return urljoin(base_url.rstrip("/") + "/", "health/ready/")


def probe(url: str, timeout: float) -> dict:
    started = time.monotonic()
    status_code = None
    error = None
    try:
        request = Request(
            url,
            headers={
                "User-Agent": "OfficeFlow-Uptime-Probe/1.0",
                "Accept": "application/json",
                "Cache-Control": "no-cache",
            },
        )
        with urlopen(request, timeout=timeout) as response:
            status_code = response.status
            response.read(1)
    except HTTPError as exc:
        status_code = exc.code
        error = f"HTTP {exc.code}"
    except (URLError, TimeoutError, OSError) as exc:
        error = str(getattr(exc, "reason", exc))[:300]

    latency_ms = round((time.monotonic() - started) * 1000, 2)
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "status_code": status_code,
        "latency_ms": latency_ms,
        "success": status_code == 200,
        "error": error,
    }


def append_record(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=os.getenv("OFFICEFLOW_URL", ""))
    parser.add_argument("--log-file", default="probes.jsonl")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--allow-http", action="store_true", help="Allow HTTP only for local testing")
    args = parser.parse_args()

    if not args.url:
        parser.error("Set OFFICEFLOW_URL or pass --url")
    if not 0 < args.timeout <= 60:
        parser.error("--timeout must be greater than 0 and at most 60 seconds")

    try:
        url = build_probe_url(args.url, allow_http=args.allow_http)
    except ValueError as exc:
        parser.error(str(exc))

    record = probe(url, args.timeout)
    record["url"] = url
    append_record(Path(args.log_file), record)
    print(json.dumps(record, ensure_ascii=False))

    return 0 if record["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
