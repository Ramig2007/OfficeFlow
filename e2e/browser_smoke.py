"""OfficeFlow: read-only Chromium E2E smoke tests against an already running site.

Run from a container on `officeflow_internal`, with the user's existing K6_USERNAME
and K6_PASSWORD environment variables. Does not create, change or cancel bookings.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

BASE_URL = os.environ.get("BASE_URL", "http://proxy").rstrip("/")
USERNAME = os.environ.get("K6_USERNAME", "")
PASSWORD = os.environ.get("K6_PASSWORD", "")
ARTIFACTS = Path("/tests/artifacts")


def open_ok(page: Page, path: str) -> None:
    response = page.goto(f"{BASE_URL}{path}", wait_until="domcontentloaded", timeout=20000)
    assert response is not None, f"No response for {path}"
    assert response.status == 200, f"GET {path}: expected 200, got {response.status}"
    assert "/accounts/login/" not in page.url, f"Unexpected login redirect on {path}"


def run() -> int:
    if not USERNAME or not PASSWORD:
        print("ERROR: K6_USERNAME or K6_PASSWORD is missing in this terminal.", file=sys.stderr)
        return 2

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    steps: list[str] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="ru-RU",
        )
        page = context.new_page()
        try:
            response = page.goto(f"{BASE_URL}/", wait_until="domcontentloaded")
            assert response is not None
            assert "/accounts/login/" in page.url, "Anonymous visitor was not redirected to login"
            steps.append("Anonymous visitor redirected to login")
            print("PASS 1: anonymous redirect")

            page.locator('input[name="username"]').fill(USERNAME)
            page.locator('input[name="password"]').fill(PASSWORD)
            page.locator('form button[type="submit"]').click()
            try:
                page.locator(".app-shell").wait_for(timeout=10000)
            except Exception as exc:
                errors = page.locator(".field-errors").all_inner_texts()
                raise AssertionError(f"Browser login failed; visible form errors: {errors}") from exc
            assert "/accounts/login/" not in page.url, "Login form was shown again"
            steps.append("Employee logged in through real HTML form")
            print("PASS 2: browser login")

            open_ok(page, "/")
            assert page.locator(".stat-grid .stat-card").count() >= 1
            page.screenshot(path=str(ARTIFACTS / "dashboard-desktop.png"), full_page=True)
            steps.append("Dashboard loads and displays summary cards")
            print("PASS 3: dashboard")

            open_ok(page, "/rooms/")
            assert page.locator(".room-card").count() >= 1, "No rooms in demo data"
            page.locator(".room-card .room-actions a.btn-light").first.click()
            assert "/api/" not in page.url, "Room detail opened the API instead of HTML"
            assert "/rooms/" in page.url and page.url.rstrip("/") != f"{BASE_URL}/rooms"
            assert page.locator(".detail-panel").is_visible(), "Room detail template did not render"
            steps.append("Rooms catalogue -> actual HTML room detail")
            print("PASS 4: room detail navigation")

            open_ok(page, "/rooms/?vip=1")
            assert page.locator(".room-card").count() >= 1, "No VIP rooms in demo data"
            assert page.locator(".room-card .vip-tag").count() >= 1, "VIP filter produced non-VIP cards"
            steps.append("VIP room filter")
            print("PASS 5: room filter")

            open_ok(page, "/schedule/")
            assert page.locator(".page-heading h1").count() == 1
            steps.append("Weekly schedule")
            print("PASS 6: schedule")

            open_ok(page, "/my-bookings/")
            assert page.locator(".data-table").count() == 1
            steps.append("Personal bookings history")
            print("PASS 7: bookings history")

            approvals = context.request.get(f"{BASE_URL}/approvals/")
            users_api = context.request.get(f"{BASE_URL}/api/v1/users/")
            assert approvals.status == 403, f"Employee approvals access: {approvals.status} (expected 403)"
            assert users_api.status == 403, f"Employee users API access: {users_api.status} (expected 403)"
            steps.append("Employee denied access to admin UI and users API")
            print("PASS 8: permissions (HTTP 403)")

            page.set_viewport_size({"width": 375, "height": 812})
            open_ok(page, "/rooms/")
            assert page.locator(".room-card").first.is_visible()
            page.screenshot(path=str(ARTIFACTS / "rooms-mobile.png"), full_page=True)
            width = page.evaluate(
                "({viewport: window.innerWidth, content: document.documentElement.scrollWidth})"
            )
            if width["content"] > width["viewport"] + 2:
                print(
                    f"WARNING: possible horizontal overflow at 375px: "
                    f"scrollWidth={width['content']}px"
                )
            steps.append("Mobile catalogue renders at 375px")
            print("PASS 9: mobile catalogue")

            print(f"RESULT: {len(steps)}/{len(steps)} browser checks passed")
            print("Screenshots: e2e/artifacts/dashboard-desktop.png, e2e/artifacts/rooms-mobile.png")
            print("No bookings or users were modified.")
            return 0
        except Exception as exc:
            try:
                page.screenshot(path=str(ARTIFACTS / "failure.png"), full_page=True)
            except Exception:
                pass
            print(f"FAIL after {len(steps)} passing checks: {type(exc).__name__}: {exc}", file=sys.stderr)
            print("Failure screenshot (if available): e2e/artifacts/failure.png", file=sys.stderr)
            return 1
        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    sys.exit(run())
