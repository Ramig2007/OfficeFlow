from datetime import datetime, timedelta, timezone

import pytest

from scripts.uptime_probe import build_probe_url
from scripts.uptime_report import calculate_report


def make_full_window(successful=True):
    now = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)
    start = now - timedelta(days=1)
    records = [
        {
            "timestamp_utc": (start + timedelta(seconds=60 * index)).isoformat(),
            "success": successful,
        }
        for index in range(1441)
    ]
    return now, records


def test_build_probe_url_requires_https_by_default():
    assert build_probe_url("https://officeflow.example.test") == (
        "https://officeflow.example.test/health/ready/"
    )
    with pytest.raises(ValueError):
        build_probe_url("http://officeflow.example.test")


def test_build_probe_url_allows_http_only_when_explicitly_enabled():
    assert build_probe_url("http://127.0.0.1:8080", allow_http=True) == (
        "http://127.0.0.1:8080/health/ready/"
    )


def test_report_passes_with_complete_100_percent_availability():
    now, records = make_full_window()
    report = calculate_report(
        records,
        interval_seconds=60,
        window_days=1,
        target_percent=99.9,
        now=now,
    )
    assert report["status"] == "PASS"
    assert report["availability_percent"] == 100
    assert report["missing_slots"] == 0


def test_report_fails_when_two_one_minute_intervals_are_unavailable():
    now, records = make_full_window()
    records[100]["success"] = False
    records[101]["success"] = False
    report = calculate_report(
        records,
        interval_seconds=60,
        window_days=1,
        target_percent=99.9,
        now=now,
    )
    assert report["status"] == "FAIL"
    assert report["failed_slots"] == 2
    assert report["estimated_downtime_seconds"] == 120


def test_report_counts_missing_probe_intervals_as_unavailable():
    now, records = make_full_window()
    del records[100]
    del records[200]
    report = calculate_report(
        records,
        interval_seconds=60,
        window_days=1,
        target_percent=99.9,
        now=now,
    )
    assert report["status"] == "FAIL"
    assert report["missing_slots"] == 2


def test_report_requires_full_fresh_window():
    now, records = make_full_window()
    report = calculate_report(
        records[-60:],
        interval_seconds=60,
        window_days=1,
        target_percent=99.9,
        now=now,
    )
    assert report["status"] == "INSUFFICIENT_HISTORY"
