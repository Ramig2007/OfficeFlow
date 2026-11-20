"""OfficeFlow: Chromium acceptance checks against an isolated demo stack.

The CI run creates only disposable demo data. It exercises real browser forms,
then the Compose stack is destroyed by the workflow's final teardown step.
"""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path
from secrets import randbelow, token_hex

from playwright.sync_api import Page, sync_playwright

BASE_URL = os.environ.get("BASE_URL", "http://proxy").rstrip("/")
PASSWORD = os.environ.get("K6_PASSWORD", "")
ARTIFACTS = Path("/tests/artifacts")


def open_ok(page: Page, path: str) -> None:
    response = page.goto(f"{BASE_URL}{path}", wait_until="domcontentloaded", timeout=20000)
    assert response is not None, f"No response for {path}"
    assert response.status == 200, f"GET {path}: expected 200, got {response.status}"
    assert "/accounts/login/" not in page.url, f"Unexpected login redirect on {path}"


def login(page: Page, username: str) -> None:
    response = page.goto(f"{BASE_URL}/accounts/login/", wait_until="domcontentloaded")
    assert response is not None and response.status == 200, "Login page is unavailable"
    page.locator('input[name="username"]').fill(username)
    page.locator('input[name="password"]').fill(PASSWORD)
    page.get_by_role("button", name="Войти в OfficeFlow").click()
    page.locator(".app-shell").wait_for(timeout=10000)
    assert "/accounts/login/" not in page.url, f"Login failed for {username}"


def create_booking(page: Page, room_name: str, title: str, day: date, hour: int) -> None:
    open_ok(page, "/bookings/new/")
    page.locator('select[name="room"]').select_option(label=room_name)
    page.locator('input[name="title"]').fill(title)
    page.locator('input[name="starts_at_0"]').fill(day.isoformat())
    page.locator('select[name="starts_at_1"]').select_option(f"{hour:02d}:00")
    page.locator('input[name="ends_at_0"]').fill(day.isoformat())
    page.locator('select[name="ends_at_1"]').select_option(f"{hour + 1:02d}:00")
    page.get_by_role("button", name="Забронировать время").click()
    page.wait_for_url("**/my-bookings/", timeout=15000)
    page.locator("tr", has_text=title).wait_for(timeout=10000)


def run() -> int:
    if not PASSWORD:
        print("ERROR: K6_PASSWORD is missing in the browser container environment.", file=sys.stderr)
        return 2

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    steps: list[str] = []
    manager_context = None

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

            login(page, "employee")
            steps.append("Employee logged in through real HTML form")
            print("PASS 2: employee browser login")

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
            assert page.locator(".room-card").count() >= 1, "No rooms in demo data"
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
            assert width["content"] <= width["viewport"] + 2, (
                f"Horizontal overflow at 375px: scrollWidth={width['content']}px"
            )
            steps.append("Mobile catalogue renders without horizontal overflow at 375px")
            print("PASS 9: mobile catalogue (375px)")

            page.set_viewport_size({"width": 768, "height": 1024})
            open_ok(page, "/rooms/")
            assert page.locator(".room-card").first.is_visible()
            page.screenshot(path=str(ARTIFACTS / "rooms-tablet.png"), full_page=True)
            width = page.evaluate(
                "({viewport: window.innerWidth, content: document.documentElement.scrollWidth})"
            )
            assert width["content"] <= width["viewport"] + 2, (
                f"Horizontal overflow at 768px: scrollWidth={width['content']}px"
            )
            steps.append("Tablet catalogue renders without horizontal overflow at 768px")
            print("PASS 10: tablet catalogue (768px)")

            # Use a random, safely-future slot so reruns do not collide with demo fixtures.
            test_day = date.today() + timedelta(days=30 + randbelow(100))
            test_hour = 9 + randbelow(8)
            token = token_hex(3)
            booking_title = f"CI lifecycle {token}"
            edited_title = f"CI lifecycle edited {token}"
            create_booking(page, "Маяк", booking_title, test_day, test_hour)
            steps.append("Employee creates a standard booking through the browser form")
            print("PASS 11: booking create")

            booking_row = page.locator("tr", has_text=booking_title)
            booking_row.get_by_role("link", name="Изменить").click()
            page.locator('input[name="title"]').fill(edited_title)
            page.get_by_role("button", name="Сохранить изменения").click()
            page.wait_for_url("**/my-bookings/", timeout=15000)
            edited_row = page.locator("tr", has_text=edited_title)
            edited_row.wait_for(timeout=10000)
            steps.append("Employee edits an existing booking through the browser form")
            print("PASS 12: booking edit")

            page.on("dialog", lambda dialog: dialog.accept())
            edited_row.locator('form[action*="/cancel/"] button').click()
            page.locator(".flash-stack").get_by_text("Бронирование отменено").wait_for(timeout=10000)
            cancelled_row = page.locator("tr", has_text=edited_title)
            assert "Отменено" in cancelled_row.inner_text(), "Booking was not marked cancelled"
            steps.append("Employee cancels the edited booking through the browser form")
            print("PASS 13: booking cancel")

            vip_approved_title = f"CI VIP approved {token}"
            vip_rejected_title = f"CI VIP rejected {token}"
            create_booking(page, "Орбита", vip_approved_title, test_day, 12)
            create_booking(page, "Орбита", vip_rejected_title, test_day, 14)
            steps.append("Employee submits two VIP requests that start as pending")
            print("PASS 14: VIP requests submitted")

            manager_context = browser.new_context(
                viewport={"width": 1440, "height": 900},
                locale="ru-RU",
            )
            manager_page = manager_context.new_page()
            login(manager_page, "manager")

            for path in ("/approvals/", "/control/rooms/", "/control/users/", "/reports/"):
                open_ok(manager_page, path)
            steps.append("Manager can open approvals, room management, user management and reports")
            print("PASS 15: administrator pages")

            open_ok(manager_page, "/approvals/")
            approve_row = manager_page.locator("tr", has_text=vip_approved_title)
            approve_row.locator('form[action$="/approve/"] button').click()
            manager_page.locator(".flash-stack").get_by_text("Решение сохранено").wait_for(timeout=10000)
            steps.append("Manager approves a VIP request through the browser")
            print("PASS 16: VIP approval")

            open_ok(manager_page, "/approvals/")
            reject_row = manager_page.locator("tr", has_text=vip_rejected_title)
            reject_row.locator('input[name="reason"]').fill("Тестовая причина отказа")
            reject_row.locator('form[action$="/reject/"] button').click()
            manager_page.locator(".flash-stack").get_by_text("Решение сохранено").wait_for(timeout=10000)
            steps.append("Manager rejects a VIP request with a required reason")
            print("PASS 17: VIP rejection")

            # Verify the resulting state from the employee's own account.
            open_ok(page, "/my-bookings/")
            approved_row = page.locator("tr", has_text=vip_approved_title)
            rejected_row = page.locator("tr", has_text=vip_rejected_title)
            assert "Подтверждено" in approved_row.inner_text(), "Approved VIP booking is not confirmed"
            assert "Отклонено" in rejected_row.inner_text(), "Rejected VIP booking has the wrong status"
            assert "Тестовая причина отказа" in rejected_row.inner_text(), "Rejection reason is not visible to the owner"
            steps.append("Employee sees the final VIP decisions and rejection reason")
            print("PASS 18: VIP decision visibility")

            # Exercise room create, edit and deactivate on disposable CI data.
            room_name = f"CI Room {token}"
            open_ok(manager_page, "/control/rooms/new/")
            manager_page.locator('input[name="name"]').fill(room_name)
            manager_page.locator('input[name="floor"]').fill("1")
            manager_page.locator('input[name="location"]').fill("CI test environment")
            manager_page.locator('input[name="capacity"]').fill("4")
            manager_page.locator('textarea[name="description"]').fill("Temporary room created by browser CI")
            manager_page.locator('input[name="equipment"]').fill("Display")
            manager_page.get_by_role("button", name="Сохранить переговорную").click()
            manager_page.wait_for_url("**/control/rooms/", timeout=15000)
            room_row = manager_page.locator("tr", has_text=room_name)
            room_row.wait_for(timeout=10000)
            steps.append("Manager creates a room through the browser")
            print("PASS 19: room create")

            room_row.locator('a[href*="/control/rooms/"]').click()
            manager_page.locator('input[name="capacity"]').fill("5")
            manager_page.get_by_role("button", name="Сохранить переговорную").click()
            manager_page.wait_for_url("**/control/rooms/", timeout=15000)
            room_row = manager_page.locator("tr", has_text=room_name)
            assert "5" in room_row.inner_text(), "Room capacity was not updated"
            steps.append("Manager edits room details through the browser")
            print("PASS 20: room edit")

            room_row.locator('a[href*="/control/rooms/"]').click()
            active_checkbox = manager_page.locator('input[name="is_active"]')
            if active_checkbox.is_checked():
                active_checkbox.uncheck()
            manager_page.get_by_role("button", name="Сохранить переговорную").click()
            manager_page.wait_for_url("**/control/rooms/", timeout=15000)
            room_row = manager_page.locator("tr", has_text=room_name)
            assert "Отключена" in room_row.inner_text(), "Room was not deactivated"
            steps.append("Manager deactivates a room without deleting booking history")
            print("PASS 21: room deactivate")

            print(f"RESULT: {len(steps)}/{len(steps)} browser acceptance checks passed")
            print(
                "Disposable CI data only: one standard booking was edited and cancelled; "
                "two VIP requests were approved/rejected; one temporary room was created, edited and deactivated."
            )
            return 0
        except Exception as exc:
            try:
                page.screenshot(path=str(ARTIFACTS / "failure.png"), full_page=True)
            except Exception:
                pass
            print(f"FAIL after {len(steps)} passing checks: {type(exc).__name__}: {exc}", file=sys.stderr)
            print("Failure screenshot (if available): /tests/artifacts/failure.png", file=sys.stderr)
            return 1
        finally:
            if manager_context is not None:
                manager_context.close()
            context.close()
            browser.close()


if __name__ == "__main__":
    sys.exit(run())
