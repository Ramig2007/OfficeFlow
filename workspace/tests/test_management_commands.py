import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from workspace.models import User


def test_seed_demo_requires_debug(monkeypatch):
    monkeypatch.setenv("DEBUG", "0")
    with pytest.raises(CommandError, match="DEBUG=1"):
        call_command("seed_demo")


@pytest.mark.django_db
def test_seed_demo_sets_passwords_for_new_accounts_and_preserves_existing_password(monkeypatch):
    password = "OfficeFlow-CI-Demo-Only-2026!"
    monkeypatch.setenv("DEBUG", "1")
    monkeypatch.setenv("DEMO_PASSWORD", password)

    call_command("seed_demo")

    employee = User.objects.get(username="employee")
    manager = User.objects.get(username="manager")
    assert employee.check_password(password)
    assert manager.check_password(password)
    assert employee.role == User.Roles.MEMBER
    assert manager.role == User.Roles.ADMIN

    monkeypatch.setenv("DEMO_PASSWORD", "A-Different-Password-2026!")
    call_command("seed_demo")
    employee.refresh_from_db()
    manager.refresh_from_db()
    assert employee.check_password(password)
    assert manager.check_password(password)
    assert not employee.check_password("A-Different-Password-2026!")
