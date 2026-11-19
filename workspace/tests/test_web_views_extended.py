"""Additional web-flow regression tests for OfficeFlow.

These tests use the isolated pytest PostgreSQL test database, not demo data.
"""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from workspace.models import AuditEvent, Booking, Room, User
from workspace.services import create_booking

pytestmark = pytest.mark.django_db


def booking_fields(room, start, end, title="Тестовая встреча"):
    """Django SplitDateTimeField expects separate date and hour keys."""
    start = timezone.localtime(start)
    end = timezone.localtime(end)
    return {
        "room": str(room.pk),
        "title": title,
        "notes": "Проверка из браузера",
        "starts_at_0": start.date().isoformat(),
        "starts_at_1": start.strftime("%H:%M"),
        "ends_at_0": end.date().isoformat(),
        "ends_at_1": end.strftime("%H:%M"),
    }


def book(member, room, window, title="Встреча"):
    return create_booking(
        actor=member, room_id=room.pk, title=title, notes="",
        starts_at=window[0], ends_at=window[1],
    )


def test_rooms_filtering_and_detail_page(client, member, room, vip_room):
    client.force_login(member)
    assert client.get(reverse("rooms")).status_code == 200
    response = client.get(reverse("rooms"), {"vip": "1"})
    assert response.status_code == 200
    assert list(response.context["rooms"]) == [vip_room]
    response = client.get(reverse("rooms"), {"capacity": "8", "vip": "0"})
    assert list(response.context["rooms"]) == [room]
    assert reverse("room-detail", args=[room.slug]) == f"/rooms/{room.slug}/"
    assert client.get(reverse("room-detail", args=[room.slug])).status_code == 200
    assert client.get(reverse("room-detail", args=["missing-room"])).status_code == 404


def test_schedule_filters_week_day_and_room(client, member, room, window):
    client.force_login(member)
    book(member, room, window)
    date = window[0].date().isoformat()
    response = client.get(reverse("schedule"), {
        "week": date, "day": date, "room": str(room.pk),
    })
    assert response.status_code == 200
    assert len(response.context["matrix"]) == 1
    assert response.context["matrix"][0]["room"].pk == room.pk
    assert response.context["chosen_day"].isoformat() == date
    assert client.get(reverse("schedule"), {"week": "invalid", "room": "abc"}).status_code == 200


def test_booking_create_prefills_room_and_hour(client, member, room, window):
    client.force_login(member)
    response = client.get(reverse("booking-create"), {
        "room": str(room.pk), "date": window[0].date().isoformat(), "hour": "15",
    })
    assert response.status_code == 200
    assert response.context["form"].initial["room"] == str(room.pk)
    assert response.context["form"].initial["starts_at"].hour == 15
    assert client.get(reverse("booking-create"), {
        "date": window[0].date().isoformat(), "hour": "invalid",
    }).status_code == 200


def test_create_and_edit_booking_through_web_form(client, member, room, window):
    client.force_login(member)
    response = client.post(reverse("booking-create"), booking_fields(room, *window))
    assert response.status_code == 302
    item = Booking.objects.get(creator=member)
    assert item.status == Booking.Status.CONFIRMED
    assert client.get(reverse("booking-edit", args=[item.pk])).status_code == 200

    revised_start = window[0] + timedelta(hours=2)
    revised_end = window[1] + timedelta(hours=2)
    response = client.post(
        reverse("booking-edit", args=[item.pk]),
        booking_fields(room, revised_start, revised_end, title="Изменённая встреча"),
    )
    assert response.status_code == 302
    item.refresh_from_db()
    assert item.title == "Изменённая встреча"
    assert item.starts_at == revised_start
    assert AuditEvent.objects.filter(action="booking.created").exists()


def test_web_booking_conflict_is_shown_without_duplicate(client, member, second_member, room, window):
    book(member, room, window)
    client.force_login(second_member)
    response = client.post(
        reverse("booking-create"), booking_fields(room, *window, title="Повтор"),
    )
    assert response.status_code == 200
    assert "занята" in response.content.decode("utf-8")
    assert Booking.objects.count() == 1


def test_web_booking_invalid_form_and_wrong_owner(client, member, second_member, room, window):
    item = book(member, room, window)
    client.force_login(second_member)
    assert client.get(reverse("booking-edit", args=[item.pk])).status_code == 403
    response = client.post(reverse("booking-create"), {
        **booking_fields(room, *window), "starts_at_1": "not-a-time",
    })
    assert response.status_code == 200
    assert Booking.objects.count() == 1


def test_cancel_booking_from_web_and_prevent_repeat(client, member, room, window):
    item = book(member, room, window)
    client.force_login(member)
    assert reverse("booking-cancel", args=[item.pk]) == f"/bookings/{item.pk}/cancel/"
    url = reverse("booking-cancel", args=[item.pk])
    assert client.get(url).status_code == 405
    assert client.post(url).status_code == 302
    item.refresh_from_db()
    assert item.status == Booking.Status.CANCELLED
    assert client.post(url).status_code == 302
    assert client.get(reverse("booking-edit", args=[item.pk])).status_code == 302
    assert client.get(reverse("my-bookings")).status_code == 200
    assert client.post(reverse("booking-cancel", args=[999999])).status_code == 404


def test_vip_approval_web_flow_and_invalid_action(client, member, manager, vip_room, window):
    item = book(member, vip_room, window)
    client.force_login(manager)
    assert client.get(reverse("approvals")).status_code == 200
    assert client.get(reverse("approval-action", args=[item.pk, "approve"])).status_code == 405
    assert client.post(reverse("approval-action", args=[item.pk, "invalid"])).status_code == 404
    assert client.post(reverse("approval-action", args=[item.pk, "approve"])).status_code == 302
    item.refresh_from_db()
    assert item.status == Booking.Status.CONFIRMED
    # A second decision must not overwrite the prior approval.
    assert client.post(reverse("approval-action", args=[item.pk, "reject"]), {"reason": "Нет"}).status_code == 302
    item.refresh_from_db()
    assert item.status == Booking.Status.CONFIRMED


def test_vip_reject_needs_reason_in_web_flow(client, member, manager, vip_room, window):
    item = book(member, vip_room, window)
    client.force_login(manager)
    url = reverse("approval-action", args=[item.pk, "reject"])
    assert client.post(url, {"reason": ""}).status_code == 302
    item.refresh_from_db()
    assert item.status == Booking.Status.PENDING
    assert client.post(url, {"reason": "Комната закрыта"}).status_code == 302
    item.refresh_from_db()
    assert item.status == Booking.Status.REJECTED
    assert item.rejection_reason == "Комната закрыта"


def test_manager_can_create_and_update_room_from_web(client, manager):
    client.force_login(manager)
    assert client.get(reverse("manage-rooms")).status_code == 200
    assert client.get(reverse("manage-room-new")).status_code == 200
    data = {
        "name": "Тестовая комната", "floor": "2", "location": "Корпус B",
        "capacity": "6", "description": "Описание", "equipment": "Экран",
        "is_active": "on",
    }
    assert client.post(reverse("manage-room-new"), data).status_code == 302
    room = Room.objects.get(name="Тестовая комната")
    assert room.slug
    assert AuditEvent.objects.filter(action="room.created", target=str(room.pk)).exists()
    assert client.get(reverse("manage-room-edit", args=[room.pk])).status_code == 200
    assert client.post(reverse("manage-room-edit", args=[room.pk]), {
        **data, "name": "Комната после редактирования",
    }).status_code == 302
    room.refresh_from_db()
    assert room.name == "Комната после редактирования"
    assert AuditEvent.objects.filter(action="room.updated", target=str(room.pk)).exists()


def test_room_form_rejects_bad_input(client, manager):
    client.force_login(manager)
    response = client.post(reverse("manage-room-new"), {
        "name": "Неверная", "floor": "1", "location": "Этаж 1", "capacity": "0",
        "is_active": "on",
    })
    assert response.status_code == 200
    assert not Room.objects.filter(name="Неверная").exists()


def test_manager_role_change_validates_self_and_target(client, member, manager):
    client.force_login(manager)
    url = reverse("manage-users")
    assert client.get(url).status_code == 200
    assert client.post(url, {"user_id": str(member.pk), "role": "invalid"}).status_code == 302
    member.refresh_from_db()
    assert member.role == User.Roles.MEMBER
    assert client.post(url, {"user_id": str(manager.pk), "role": User.Roles.MEMBER}).status_code == 302
    manager.refresh_from_db()
    assert manager.role == User.Roles.ADMIN
    assert client.post(url, {"user_id": str(member.pk), "role": User.Roles.ADMIN}).status_code == 302
    member.refresh_from_db()
    assert member.role == User.Roles.ADMIN
    assert AuditEvent.objects.filter(action="user.role_changed", target=str(member.pk)).exists()


def test_reports_and_export_are_staff_only(client, member, manager, room, window):
    book(member, room, window)
    client.force_login(member)
    assert client.get(reverse("reports")).status_code == 403
    assert client.get(reverse("report-csv")).status_code == 403
    client.force_login(manager)
    assert client.get(reverse("reports"), {"room": str(room.pk)}).status_code == 200
    response = client.get(reverse("report-csv"), {"room": str(room.pk)})
    assert response.status_code == 200
    assert "text/csv" in response["Content-Type"]
    assert "Тестовая" not in response.content.decode("utf-8-sig")  # title is "Встреча"
    assert "Встреча" in response.content.decode("utf-8-sig")
    assert AuditEvent.objects.filter(action="report.exported").exists()


def test_profile_updates_and_rejects_duplicate_email(client, member, second_member):
    second_member.email = "second@example.test"
    second_member.save(update_fields=["email"])
    client.force_login(member)
    assert client.get(reverse("profile")).status_code == 200
    fields = {
        "first_name": "Новое имя", "last_name": "Фамилия",
        "email": "first@example.test", "department": "Разработка",
    }
    assert client.post(reverse("profile"), fields).status_code == 302
    member.refresh_from_db()
    assert member.department == "Разработка"
    assert AuditEvent.objects.filter(action="user.profile_updated").exists()
    response = client.post(reverse("profile"), {**fields, "email": "SECOND@example.test"})
    assert response.status_code == 200
    member.refresh_from_db()
    assert member.email == "first@example.test"


def test_registration_duplicate_email_and_logged_in_redirect(client, member):
    member.email = "registered@example.test"
    member.save(update_fields=["email"])
    response = client.post(reverse("register"), {
        "username": "another_user", "first_name": "Елена", "email": "REGISTERED@example.test",
        "password1": "UniqueStrongPass2026!", "password2": "UniqueStrongPass2026!",
    })
    assert response.status_code == 200
    assert not User.objects.filter(username="another_user").exists()
    client.force_login(member)
    assert client.get(reverse("register")).status_code == 302


def test_health_readiness_success_and_cache_failure(client, monkeypatch):
    class ReadyCache:
        def set(self, key, value, ttl):
            return None

        def get(self, key):
            return "ok"

    class BrokenCache(ReadyCache):
        def get(self, key):
            return None

    monkeypatch.setattr("workspace.views.cache", ReadyCache())
    assert client.get(reverse("health-ready")).status_code == 200
    monkeypatch.setattr("workspace.views.cache", BrokenCache())
    assert client.get(reverse("health-ready")).status_code == 503
