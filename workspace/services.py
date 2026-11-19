"""Single entry point for booking state transitions across UI and REST API."""

import logging
from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from workspace.models import AuditEvent, Booking, Room

logger = logging.getLogger("workspace")


class BookingConflict(Exception):
    """The selected room/time is no longer available."""


class BookingStateError(Exception):
    """An invalid booking state transition was requested."""


def audit(actor, action, target, **detail):
    AuditEvent.objects.create(actor=actor, action=action, target=str(target), detail=detail)
    logger.info("actor=%s action=%s target=%s", getattr(actor, "pk", None), action, target)


def _validate_time(start, end):
    if not start or not end or timezone.is_naive(start) or timezone.is_naive(end):
        raise ValidationError("Укажите корректное время с часовым поясом.")
    duration = end - start
    if duration < timedelta(hours=1) or duration > timedelta(hours=4):
        raise ValidationError("Продолжительность бронирования — от 1 до 4 часов.")
    local_start = timezone.localtime(start)
    local_end = timezone.localtime(end)
    if any((local_start.minute, local_start.second, local_start.microsecond,
            local_end.minute, local_end.second, local_end.microsecond)):
        raise ValidationError("Начало и окончание должны приходиться на целый час.")
    if start < timezone.now() - timedelta(seconds=2):
        raise ValidationError("Нельзя забронировать прошедшее время.")
    if start > timezone.now() + timedelta(days=180):
        raise ValidationError("Бронировать можно максимум на 180 дней вперёд.")


def _check_overlap(room, start, end, exclude=None):
    busy = Booking.objects.filter(
        room=room, status__in=Booking.ACTIVE_STATUSES,
        starts_at__lt=end, ends_at__gt=start,
    )
    if exclude:
        busy = busy.exclude(pk=exclude)
    if busy.exists():
        raise BookingConflict("Переговорная уже занята в выбранный период.")


def create_booking(*, actor, room_id, title, notes, starts_at, ends_at):
    _validate_time(starts_at, ends_at)
    if not title or not title.strip():
        raise ValidationError("Укажите название встречи.")
    try:
        with transaction.atomic():
            room = Room.objects.select_for_update().get(pk=room_id, is_active=True)
            _check_overlap(room, starts_at, ends_at)
            status = Booking.Status.PENDING if room.is_vip else Booking.Status.CONFIRMED
            booking = Booking.objects.create(
                creator=actor, room=room, title=title.strip(), notes=notes or "",
                starts_at=starts_at, ends_at=ends_at, status=status,
            )
            audit(actor, "booking.created", booking.pk, room=room.pk, status=status)
            return booking
    except Room.DoesNotExist as exc:
        raise ValidationError("Переговорная не найдена или недоступна.") from exc
    except IntegrityError as exc:
        raise BookingConflict("Переговорная занята: конкурентное бронирование.") from exc


def update_booking(*, actor, booking_id, room_id, title, notes, starts_at, ends_at):
    _validate_time(starts_at, ends_at)
    if not title or not title.strip():
        raise ValidationError("Укажите название встречи.")
    try:
        with transaction.atomic():
            booking = Booking.objects.select_for_update().get(pk=booking_id)
            if booking.creator_id != actor.pk and not actor.can_manage:
                raise PermissionDenied
            if not booking.is_active:
                raise BookingStateError("Изменять можно только действующую бронь.")
            # Lock room rows in consistent order; exclusion constraint is the final backstop.
            ids = sorted({booking.room_id, int(room_id)})
            list(Room.objects.select_for_update().filter(pk__in=ids).order_by("pk"))
            room = Room.objects.get(pk=room_id, is_active=True)
            _check_overlap(room, starts_at, ends_at, exclude=booking.pk)
            booking.room = room
            booking.title = title.strip()
            booking.notes = notes or ""
            booking.starts_at = starts_at
            booking.ends_at = ends_at
            booking.status = Booking.Status.PENDING if room.is_vip else Booking.Status.CONFIRMED
            booking.reviewed_by = None
            booking.reviewed_at = None
            booking.rejection_reason = ""
            booking.save()
            audit(actor, "booking.updated", booking.pk, status=booking.status)
            return booking
    except Room.DoesNotExist as exc:
        raise ValidationError("Переговорная не найдена или недоступна.") from exc
    except IntegrityError as exc:
        raise BookingConflict("Переговорная занята: конкурентное изменение.") from exc


def cancel_booking(*, actor, booking_id):
    with transaction.atomic():
        booking = Booking.objects.select_for_update().get(pk=booking_id)
        if booking.creator_id != actor.pk and not actor.can_manage:
            raise PermissionDenied
        if not booking.is_active:
            raise BookingStateError("Эта бронь уже закрыта.")
        booking.status = Booking.Status.CANCELLED
        booking.save(update_fields=["status", "updated_at"])
        audit(actor, "booking.cancelled", booking.pk)
        return booking


def review_booking(*, actor, booking_id, approve, reason=""):
    if not actor.can_manage:
        raise PermissionDenied
    with transaction.atomic():
        booking = Booking.objects.select_for_update().get(pk=booking_id)
        if booking.status != Booking.Status.PENDING or not booking.room.is_vip:
            raise BookingStateError("Заявка уже рассмотрена либо не относится к VIP.")
        if not approve and not reason.strip():
            raise ValidationError("Укажите причину отклонения.")
        booking.status = Booking.Status.CONFIRMED if approve else Booking.Status.REJECTED
        booking.reviewed_by = actor
        booking.reviewed_at = timezone.now()
        booking.rejection_reason = reason.strip() if not approve else ""
        booking.save(update_fields=["status", "reviewed_by", "reviewed_at", "rejection_reason", "updated_at"])
        audit(actor, "booking.approved" if approve else "booking.rejected", booking.pk)
        return booking
