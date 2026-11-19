from datetime import timedelta

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from workspace.models import Booking, User
from workspace.services import create_booking

pytestmark = pytest.mark.django_db


def test_registration_creates_member(client):
    response = client.post(reverse("register"), {
        "username": "new_person", "first_name": "Ольга", "email": "olga@example.test",
        "password1": "UnusualTestPass98!", "password2": "UnusualTestPass98!",
    })
    assert response.status_code == 302
    assert User.objects.get(username="new_person").role == User.Roles.MEMBER


def test_dashboard_and_schedule_require_login(client):
    assert client.get(reverse("dashboard")).status_code == 302
    assert client.get(reverse("schedule")).status_code == 302


def test_member_can_open_dashboard_and_schedule(client, member, room):
    client.force_login(member)
    assert client.get(reverse("dashboard")).status_code == 200
    page = client.get(reverse("schedule"))
    assert page.status_code == 200
    assert room.name.encode() in page.content


def test_member_cannot_use_admin_pages(client, member):
    client.force_login(member)
    for page in ("approvals", "manage-users", "reports", "manage-rooms"):
        assert client.get(reverse(page)).status_code == 403


def test_vip_booking_via_api_cannot_be_forced_confirmed(member, vip_room, window):
    api = APIClient()
    api.force_authenticate(user=member)
    start, end = window
    response = api.post("/api/v1/bookings/", {
        "room": vip_room.pk, "title": "Тест", "starts_at": start.isoformat(),
        "ends_at": end.isoformat(), "status": "confirmed", "creator": 999,
    }, format="json")
    assert response.status_code == 201
    item = Booking.objects.get(pk=response.data["id"])
    assert item.creator == member
    assert item.status == Booking.Status.PENDING


def test_booking_api_rejects_conflict(member, second_member, room, window):
    create_booking(actor=member, room_id=room.pk, title="Встреча", notes="", starts_at=window[0], ends_at=window[1])
    api = APIClient()
    api.force_authenticate(user=second_member)
    response = api.post("/api/v1/bookings/", {
        "room": room.pk, "title": "Конфликт", "starts_at": window[0].isoformat(),
        "ends_at": window[1].isoformat(),
    }, format="json")
    assert response.status_code == 409


def test_booking_api_cannot_mass_assign_status(member, room, window):
    item = create_booking(actor=member, room_id=room.pk, title="Встреча", notes="", starts_at=window[0], ends_at=window[1])
    api = APIClient()
    api.force_authenticate(user=member)
    response = api.patch(f"/api/v1/bookings/{item.pk}/", {"status": "rejected", "reviewed_by": 999}, format="json")
    assert response.status_code == 200
    item.refresh_from_db()
    assert item.status == Booking.Status.CONFIRMED
    assert item.reviewed_by is None


def test_member_cannot_access_other_users_booking(member, second_member, room, window):
    item = create_booking(actor=member, room_id=room.pk, title="Чужая", notes="", starts_at=window[0], ends_at=window[1])
    api = APIClient()
    api.force_authenticate(user=second_member)
    assert api.get(f"/api/v1/bookings/{item.pk}/").status_code == 404
    assert api.post(f"/api/v1/bookings/{item.pk}/cancel/").status_code == 404
    result = api.get("/api/v1/bookings/")
    assert result.status_code == 200
    assert result.data == []


def test_member_cannot_approve_vip(member, vip_room, window):
    item = create_booking(actor=member, room_id=vip_room.pk, title="VIP", notes="", starts_at=window[0], ends_at=window[1])
    api = APIClient()
    api.force_authenticate(user=member)
    assert api.post(f"/api/v1/bookings/{item.pk}/approve/").status_code == 403


def test_admin_can_approve_vip(member, manager, vip_room, window):
    item = create_booking(actor=member, room_id=vip_room.pk, title="VIP", notes="", starts_at=window[0], ends_at=window[1])
    api = APIClient()
    api.force_authenticate(user=manager)
    response = api.post(f"/api/v1/bookings/{item.pk}/approve/")
    assert response.status_code == 200
    assert response.data["status"] == Booking.Status.CONFIRMED


def test_member_cannot_edit_room(member, room):
    api = APIClient()
    api.force_authenticate(user=member)
    assert api.patch(f"/api/v1/rooms/{room.pk}/", {"capacity": 100}, format="json").status_code == 403
    room.refresh_from_db()
    assert room.capacity == 8


def test_admin_can_deactivate_room(manager, room):
    api = APIClient()
    api.force_authenticate(user=manager)
    assert api.delete(f"/api/v1/rooms/{room.pk}/").status_code == 204
    room.refresh_from_db()
    assert not room.is_active


def test_csv_export_filters_rooms_and_defuses_formulas(client, member, manager, room, vip_room, window):
    create_booking(actor=member, room_id=room.pk, title="=2+3", notes="", starts_at=window[0], ends_at=window[1])
    create_booking(actor=member, room_id=vip_room.pk, title="Другая", notes="", starts_at=window[0], ends_at=window[1])
    client.force_login(manager)
    response = client.get(reverse("report-csv"), {"room": room.pk})
    text = response.content.decode("utf-8-sig")
    assert response.status_code == 200
    assert "'=2+3" in text
    assert room.name in text
    assert vip_room.name not in text


def test_role_change_restricted_to_admin(member, manager):
    api = APIClient()
    api.force_authenticate(user=member)
    assert api.post(f"/api/v1/users/{member.pk}/change_role/", {"role": "admin"}).status_code == 403
    api.force_authenticate(user=manager)
    assert api.post(f"/api/v1/users/{member.pk}/change_role/", {"role": "admin"}).status_code == 200
    member.refresh_from_db()
    assert member.can_manage


def test_api_schedule_shows_active_bookings(member, room, window):
    create_booking(actor=member, room_id=room.pk, title="Команда", notes="", starts_at=window[0], ends_at=window[1])
    api = APIClient()
    api.force_authenticate(user=member)
    response = api.get("/api/v1/schedule/", {"date": window[0].date().isoformat()})
    assert response.status_code == 200
    assert len(response.data["bookings"]) == 1


def test_health_live_works_without_auth(client):
    assert client.get("/health/live/").status_code == 200


def test_logout_requires_post(client, member):
    client.force_login(member)
    assert client.get(reverse("logout")).status_code == 405
    assert client.post(reverse("logout")).status_code == 302


def test_standard_room_api_validation_rejects_invalid_hours(member, room, window):
    api = APIClient()
    api.force_authenticate(user=member)
    response = api.post("/api/v1/bookings/", {
        "room": room.pk, "title": "Долго", "starts_at": window[0].isoformat(),
        "ends_at": (window[0] + timedelta(hours=6)).isoformat(),
    }, format="json")
    assert response.status_code == 400
