"""Idempotent DEMO fixtures. Never run on a production database."""
import os
from datetime import datetime, time, timedelta

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from workspace.models import Booking, Room, User
from workspace.services import create_booking


class Command(BaseCommand):
    help = "Create demonstration rooms, accounts and bookings (only when DEBUG=1)"

    def handle(self, *args, **kwargs):
        if os.getenv("DEBUG") != "1":
            raise CommandError("seed_demo is only available with DEBUG=1")
        admin, admin_created = User.objects.get_or_create(
            username="manager", defaults={"first_name": "Анна", "last_name": "Орлова", "role": User.Roles.ADMIN, "email": "manager@example.test"},
        )
        if admin_created or not admin.password or not admin.has_usable_password():
            admin.set_password(os.getenv("DEMO_PASSWORD", "DemoOnly!123"))
            admin.save(update_fields=["password"])
        member, member_created = User.objects.get_or_create(username="employee", defaults={"first_name": "Илья", "last_name": "Миронов", "email": "employee@example.test"})
        if member_created or not member.password or not member.has_usable_password():
            member.set_password(os.getenv("DEMO_PASSWORD", "DemoOnly!123"))
            member.save(update_fields=["password"])

        try:
            loadtest_count = int(os.getenv("LOADTEST_USERS", "0"))
        except ValueError as exc:
            raise CommandError("LOADTEST_USERS must be an integer between 0 and 1000") from exc
        if not 0 <= loadtest_count <= 1000:
            raise CommandError("LOADTEST_USERS must be between 0 and 1000")
        if loadtest_count and not os.getenv("DEMO_PASSWORD"):
            raise CommandError("Set DEMO_PASSWORD when creating load-test accounts")
        if loadtest_count:
            usernames = [f"loadtest{index:02d}" for index in range(1, loadtest_count + 1)]
            # One shared password hash is acceptable only for these disposable DEBUG fixtures.
            # This avoids performing 1000 expensive password hashes during CI data seeding.
            password_hash = make_password(os.environ["DEMO_PASSWORD"])
            User.objects.bulk_create(
                [
                    User(
                        username=username,
                        first_name=f"Load test {index}",
                        email=f"{username}@example.test",
                        password=password_hash,
                    )
                    for index, username in enumerate(usernames, start=1)
                ],
                batch_size=500,
                ignore_conflicts=True,
            )
            User.objects.filter(username__in=usernames).update(
                password=password_hash,
                is_active=True,
            )
        specs = [
            ("Атлас", "atlas", 2, "Северное крыло · 2 этаж", 8, "ТВ 65″, видеосвязь, доска", False),
            ("Маяк", "mayak", 1, "Западное крыло · 1 этаж", 4, "Доска, HDMI", False),
            ("Орбита", "orbita", 3, "Восточное крыло · 3 этаж", 12, "Проектор, видеосвязь, акустика", True),
            ("Нота", "nota", 2, "Северное крыло · 2 этаж", 6, "Экран, флипчарт", False),
            ("Точка", "tochka", 1, "Западное крыло · 1 этаж", 3, "Монитор, маркерная доска", False),
        ]
        rooms = []
        for name, slug, floor, location, capacity, equipment, vip in specs:
            room, _ = Room.objects.get_or_create(
                slug=slug, defaults={"name": name, "floor": floor, "location": location, "capacity": capacity, "equipment": equipment, "is_vip": vip, "description": "Светлая переговорная для работы команд и встреч с коллегами."},
            )
            rooms.append(room)
        base = timezone.localdate() + timedelta(days=1)
        if base.weekday() >= 5:
            base += timedelta(days=7 - base.weekday())
        for idx, room in enumerate(rooms):
            start = timezone.make_aware(datetime.combine(base, time(10 + idx, 0)))
            if not Booking.objects.filter(room=room, starts_at=start).exists():
                create_booking(actor=member, room_id=room.id, title=["Планирование спринта", "Обсуждение дизайна", "Встреча с партнёрами", "Презентация", "Короткий синк"][idx], notes="Демонстрационная встреча", starts_at=start, ends_at=start + timedelta(hours=1))
        suffix = f", load-test accounts: {loadtest_count}" if loadtest_count else ""
        self.stdout.write(self.style.SUCCESS(f"Демо: manager / employee, комнаты и встречи созданы{suffix}"))
