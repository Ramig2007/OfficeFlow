"""Render/Neon production configuration without contacting a real Neon database."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError

ROOT = Path(__file__).resolve().parents[2]


def render_env():
    env = dict(os.environ)
    env.update(
        {
            "DJANGO_SETTINGS_MODULE": "officeflow.settings_render",
            "DEBUG": "1",  # The Render settings module must force DEBUG off.
            "RENDER_EXTERNAL_HOSTNAME": "officeflow-ci.onrender.com",
            "RENDER_SECRET_KEY": "z" * 44,
            "NEON_HOST": "ep-test.eu-central-1.aws.neon.tech",
            "NEON_DATABASE": "neondb",
            "NEON_USER": "neondb_owner",
            "NEON_PASSWORD": "ci-only-render-neon-password-32chars",
        }
    )
    for key in (
        "SECRET_KEY", "DB_HOST", "DB_PORT", "DB_USER", "DB_NAME", "DB_PASSWORD",
        "ALLOWED_HOSTS", "CSRF_TRUSTED_ORIGINS", "REDIS_URL",
    ):
        env.pop(key, None)
    return env


def run_render(code, env=None):
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=render_env() if env is None else env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def test_render_config_is_secure_and_removes_public_metrics():
    result = run_render(
        """
import django
django.setup()
from django.conf import settings
from django.urls import resolve, Resolver404

db = settings.DATABASES["default"]
assert settings.DEBUG is False
assert settings.SECRET_KEY.startswith("officeflow-render-v1:")
assert len(settings.SECRET_KEY) >= 50
assert settings.ALLOWED_HOSTS == ["officeflow-ci.onrender.com"]
assert settings.CSRF_TRUSTED_ORIGINS == ["https://officeflow-ci.onrender.com"]
assert settings.SESSION_COOKIE_SECURE and settings.CSRF_COOKIE_SECURE
assert settings.SECURE_SSL_REDIRECT
assert settings.SECURE_HSTS_SECONDS == 31536000
assert db["ENGINE"] == "django.db.backends.postgresql"
assert db["HOST"] == "ep-test.eu-central-1.aws.neon.tech"
assert db["OPTIONS"]["sslmode"] == "verify-full"
assert db["OPTIONS"]["sslrootcert"] == "/etc/ssl/certs/ca-certificates.crt"
assert db["CONN_MAX_AGE"] == 0
assert settings.SESSION_ENGINE == "django.contrib.sessions.backends.db"
assert settings.OFFICEFLOW_EXPOSE_METRICS is False
assert resolve("/health/live/").url_name == "health-live"
assert resolve("/health/ready/").url_name == "health-ready"
try:
    resolve("/metrics")
except Resolver404:
    pass
else:
    raise AssertionError("Public Prometheus endpoint must be disabled on Render")
"""
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("length", [12, 16, 23])
def test_render_accepts_neon_generated_password_below_24_chars(length):
    env = render_env()
    env["NEON_PASSWORD"] = "R" * length
    result = run_render(
        'import django; django.setup(); from django.conf import settings; '
        'assert len(settings.DATABASES["default"]["PASSWORD"]) < 24',
        env,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("password", ["short", "REPLACE_" + "z" * 24, "CHANGE_" + "z" * 24])
def test_render_refuses_short_or_placeholder_database_password(password):
    env = render_env()
    env["NEON_PASSWORD"] = password
    result = run_render("import django; django.setup()", env)
    assert result.returncode != 0
    assert "DB_PASSWORD must" in result.stderr


def test_standard_production_keeps_24_character_database_password_policy():
    env = render_env()
    env.update({
        "DJANGO_SETTINGS_MODULE": "officeflow.settings",
        "DEBUG": "0",
        "SECRET_KEY": "S" * 60,
        "ALLOWED_HOSTS": "example.com",
        "CSRF_TRUSTED_ORIGINS": "https://example.com",
        "DB_HOST": "postgres.example.com",
        "DB_NAME": "officeflow",
        "DB_USER": "officeflow",
        "DB_PASSWORD": "R" * 16,
        "COOKIE_SECURE": "1",
        "SECURE_SSL_REDIRECT": "1",
        "SECURE_HSTS_SECONDS": "31536000",
    })
    result = run_render("import django; django.setup()", env)
    assert result.returncode != 0
    assert "at least 24 characters" in result.stderr


@pytest.mark.parametrize("key", ["NEON_HOST", "NEON_DATABASE", "NEON_USER", "NEON_PASSWORD"])
def test_render_refuses_missing_neon_settings(key):
    env = render_env()
    env.pop(key)
    result = run_render("import django; django.setup()", env)
    assert result.returncode != 0
    assert f"Set {key}" in result.stderr


def test_render_refuses_pooled_neon_host():
    env = render_env()
    env["NEON_HOST"] = "ep-test-pooler.eu-central-1.aws.neon.tech"
    result = run_render("import django; django.setup()", env)
    assert result.returncode != 0
    assert "Direct connection hostname" in result.stderr


def test_render_refuses_missing_secret():
    env = render_env()
    env.pop("RENDER_SECRET_KEY")
    result = run_render("import django; django.setup()", env)
    assert result.returncode != 0
    assert "RENDER_SECRET_KEY" in result.stderr


@pytest.mark.django_db
def test_render_admin_bootstrap_creates_once_and_never_resets_existing_password(monkeypatch):
    monkeypatch.setenv("BOOTSTRAP_ADMIN_USERNAME", "first_render_admin")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "officeflow-ci-test-password-123456")
    call_command("bootstrap_render_admin")
    User = get_user_model()
    user = User.objects.get(username="first_render_admin")
    assert user.is_superuser and user.is_staff and user.role == User.Roles.ADMIN
    assert user.check_password("officeflow-ci-test-password-123456")

    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "different-ci-test-password-123456")
    call_command("bootstrap_render_admin")
    user.refresh_from_db()
    assert user.check_password("officeflow-ci-test-password-123456")


@pytest.mark.django_db
def test_render_admin_bootstrap_rejects_weak_password(monkeypatch):
    monkeypatch.setenv("BOOTSTRAP_ADMIN_USERNAME", "new_admin")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "weak")
    with pytest.raises(CommandError, match="at least 16"):
        call_command("bootstrap_render_admin")
    assert not get_user_model().objects.filter(username="new_admin").exists()
