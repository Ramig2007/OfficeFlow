#!/usr/bin/env python3
"""Calculate conservative rolling availability from OfficeFlow JSONL probe records."""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path


def parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"Timestamp must include a timezone: {value}")
    return parsed.astimezone(timezone.utc)


def calculate_report(
    records: list[dict],
    *,
    interval_seconds: int = 60,
    window_days: int = 30,
    target_percent: float = 99.9,
    now: datetime | None = None,
    max_age_seconds: int = 180,
) -> dict:
    if interval_seconds < 1 or window_days < 1:
        raise ValueError("interval_seconds and window_days must be positive")
    if not 0 < target_percent <= 100:
        raise ValueError("target_percent must be greater than 0 and at most 100")
    if not records:
        return {"status": "INSUFFICIENT_HISTORY", "message": "No probe records were found."}

    parsed = []
    for record in records:
        parsed.append((parse_timestamp(record["timestamp_utc"]), bool(record["success"])))
    parsed.sort(key=lambda item: item[0])

    current_time = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    latest = parsed[-1][0]
    window_seconds = window_days * 24 * 60 * 60
    coverage_seconds = (latest - parsed[0][0]).total_seconds()
    coverage_days = coverage_seconds / 86400
    latest_age_seconds = max(0, (current_time - latest).total_seconds())

    base = {
        "target_percent": target_percent,
        "window_days": window_days,
        "interval_seconds": interval_seconds,
        "coverage_days": round(coverage_days, 3),
        "latest_probe_age_seconds": round(latest_age_seconds, 1),
        "first_probe_utc": parsed[0][0].isoformat(),
        "last_probe_utc": latest.isoformat(),
        "records_read": len(parsed),
    }

    if coverage_seconds < window_seconds - interval_seconds or latest_age_seconds > max_age_seconds:
        return {
            **base,
            "status": "INSUFFICIENT_HISTORY",
            "message": (
                f"Need at least {window_days} days of fresh probe history; "
                f"observed {coverage_days:.2f} days and latest sample age {latest_age_seconds:.0f}s."
            ),
        }

    window_start = latest - timedelta(seconds=window_seconds)
    expected_slots = math.floor(window_seconds / interval_seconds) + 1
    slot_results: dict[int, bool] = {}
    samples_in_window = 0

    for timestamp, success in parsed:
        offset = (timestamp - window_start).total_seconds()
        if 0 <= offset <= window_seconds + interval_seconds / 2:
            slot = round(offset / interval_seconds)
            if 0 <= slot < expected_slots:
                samples_in_window += 1
                # Conservative handling: any failed sample makes its interval unavailable.
                slot_results[slot] = slot_results.get(slot, True) and success

    available_slots = sum(1 for success in slot_results.values() if success)
    missing_slots = expected_slots - len(slot_results)
    failed_slots = sum(1 for success in slot_results.values() if not success)
    unavailable_slots = expected_slots - available_slots
    availability = available_slots / expected_slots * 100
    estimated_downtime_seconds = unavailable_slots * interval_seconds
    status = "PASS" if availability >= target_percent else "FAIL"

    return {
        **base,
        "status": status,
        "availability_percent": round(availability, 5),
        "expected_probe_slots": expected_slots,
        "samples_in_window": samples_in_window,
        "observed_slots": len(slot_results),
        "successful_slots": available_slots,
        "failed_slots": failed_slots,
        "missing_slots": missing_slots,
        "unavailable_slots": unavailable_slots,
        "estimated_downtime_seconds": estimated_downtime_seconds,
        "estimated_downtime_minutes": round(estimated_downtime_seconds / 60, 2),
        "message": (
            f"Measured availability {availability:.5f}% "
            f"({'meets' if status == 'PASS' else 'does not meet'} {target_percent:.3f}% target). "
            "Missing probe intervals are counted as unavailable."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log_file", type=Path)
    parser.add_argument("--interval-seconds", type=int, default=60)
    parser.add_argument("--window-days", type=int, default=30)
    parser.add_argument("--target-percent", type=float, default=99.9)
    parser.add_argument("--max-age-seconds", type=int, default=180)
    args = parser.parse_args()

    if not args.log_file.is_file():
        parser.error(f"Probe log does not exist: {args.log_file}")

    records = []
    with args.log_file.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if line.strip():
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    parser.error(f"Invalid JSON on line {line_number}: {exc}")

    result = calculate_report(
        records,
        interval_seconds=args.interval_seconds,
        window_days=args.window_days,
        target_percent=args.target_percent,
        max_age_seconds=args.max_age_seconds,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] == "INSUFFICIENT_HISTORY":
        return 2
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
