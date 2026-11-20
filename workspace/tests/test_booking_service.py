from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, connections

from workspace.models import AuditEvent, Booking
from workspace.services import (
    BookingConflict, BookingStateError, cancel_booking, create_booking, review_booking,
    update_booking,
)

pytestmark = pytest.mark.django_db


def book(member, room, window, **overrides):
    start, end = window
    params = dict(actor=member, room_id=room.pk, title="Планирование", notes="", starts_at=start, ends_at=end)
    params.update(overrides)
    return create_booking(**params)


def test_standard_room_is_confirmed(member, room, window):
    item = book(member, room, window)
    assert item.status == Booking.Status.CONFIRMED
    assert item.creator == member
    assert AuditEvent.objects.filter(action="booking.created").exists()


def test_overlapping_reservations_are_rejected(member, second_member, room, window):
    book(member, room, window)
    with pytest.raises(BookingConflict):
        book(second_member, room, window, starts_at=window[0] + timedelta(hours=1), ends_at=window[1] + timedelta(hours=1))
    assert Booking.objects.filter(status=Booking.Status.CONFIRMED).count() == 1


def test_adjacent_time_slots_are_allowed(member, second_member, room, window):
    book(member, room, window)
    item = book(second_member, room, window, starts_at=window[1], ends_at=window[1] + timedelta(hours=1))
    assert item.status == Booking.Status.CONFIRMED


@pytest.mark.parametrize("hours", [0.5, 5, -1])
def test_duration_out_of_bounds(member, room, window, hours):
    with pytest.raises(ValidationError):
        book(member, room, window, ends_at=window[0] + timedelta(hours=hours))


def test_fractional_start_is_rejected(member, room, window):
    with pytest.raises(ValidationError):
        book(member, room, window, starts_at=window[0] + timedelta(minutes=15))


def test_past_booking_is_rejected(member, room, window):
    with pytest.raises(ValidationError):
        book(member, room, window, starts_at=window[0] - timedelta(days=30), ends_at=window[1] - timedelta(days=30))


def test_missing_title_is_rejected(member, room, window):
    with pytest.raises(ValidationError):
        book(member, room, window, title="   ")


def test_vip_requires_approval(member, manager, vip_room, window):
    item = book(member, vip_room, window)
    assert item.status == Booking.Status.PENDING
    approved = review_booking(actor=manager, booking_id=item.pk, approve=True)
    assert approved.status == Booking.Status.CONFIRMED
    assert approved.reviewed_by == manager


def test_pending_vip_reserves_the_slot(member, second_member, vip_room, window):
    book(member, vip_room, window)
    with pytest.raises(BookingConflict):
        book(second_member, vip_room, window)


def test_non_admin_cannot_approve(member, vip_room, window):
    item = book(member, vip_room, window)
    with pytest.raises(PermissionDenied):
        review_booking(actor=member, booking_id=item.pk, approve=True)


def test_rejection_requires_a_reason(member, manager, vip_room, window):
    item = book(member, vip_room, window)
    with pytest.raises(ValidationError):
        review_booking(actor=manager, booking_id=item.pk, approve=False)
    rejected = review_booking(actor=manager, booking_id=item.pk, approve=False, reason="Конференция")
    assert rejected.status == Booking.Status.REJECTED
    assert rejected.rejection_reason == "Конференция"


def test_review_twice_returns_conflict(member, manager, vip_room, window):
    item = book(member, vip_room, window)
    review_booking(actor=manager, booking_id=item.pk, approve=True)
    with pytest.raises(BookingStateError):
        review_booking(actor=manager, booking_id=item.pk, approve=False, reason="Повтор")


def test_cancelling_releases_slot(member, second_member, room, window):
    item = book(member, room, window)
    cancel_booking(actor=member, booking_id=item.pk)
    assert item.pk == Booking.objects.get(pk=item.pk).pk
    book(second_member, room, window)
    assert Booking.objects.count() == 2


def test_cannot_cancel_twice(member, room, window):
    item = book(member, room, window)
    cancel_booking(actor=member, booking_id=item.pk)
    with pytest.raises(BookingStateError):
        cancel_booking(actor=member, booking_id=item.pk)


def test_other_user_cannot_cancel(member, second_member, room, window):
    item = book(member, room, window)
    with pytest.raises(PermissionDenied):
        cancel_booking(actor=second_member, booking_id=item.pk)


def test_edit_booking_changes_period(member, room, window):
    item = book(member, room, window)
    changed = update_booking(
        actor=member, booking_id=item.pk, room_id=room.pk, title="Обновлено",
        notes="После обеда", starts_at=window[0] + timedelta(hours=2),
        ends_at=window[1] + timedelta(hours=2),
    )
    assert changed.title == "Обновлено"
    assert changed.notes == "После обеда"


def test_edit_to_vip_resets_status(member, room, vip_room, window):
    item = book(member, room, window)
    updated = update_booking(actor=member, booking_id=item.pk, room_id=vip_room.pk, title="VIP", notes="", starts_at=window[0], ends_at=window[1])
    assert updated.status == Booking.Status.PENDING


def test_edit_other_users_booking_forbidden(member, second_member, room, window):
    item = book(member, room, window)
    with pytest.raises(PermissionDenied):
        update_booking(actor=second_member, booking_id=item.pk, room_id=room.pk, title="Чужое", notes="", starts_at=window[0], ends_at=window[1])


def test_edit_to_occupied_period_fails(member, second_member, room, window):
    first = book(member, room, window)
    later = (window[1], window[1] + timedelta(hours=1))
    second = book(second_member, room, later)
    with pytest.raises(BookingConflict):
        update_booking(actor=member, booking_id=first.pk, room_id=room.pk, title="Нет", notes="", starts_at=later[0], ends_at=later[1])
    second.refresh_from_db()
    assert second.status == Booking.Status.CONFIRMED


@pytest.mark.django_db(transaction=True)
def test_concurrent_booking_only_one_wins():
    """Runs against a real PostgreSQL database in CI and Docker."""
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL required for concurrency integration")
    from django.utils import timezone
    from datetime import datetime, time

    from workspace.models import Room, User

    room = Room.objects.create(name="Гонка", slug="race", location="Тест")
    users = [User.objects.create_user(username=f"race{i}", password="StrongTestPass123!") for i in range(2)]
    date = timezone.localdate() + timedelta(days=2)
    start = timezone.make_aware(datetime.combine(date, time(10)))
    barrier = Barrier(2)

    def do_booking(user):
        # Each worker owns a thread-local Django connection. Close it explicitly
        # before and after the concurrent operation so pytest can drop its DB.
        connections.close_all()
        try:
            barrier.wait(timeout=10)
            create_booking(actor=user, room_id=room.pk, title="Синхронная бронь", notes="", starts_at=start, ends_at=start + timedelta(hours=1))
            return "created"
        except BookingConflict:
            return "conflict"
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(do_booking, user) for user in users]
        outcomes = [future.result(timeout=15) for future in futures]
    assert sorted(outcomes) == ["conflict", "created"]
    assert Booking.objects.filter(room=room, status=Booking.Status.CONFIRMED).count() == 1


def test_vip_toggle_with_future_booking_is_blocked(member, room, window):
    book(member, room, window)
    room.is_vip = True
    with pytest.raises(ValidationError):
        room.save(update_fields=["is_vip"])
    room.refresh_from_db()
    assert not room.is_vip
