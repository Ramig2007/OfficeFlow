from datetime import datetime, time, timedelta
from functools import wraps

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connections
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from workspace.forms import BookingForm, LoginForm, ProfileForm, RegisterForm, RoomForm
from workspace.models import Booking, Room, User
from workspace.queries import booking_report, export_csv, report_summary, safe_parse_date
from workspace.services import (
    BookingConflict, BookingStateError, audit, cancel_booking, create_booking, review_booking,
    update_booking,
)


class OfficeLoginView(LoginView):
    template_name = "auth/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


def register_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        audit(user, "user.registered", user.pk)
        login(request, user)
        return redirect("dashboard")
    return render(request, "auth/register.html", {"form": form})


@login_required
@require_POST
def logout_view(request):
    logout(request)
    return redirect("login")


def staff_required(view):
    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.can_manage:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper


@login_required
def dashboard(request):
    today = timezone.localdate()
    tomorrow = today + timedelta(days=1)
    active_rooms = Room.objects.filter(is_active=True)
    today_bookings = Booking.objects.filter(
        starts_at__date=today, status__in=Booking.ACTIVE_STATUSES,
    ).select_related("room", "creator").order_by("starts_at")
    current = timezone.now()
    stats = {
        "rooms": active_rooms.count(),
        "today": today_bookings.count(),
        "mine": Booking.objects.filter(creator=request.user, starts_at__gte=current, status__in=Booking.ACTIVE_STATUSES).count(),
        "awaiting": Booking.objects.filter(status=Booking.Status.PENDING).count() if request.user.can_manage else Booking.objects.filter(creator=request.user, status=Booking.Status.PENDING).count(),
    }
    upcoming = Booking.objects.filter(creator=request.user, starts_at__gte=current, status__in=Booking.ACTIVE_STATUSES).select_related("room").order_by("starts_at")[:5]
    return render(request, "workspace/dashboard.html", {
        "today": today, "tomorrow": tomorrow, "stats": stats,
        "today_bookings": today_bookings[:7], "upcoming": upcoming, "rooms": active_rooms[:5],
    })


@login_required
def schedule(request):
    selected = safe_parse_date(request.GET.get("week", "")) or timezone.localdate()
    monday = selected - timedelta(days=selected.weekday())
    days = [monday + timedelta(days=offset) for offset in range(7)]
    chosen_day = safe_parse_date(request.GET.get("day", "")) or (timezone.localdate() if timezone.localdate() in days else monday)
    if chosen_day not in days:
        chosen_day = monday
    selected_room = request.GET.get("room", "")
    room_list = Room.objects.filter(is_active=True)
    if selected_room.isdigit():
        room_list = room_list.filter(pk=int(selected_room))
    week_start = timezone.make_aware(datetime.combine(monday, time.min))
    week_end = timezone.make_aware(datetime.combine(days[-1] + timedelta(days=1), time.min))
    bookings = list(Booking.objects.filter(
        room__in=room_list, status__in=Booking.ACTIVE_STATUSES,
        starts_at__lt=week_end, ends_at__gt=week_start,
    ).select_related("room", "creator"))
    by_room_day = {}
    for booking in bookings:
        for day in days:
            day_start = timezone.make_aware(datetime.combine(day, time.min))
            day_end = day_start + timedelta(days=1)
            if booking.starts_at < day_end and booking.ends_at > day_start:
                by_room_day.setdefault((booking.room_id, day), []).append(booking)
    matrix = [{"room": room, "cells": [{"day": day, "bookings": by_room_day.get((room.pk, day), [])} for day in days]} for room in room_list]
    hours = list(range(9, 19))
    hourly = []
    for room in room_list:
        cells = []
        for hour in hours:
            slot_start = timezone.make_aware(datetime.combine(chosen_day, time(hour)))
            slot_end = slot_start + timedelta(hours=1)
            occupied = next((b for b in bookings if b.room_id == room.pk and b.starts_at < slot_end and b.ends_at > slot_start), None)
            cells.append({"hour": hour, "busy": occupied})
        hourly.append({"room": room, "cells": cells})
    return render(request, "workspace/schedule.html", {
        "days": days, "matrix": matrix, "hours": hours, "hourly": hourly,
        "chosen_day": chosen_day, "prev_week": (monday - timedelta(days=7)).isoformat(),
        "next_week": (monday + timedelta(days=7)).isoformat(),
        "current_week": monday.isoformat(), "selected_room": selected_room,
        "all_rooms": Room.objects.filter(is_active=True),
    })


@login_required
def rooms(request):
    all_rooms = Room.objects.filter(is_active=True)
    size = request.GET.get("capacity", "")
    vip = request.GET.get("vip", "")
    if size.isdigit():
        all_rooms = all_rooms.filter(capacity__gte=int(size))
    if vip in {"0", "1"}:
        all_rooms = all_rooms.filter(is_vip=vip == "1")
    return render(request, "workspace/rooms.html", {"rooms": all_rooms})


@login_required
def room_detail(request, slug):
    room = get_object_or_404(Room, slug=slug, is_active=True)
    bookings = room.bookings.filter(
        status__in=Booking.ACTIVE_STATUSES, starts_at__gte=timezone.now(),
    ).select_related("creator").order_by("starts_at")[:12]
    return render(request, "workspace/room_detail.html", {"room": room, "bookings": bookings})


def _save_booking_form(request, form, booking=None):
    data = form.cleaned_data
    kwargs = {
        "actor": request.user, "room_id": data["room"].pk, "title": data["title"],
        "notes": data["notes"], "starts_at": data["starts_at"], "ends_at": data["ends_at"],
    }
    try:
        if booking:
            result = update_booking(booking_id=booking.pk, **kwargs)
            messages.success(request, "Бронирование изменено.")
        else:
            result = create_booking(**kwargs)
            messages.success(request, "Заявка отправлена на согласование." if result.status == Booking.Status.PENDING else "Комната забронирована.")
        return redirect("my-bookings")
    except (ValidationError, BookingConflict, BookingStateError) as exc:
        form.add_error(None, "; ".join(exc.messages) if isinstance(exc, ValidationError) else str(exc))
        return None


@login_required
def booking_create(request):
    initial = {}
    if request.GET.get("room", "").isdigit():
        initial["room"] = request.GET["room"]
    if start_date := safe_parse_date(request.GET.get("date", "")):
        next_day = max(start_date, timezone.localdate())
        requested_hour = request.GET.get("hour", "10")
        hour = int(requested_hour) if requested_hour.isdigit() and 0 <= int(requested_hour) <= 22 else 10
        initial["starts_at"] = datetime.combine(next_day, time(hour, 0))
        initial["ends_at"] = datetime.combine(next_day, time(hour + 1, 0))
    form = BookingForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        response = _save_booking_form(request, form)
        if response:
            return response
    return render(request, "workspace/booking_form.html", {"form": form, "editing": False})


@login_required
def booking_edit(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    if booking.creator_id != request.user.pk and not request.user.can_manage:
        raise PermissionDenied
    if not booking.is_active:
        messages.error(request, "Изменение закрытой брони недоступно.")
        return redirect("my-bookings")
    initial = {
        "room": booking.room, "title": booking.title, "notes": booking.notes,
        "starts_at": timezone.localtime(booking.starts_at), "ends_at": timezone.localtime(booking.ends_at),
    }
    form = BookingForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        response = _save_booking_form(request, form, booking=booking)
        if response:
            return response
    return render(request, "workspace/booking_form.html", {"form": form, "editing": True, "booking": booking})


@login_required
@require_POST
def booking_cancel(request, pk):
    try:
        cancel_booking(actor=request.user, booking_id=pk)
        messages.success(request, "Бронирование отменено.")
    except BookingStateError as exc:
        messages.error(request, str(exc))
    except Booking.DoesNotExist as exc:
        raise Http404 from exc
    return redirect("my-bookings")


@login_required
def my_bookings(request):
    queryset = Booking.objects.filter(creator=request.user).select_related("room").order_by("-starts_at")
    return render(request, "workspace/my_bookings.html", {"bookings": queryset})


@staff_required
def approvals(request):
    pending = Booking.objects.filter(status=Booking.Status.PENDING).select_related("room", "creator").order_by("starts_at")
    return render(request, "workspace/approvals.html", {"bookings": pending})


@staff_required
@require_POST
def approval_action(request, pk, action):
    if action not in {"approve", "reject"}:
        raise Http404
    try:
        review_booking(actor=request.user, booking_id=pk, approve=action == "approve", reason=request.POST.get("reason", ""))
        messages.success(request, "Решение сохранено.")
    except (BookingStateError, ValidationError) as exc:
        messages.error(request, "; ".join(exc.messages) if isinstance(exc, ValidationError) else str(exc))
    except Booking.DoesNotExist as exc:
        raise Http404 from exc
    return redirect("approvals")


@staff_required
def manage_rooms(request):
    return render(request, "workspace/manage_rooms.html", {"rooms": Room.objects.all()})


@staff_required
def manage_room_form(request, pk=None):
    room = get_object_or_404(Room, pk=pk) if pk else None
    form = RoomForm(request.POST or None, instance=room)
    if request.method == "POST" and form.is_valid():
        try:
            obj = form.save()
        except ValidationError as exc:
            form.add_error("is_vip", exc.message_dict.get("is_vip", exc.messages))
        else:
            audit(request.user, "room.updated" if room else "room.created", obj.pk)
            messages.success(request, "Переговорная сохранена.")
            return redirect("manage-rooms")
    return render(request, "workspace/manage_room_form.html", {"form": form, "room": room})


@staff_required
def manage_users(request):
    if request.method == "POST":
        user = get_object_or_404(User, pk=request.POST.get("user_id"))
        role = request.POST.get("role")
        if role not in User.Roles.values:
            messages.error(request, "Неизвестная роль.")
        elif user.pk == request.user.pk and role != User.Roles.ADMIN:
            messages.error(request, "Нельзя понизить собственную административную роль.")
        elif user.is_superuser and role != User.Roles.ADMIN:
            messages.error(request, "Нельзя изменить роль суперпользователя этим способом.")
        else:
            user.role = role
            user.save(update_fields=["role"])
            audit(request.user, "user.role_changed", user.pk, role=role)
            messages.success(request, "Роль изменена.")
        return redirect("manage-users")
    return render(request, "workspace/manage_users.html", {"users": User.objects.order_by("username")})


@staff_required
def reports(request):
    queryset = booking_report(request)
    return render(request, "workspace/reports.html", {
        "stats": report_summary(queryset), "bookings": queryset[:30], "rooms": Room.objects.all(),
    })


@staff_required
def report_csv(request):
    audit(request.user, "report.exported", "bookings")
    return export_csv(booking_report(request))


@login_required
def profile(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        audit(request.user, "user.profile_updated", request.user.pk)
        messages.success(request, "Профиль обновлён.")
        return redirect("profile")
    return render(request, "workspace/profile.html", {"form": form})


def health_live(request):
    return JsonResponse({"status": "alive"})


def health_ready(request):
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        cache.set("officeflow:readiness", "ok", 10)
        if cache.get("officeflow:readiness") != "ok":
            raise RuntimeError("cache not ready")
    except Exception:  # noqa: BLE001
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ready"})
