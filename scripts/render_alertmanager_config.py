#!/usr/bin/env python3
"""Render a safe Alertmanager config for an optional HTTPS webhook receiver."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlsplit


def yaml_string(value: str) -> str:
    """JSON strings are valid YAML double-quoted scalars."""
    return json.dumps(value, ensure_ascii=False)


def render_config(webhook_url: str, bearer_token: str) -> str:
    webhook_url = webhook_url.strip()
    bearer_token = bearer_token.strip()

    if bearer_token and not webhook_url:
        raise ValueError("ALERTMANAGER_WEBHOOK_BEARER_TOKEN requires ALERTMANAGER_WEBHOOK_URL")

    if webhook_url:
        parsed = urlsplit(webhook_url)
        try:
            parsed.port
        except ValueError as exc:
            raise ValueError("ALERTMANAGER_WEBHOOK_URL contains an invalid port") from exc
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.fragment
            or any(char in webhook_url for char in "\r\n\t")
        ):
            raise ValueError(
                "ALERTMANAGER_WEBHOOK_URL must be an HTTPS URL without embedded credentials or a fragment"
            )
        lines = [
            "global:",
            "  resolve_timeout: 5m",
            "route:",
            "  receiver: officeflow-webhook",
            '  group_by: ["alertname"]',
            "  group_wait: 10s",
            "  group_interval: 5m",
            "  repeat_interval: 4h",
            "receivers:",
            "  - name: officeflow-webhook",
            "    webhook_configs:",
            f"      - url: {yaml_string(webhook_url)}",
            "        send_resolved: true",
        ]
        if bearer_token:
            if any(char in bearer_token for char in "\r\n"):
                raise ValueError("ALERTMANAGER_WEBHOOK_BEARER_TOKEN must not contain line breaks")
            lines.extend(
                [
                    "        http_config:",
                    "          authorization:",
                    "            type: Bearer",
                    f"            credentials: {yaml_string(bearer_token)}",
                ]
            )
        return "\n".join(lines) + "\n"

    return """global:
  resolve_timeout: 5m
route:
  receiver: null-receiver
  group_by: ["alertname"]
  group_wait: 10s
  group_interval: 5m
  repeat_interval: 4h
receivers:
  - name: null-receiver
# No webhook is configured: alerts are evaluated but no human notification is delivered.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="/out/alertmanager.yml")
    args = parser.parse_args()

    try:
        config = render_config(
            os.environ.get("ALERTMANAGER_WEBHOOK_URL", ""),
            os.environ.get("ALERTMANAGER_WEBHOOK_BEARER_TOKEN", ""),
        )
    except ValueError as exc:
        parser.error(str(exc))

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(config, encoding="utf-8")
    mode = "HTTPS webhook enabled" if os.environ.get("ALERTMANAGER_WEBHOOK_URL", "").strip() else "null receiver (notifications disabled)"
    print(f"Alertmanager config generated: {mode}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
