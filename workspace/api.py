"""Versioned REST API. All mutations delegate to the same domain services as HTML views."""

from datetime import timedelta

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.routers import DefaultRouter
from rest_framework.views import APIView

from workspace.models import Booking, Room, User
from workspace.queries import booking_report, export_csv, report_summary, safe_parse_date
from workspace.services import (
    BookingConflict, BookingStateError, audit, cancel_booking, create_booking, review_booking,
    update_booking,
)


class Conflict(APIException):
    status_code = 409
    default_detail = "Выбранное время занято или состояние бронирования изменилось."
    default_code = "conflict"


class IsOfficeAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and request.user.can_manage)


def error_response(exc):
    if isinstance(exc, (BookingConflict, BookingStateError)):
        raise Conflict(str(exc)) from exc
    if isinstance(exc, DjangoValidationError):
        raise ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages) from exc
    raise exc


class RoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = ["id", "name", "slug", "floor", "location", "capacity", "description", "equipment", "is_vip", "is_active"]

    def validate(self, attrs):
        if self.instance and "is_vip" in attrs and attrs["is_vip"] != self.instance.is_vip:
            if self.instance.bookings.filter(status__in=Booking.ACTIVE_STATUSES, starts_at__gte=timezone.now()).exists():
                raise ValidationError({"is_vip": "Сначала завершите или отмените будущие активные бронирования."})
        return attrs


class BookingSerializer(serializers.ModelSerializer):
    room_name = serializers.CharField(source="room.name", read_only=True)
    creator_name = serializers.CharField(source="creator.username", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Booking
        fields = [
            "id", "room", "room_name", "creator", "creator_name", "title", "notes",
            "starts_at", "ends_at", "status", "status_display", "reviewed_by",
            "reviewed_at", "rejection_reason", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "creator", "status", "reviewed_by", "reviewed_at", "rejection_reason", "created_at", "updated_at",
        ]


class BookingWriteSerializer(serializers.Serializer):
    room = serializers.PrimaryKeyRelatedField(queryset=Room.objects.filter(is_active=True))
    title = serializers.CharField(max_length=140, allow_blank=False)
    notes = serializers.CharField(allow_blank=True, required=False, default="")
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "department", "role"]
        read_only_fields = ["id", "username", "email", "first_name", "last_name", "department"]


class RoomViewSet(viewsets.ModelViewSet):
    serializer_class = RoomSerializer
    queryset = Room.objects.all()

    def get_permissions(self):
        return [IsAuthenticated()] if self.action in {"list", "retrieve"} else [IsOfficeAdmin()]

    def get_queryset(self):
        queryset = Room.objects.all()
        if not self.request.user.can_manage:
            queryset = queryset.filter(is_active=True)
        capacity = self.request.query_params.get("capacity", "")
        if capacity.isdigit():
            queryset = queryset.filter(capacity__gte=int(capacity))
        return queryset

    def perform_create(self, serializer):
        room = serializer.save()
        audit(self.request.user, "room.created", room.pk)

    def perform_update(self, serializer):
        try:
            room = serializer.save()
        except DjangoValidationError as exc:
            error_response(exc)
        audit(self.request.user, "room.updated", room.pk)

    def destroy(self, request, *args, **kwargs):
        # Deactivate rather than deleting history or breaking FK references.
        room = self.get_object()
        room.is_active = False
        room.save(update_fields=["is_active"])
        audit(request.user, "room.deactivated", room.pk)
        return Response(status=status.HTTP_204_NO_CONTENT)


class BookingViewSet(viewsets.ModelViewSet):
    serializer_class = BookingSerializer
    queryset = Booking.objects.select_related("room", "creator").all()
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def get_queryset(self):
        queryset = self.queryset
        if not self.request.user.can_manage or self.request.query_params.get("mine") == "1":
            queryset = queryset.filter(creator=self.request.user)
        room_id = self.request.query_params.get("room", "")
        if room_id.isdigit():
            queryset = queryset.filter(room_id=int(room_id))
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = BookingWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        try:
            booking = create_booking(
                actor=request.user, room_id=d["room"].pk, title=d["title"],
                notes=d.get("notes", ""), starts_at=d["starts_at"], ends_at=d["ends_at"],
            )
        except (DjangoValidationError, BookingConflict) as exc:
            error_response(exc)
        return Response(BookingSerializer(booking).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        booking = self.get_object()
        if booking.creator_id != request.user.pk and not request.user.can_manage:
            raise PermissionDenied
        initial = {
            "room": booking.room.pk, "title": booking.title, "notes": booking.notes,
            "starts_at": booking.starts_at, "ends_at": booking.ends_at,
        }
        values = {**initial, **request.data}
        serializer = BookingWriteSerializer(data=values)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        try:
            booking = update_booking(
                actor=request.user, booking_id=booking.pk, room_id=d["room"].pk,
                title=d["title"], notes=d["notes"], starts_at=d["starts_at"], ends_at=d["ends_at"],
            )
        except (DjangoValidationError, BookingConflict, BookingStateError) as exc:
            error_response(exc)
        return Response(BookingSerializer(booking).data)

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        booking = self.get_object()
        try:
            booking = cancel_booking(actor=request.user, booking_id=booking.pk)
        except BookingStateError as exc:
            error_response(exc)
        return Response(BookingSerializer(booking).data)

    @action(detail=True, methods=["post"], permission_classes=[IsOfficeAdmin])
    def approve(self, request, pk=None):
        return self._review(request, approve=True)

    @action(detail=True, methods=["post"], permission_classes=[IsOfficeAdmin])
    def reject(self, request, pk=None):
        return self._review(request, approve=False)

    def _review(self, request, *, approve):
        booking = self.get_object()
        try:
            booking = review_booking(actor=request.user, booking_id=booking.pk, approve=approve, reason=request.data.get("reason", ""))
        except (DjangoValidationError, BookingStateError) as exc:
            error_response(exc)
        return Response(BookingSerializer(booking).data)


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UserSerializer
    queryset = User.objects.all().order_by("username")
    permission_classes = [IsOfficeAdmin]

    @action(detail=True, methods=["post"])
    def change_role(self, request, pk=None):
        user = self.get_object()
        role = request.data.get("role")
        if role not in User.Roles.values:
            raise ValidationError({"role": "Недопустимая роль."})
        if user.pk == request.user.pk and role != User.Roles.ADMIN:
            raise ValidationError({"role": "Нельзя понизить собственную роль."})
        if user.is_superuser and role != User.Roles.ADMIN:
            raise ValidationError({"role": "Нельзя понизить суперпользователя."})
        user.role = role
        user.save(update_fields=["role"])
        audit(request.user, "user.role_changed", user.pk, role=role)
        return Response(self.get_serializer(user).data)


class ScheduleAPI(APIView):
    def get(self, request):
        date = safe_parse_date(request.query_params.get("date", "")) or timezone.localdate()
        end = date + timedelta(days=6)
        from datetime import datetime, time
        week_start = timezone.make_aware(datetime.combine(date, time.min))
        week_end = timezone.make_aware(datetime.combine(end + timedelta(days=1), time.min))
        bookings = Booking.objects.filter(
            status__in=Booking.ACTIVE_STATUSES, starts_at__lt=week_end,
            ends_at__gt=week_start, room__is_active=True,
        ).select_related("room", "creator")
        room = request.query_params.get("room", "")
        if room.isdigit():
            bookings = bookings.filter(room_id=int(room))
        return Response({"from": date.isoformat(), "to": end.isoformat(), "bookings": BookingSerializer(bookings, many=True).data})


class ReportSummaryAPI(APIView):
    permission_classes = [IsOfficeAdmin]

    def get(self, request):
        return Response(report_summary(booking_report(request)))


class ExportAPI(APIView):
    permission_classes = [IsOfficeAdmin]

    def get(self, request):
        audit(request.user, "report.exported", "api/bookings")
        return export_csv(booking_report(request))


router = DefaultRouter()
router.register("rooms", RoomViewSet, basename="room")
router.register("bookings", BookingViewSet, basename="booking")
router.register("users", UserViewSet, basename="user")
