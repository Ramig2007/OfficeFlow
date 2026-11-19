from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import F, Q
from django.utils import timezone


class User(AbstractUser):
    class Roles(models.TextChoices):
        MEMBER = "member", "Сотрудник"
        ADMIN = "admin", "Администратор"

    role = models.CharField(max_length=12, choices=Roles.choices, default=Roles.MEMBER)
    department = models.CharField(max_length=120, blank=True)

    @property
    def can_manage(self):
        return self.is_authenticated and (self.role == self.Roles.ADMIN or self.is_superuser)


class Room(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=110, unique=True, allow_unicode=True)
    floor = models.PositiveSmallIntegerField(default=1)
    location = models.CharField(max_length=120)
    capacity = models.PositiveSmallIntegerField(default=4)
    description = models.TextField(blank=True)
    equipment = models.CharField(max_length=250, blank=True)
    is_vip = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["floor", "name"]
        constraints = [models.CheckConstraint(condition=Q(capacity__gte=1), name="room_capacity_positive")]

    def clean(self):
        super().clean()
        if self.pk:
            previous = Room.objects.filter(pk=self.pk).values_list("is_vip", flat=True).first()
            if previous is not None and previous != self.is_vip:
                if self.bookings.filter(
                    status__in=Booking.ACTIVE_STATUSES,
                    starts_at__gte=timezone.now(),
                ).exists():
                    raise ValidationError({"is_vip": "Нельзя менять VIP при активных будущих бронированиях."})

    def save(self, *args, **kwargs):
        # Every room change serializes with booking creation, which locks the
        # same Room row. This prevents a concurrent VIP-toggle bypass.
        if not self.pk:
            return super().save(*args, **kwargs)
        with transaction.atomic():
            previous = Room.objects.select_for_update().filter(pk=self.pk).first()
            if previous is not None and previous.is_vip != self.is_vip:
                if Booking.objects.filter(
                    room_id=self.pk, status__in=Booking.ACTIVE_STATUSES,
                    starts_at__gte=timezone.now(),
                ).exists():
                    raise ValidationError({
                        "is_vip": "Перед изменением VIP отмените будущие активные бронирования."
                    })
            return super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Booking(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает подтверждения"
        CONFIRMED = "confirmed", "Подтверждено"
        REJECTED = "rejected", "Отклонено"
        CANCELLED = "cancelled", "Отменено"

    ACTIVE_STATUSES = (Status.PENDING, Status.CONFIRMED)
    room = models.ForeignKey(Room, related_name="bookings", on_delete=models.PROTECT)
    creator = models.ForeignKey(User, related_name="bookings", on_delete=models.PROTECT)
    title = models.CharField(max_length=140)
    notes = models.TextField(blank=True)
    starts_at = models.DateTimeField(db_index=True)
    ends_at = models.DateTimeField(db_index=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.CONFIRMED)
    reviewed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="reviews")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-starts_at"]
        constraints = [models.CheckConstraint(condition=Q(ends_at__gt=F("starts_at")), name="booking_positive_interval")]
        indexes = [models.Index(fields=["room", "starts_at", "ends_at"], name="booking_room_period")]

    def clean(self):
        if self.starts_at and self.ends_at:
            if self.ends_at <= self.starts_at:
                raise ValidationError({"ends_at": "Время окончания должно быть позже начала."})

    @property
    def is_active(self):
        return self.status in self.ACTIVE_STATUSES

    def __str__(self):
        return f"{self.room}: {self.title} ({self.starts_at})"


class AuditEvent(models.Model):
    actor = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=70)
    target = models.CharField(max_length=120)
    detail = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at"]
