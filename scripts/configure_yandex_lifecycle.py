#!/usr/bin/env python3
"""Merge and verify a 30-day lifecycle rule for OfficeFlow's Yandex backups."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

RULE_ID = "officeflow-backups-retention-30-days"


def normalized_prefix(value: str) -> str:
    prefix = value.strip().strip("/")
    if not prefix or any(part in {".", ".."} for part in prefix.split("/")):
        raise ValueError("Backup prefix must be a non-empty safe object-key prefix")
    return prefix + "/"


def build_lifecycle(
    existing: dict[str, Any],
    prefix: str,
    versioning: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Preserve unrelated bucket rules and replace only OfficeFlow's own rule."""
    if not isinstance(existing, dict):
        raise ValueError("Existing lifecycle configuration must be a JSON object")
    rules = existing.get("Rules", [])
    if not isinstance(rules, list):
        raise ValueError("Existing lifecycle Rules must be a list")
    if any(not isinstance(item, dict) for item in rules):
        raise ValueError("Every existing lifecycle rule must be an object")

    rule: dict[str, Any] = {
        "ID": RULE_ID,
        "Status": "Enabled",
        "Filter": {"Prefix": normalized_prefix(prefix)},
        "Expiration": {"Days": 30},
        "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 7},
    }
    versioning_status = (versioning or {}).get("Status")
    if versioning_status in {"Enabled", "Suspended"}:
        rule["NoncurrentVersionExpiration"] = {"NoncurrentDays": 30}

    merged = [item for item in rules if item.get("ID") != RULE_ID]
    if len(merged) >= 1000:
        raise ValueError("Bucket already has 1000 lifecycle rules; cannot add OfficeFlow rule")
    merged.append(rule)

    result = dict(existing)
    result["Rules"] = merged
    return result


def verify_lifecycle(
    actual: dict[str, Any],
    prefix: str,
    versioning: dict[str, Any] | None = None,
) -> None:
    rules = actual.get("Rules", [])
    matches = [rule for rule in rules if rule.get("ID") == RULE_ID]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one lifecycle rule {RULE_ID}")
    rule = matches[0]
    expected_prefix = normalized_prefix(prefix)
    if rule.get("Status") != "Enabled":
        raise ValueError("OfficeFlow lifecycle rule is not Enabled")
    if rule.get("Filter", {}).get("Prefix") != expected_prefix:
        raise ValueError("OfficeFlow lifecycle rule has an unexpected prefix")
    if rule.get("Expiration", {}).get("Days") != 30:
        raise ValueError("OfficeFlow lifecycle expiration is not 30 days")
    if rule.get("AbortIncompleteMultipartUpload", {}).get("DaysAfterInitiation") != 7:
        raise ValueError("Incomplete multipart uploads are not set to expire after 7 days")
    versioning_status = (versioning or {}).get("Status")
    if versioning_status in {"Enabled", "Suspended"}:
        if rule.get("NoncurrentVersionExpiration", {}).get("NoncurrentDays") != 30:
            raise ValueError("Noncurrent object versions are not set to expire after 30 days")


def read_json(path: str) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--versioning", required=True, help="Path to get-bucket-versioning JSON")
    parser.add_argument("--current", help="Path to current get-bucket-lifecycle-configuration JSON")
    parser.add_argument("--output", help="Write merged lifecycle JSON to this path")
    parser.add_argument("--verify", help="Verify a retrieved lifecycle JSON instead of building it")
    args = parser.parse_args()

    versioning = read_json(args.versioning)
    if args.verify:
        verify_lifecycle(read_json(args.verify), args.prefix, versioning)
        print("Yandex Object Storage lifecycle verified: OfficeFlow daily backups expire after 30 days.")
        return 0

    if not args.current or not args.output:
        parser.error("--current and --output are required when --verify is not used")
    current = read_json(args.current)
    desired = build_lifecycle(current, args.prefix, versioning)
    Path(args.output).write_text(json.dumps(desired, indent=2) + chr(10), encoding="utf-8")
    print(f"Prepared lifecycle configuration; preserved {len(desired['Rules']) - 1} unrelated rule(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
