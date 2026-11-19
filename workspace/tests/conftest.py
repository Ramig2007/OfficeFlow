from datetime import datetime, time, timedelta

import pytest
from django.utils import timezone

from workspace.models import Room, User


@pytest.fixture
def member(db):
    return User.objects.create_user(username="alice", password="VeryStrongTestPass123!", first_name="Алиса")


@pytest.fixture
def second_member(db):
    return User.objects.create_user(username="bob", password="VeryStrongTestPass123!")


@pytest.fixture
def manager(db):
    return User.objects.create_user(username="boss", password="VeryStrongTestPass123!", role=User.Roles.ADMIN)


@pytest.fixture
def room(db):
    return Room.objects.create(name="Спектр", slug="spektr", location="2 этаж", floor=2, capacity=8)


@pytest.fixture
def vip_room(db):
    return Room.objects.create(name="Вектор", slug="vektor", location="3 этаж", floor=3, capacity=6, is_vip=True)


@pytest.fixture
def window():
    start_day = timezone.localdate() + timedelta(days=2)
    start = timezone.make_aware(datetime.combine(start_day, time(12, 0)))
    return start, start + timedelta(hours=2)
