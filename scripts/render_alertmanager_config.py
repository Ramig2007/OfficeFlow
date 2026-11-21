#!/usr/bin/env python3
"""Render a safe Alertmanager config for optional Telegram and HTTPS webhook receivers."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlsplit


def yaml_string(value: str) -> str:
    """JSON strings are valid YAML double-quoted scalars."""
    return json.dumps(value, ensure_ascii=False)


def render_config(
    webhook_url: str,
    bearer_token: str,
    telegram_bot_token: str = "",
    telegram_chat_id: str = "",
) -> str:
    webhook_url = webhook_url.strip()
    bearer_token = bearer_token.strip()
    telegram_bot_token = telegram_bot_token.strip()
    telegram_chat_id = telegram_chat_id.strip()

    if bearer_token and not webhook_url:
        raise ValueError("ALERTMANAGER_WEBHOOK_BEARER_TOKEN requires ALERTMANAGER_WEBHOOK_URL")

    if webhook_url:
        parsed = urlsplit(webhook_url)
        try:
            _ = parsed.port
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

    telegram_enabled = bool(telegram_bot_token or telegram_chat_id)
    if telegram_enabled:
        if not telegram_bot_token or not telegram_chat_id:
            raise ValueError(
                "ALERTMANAGER_TELEGRAM_BOT_TOKEN and ALERTMANAGER_TELEGRAM_CHAT_ID must be set together"
            )
        if any(char in telegram_bot_token for char in "\r\n\t"):
            raise ValueError("ALERTMANAGER_TELEGRAM_BOT_TOKEN must not contain whitespace control characters")
        try:
            chat_id = int(telegram_chat_id)
        except ValueError as exc:
            raise ValueError("ALERTMANAGER_TELEGRAM_CHAT_ID must be an integer") from exc
        if chat_id == 0:
            raise ValueError("ALERTMANAGER_TELEGRAM_CHAT_ID must not be zero")

    if not webhook_url and not telegram_enabled:
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
# No receiver is configured: alerts are evaluated but no human notification is delivered.
"""

    lines = [
        "global:",
        "  resolve_timeout: 5m",
        "route:",
        "  receiver: officeflow-notifications",
        '  group_by: ["alertname"]',
        "  group_wait: 10s",
        "  group_interval: 5m",
        "  repeat_interval: 4h",
        "receivers:",
        "  - name: officeflow-notifications",
    ]

    if telegram_enabled:
        lines.extend(
            [
                "    telegram_configs:",
                f"      - bot_token: {yaml_string(telegram_bot_token)}",
                f"        chat_id: {chat_id}",
                "        send_resolved: true",
                "        parse_mode: HTML",
            ]
        )

    if webhook_url:
        lines.extend(
            [
                "    webhook_configs:",
                f"      - url: {yaml_string(webhook_url)}",
                "        send_resolved: true",
            ]
        )
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="/out/alertmanager.yml")
    args = parser.parse_args()

    try:
        config = render_config(
            os.environ.get("ALERTMANAGER_WEBHOOK_URL", ""),
            os.environ.get("ALERTMANAGER_WEBHOOK_BEARER_TOKEN", ""),
            os.environ.get("ALERTMANAGER_TELEGRAM_BOT_TOKEN", ""),
            os.environ.get("ALERTMANAGER_TELEGRAM_CHAT_ID", ""),
        )
    except ValueError as exc:
        parser.error(str(exc))

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(config, encoding="utf-8")
    mode = []
    if os.environ.get("ALERTMANAGER_TELEGRAM_BOT_TOKEN", "").strip():
        mode.append("Telegram enabled")
    if os.environ.get("ALERTMANAGER_WEBHOOK_URL", "").strip():
        mode.append("HTTPS webhook enabled")
    print(f"Alertmanager config generated: {', '.join(mode) if mode else 'null receiver (notifications disabled)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
