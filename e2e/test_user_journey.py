"""Browser E2E on a pre-started demo environment (BASE_URL=http://localhost:8080)."""
import os
from datetime import timedelta

import pytest
from django.utils import timezone
from playwright.sync_api import sync_playwright

BASE_URL = os.getenv("BASE_URL", "http://localhost:8080")
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "DemoOnly!123")


@pytest.mark.e2e
def test_member_can_book_then_cancel():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"{BASE_URL}/accounts/login/")
        page.locator("input[name=username]").fill("employee")
        page.locator("input[name=password]").fill(DEMO_PASSWORD)
        page.get_by_role("button", name="Войти в OfficeFlow").click()
        page.get_by_role("link", name="Новое бронирование").click()
        page.locator("select[name=room]").select_option(label="Маяк")
        page.locator("input[name=title]").fill("Автоматический E2E тест")
        day = (timezone.localdate() + timedelta(days=14)).isoformat()
        page.locator("input[name=starts_at_0]").fill(day)
        page.locator("input[name=starts_at_1]").fill("10:00")
        page.locator("input[name=ends_at_0]").fill(day)
        page.locator("input[name=ends_at_1]").fill("11:00")
        page.get_by_role("button", name="Забронировать время").click()
        page.get_by_text("Автоматический E2E тест").wait_for()
        booking_row = page.locator("tr", has_text="Автоматический E2E тест")
        page.on("dialog", lambda dialog: dialog.accept())
        booking_row.get_by_role("button", name="Отменить").click()
        page.get_by_text("Бронирование отменено").wait_for()
        browser.close()
