"""Render + Neon production configuration (no VPS, Nginx or Redis required).

Use only on Render with DJANGO_SETTINGS_MODULE=officeflow.settings_render.
The local Docker Compose configuration remains in officeflow.settings.
"""

import os
from urllib.parse import unquote, urlsplit

# Render Free may be cold-started at any time. Never enable Django DEBUG there.
os.environ["DEBUG"] = "0"

# Render Blueprints generate a strong 256-bit secret (44 base64 characters).
# Add a stable prefix to satisfy OfficeFlow's existing 50-character key policy.
# The generated seed must remain unchanged across deployments.
if not os.getenv("SECRET_KEY"):
    render_secret = os.getenv("RENDER_SECRET_KEY", "")
    if len(render_secret) < 40 or render_secret.startswith(("REPLACE_", "CHANGE_")):
        raise RuntimeError("Set RENDER_SECRET_KEY (a generated 256-bit Render secret)")
    os.environ["SECRET_KEY"] = "officeflow-render-v1:" + render_secret

hostname = os.getenv("RENDER_EXTERNAL_HOSTNAME", "").strip()
if hostname:
    if "://" in hostname or "/" in hostname or ":" in hostname:
        raise RuntimeError("RENDER_EXTERNAL_HOSTNAME must be a hostname, not a URL")
    os.environ.setdefault("ALLOWED_HOSTS", hostname)
    os.environ.setdefault("CSRF_TRUSTED_ORIGINS", "https://" + hostname)

# Copy the complete Direct connection URL from Neon when individual password
# fields are hard to synchronize. The URL wins over stale individual NEON_* vars.
# Never log this value: it contains the real database password.
neon_connection_string = os.getenv("NEON_CONNECTION_STRING", "").strip()
if neon_connection_string:
    try:
        connection = urlsplit(neon_connection_string)
        neon_host = connection.hostname or ""
        neon_user = unquote(connection.username or "")
        neon_password = unquote(connection.password or "")
        neon_database = unquote(connection.path.removeprefix("/"))
        neon_port = connection.port
    except ValueError:
        raise RuntimeError("Invalid NEON_CONNECTION_STRING: expected a Neon PostgreSQL URL") from None
    if (
        connection.scheme not in ("postgresql", "postgres")
        or not neon_host
        or not neon_user
        or not neon_password
        or not neon_database
        or connection.path.count("/") != 1
        or neon_port not in (None, 5432)
    ):
        raise RuntimeError("Invalid NEON_CONNECTION_STRING: expected a Neon PostgreSQL URL")
else:
    for key in ("NEON_HOST", "NEON_DATABASE", "NEON_USER", "NEON_PASSWORD"):
        if not os.getenv(key, "").strip():
            raise RuntimeError(f"Set {key} or NEON_CONNECTION_STRING in Render")
    neon_host = os.environ["NEON_HOST"].strip()
    neon_database = os.environ["NEON_DATABASE"]
    neon_user = os.environ["NEON_USER"]
    neon_password = os.environ["NEON_PASSWORD"]

if "://" in neon_host or "/" in neon_host or ":" in neon_host:
    raise RuntimeError("Neon host must be a direct hostname without a scheme or port")
if "-pooler." in neon_host:
    raise RuntimeError("Use the Direct connection hostname for OfficeFlow migrations")

os.environ["DB_HOST"] = neon_host
os.environ["DB_NAME"] = neon_database
os.environ["DB_USER"] = neon_user
os.environ["DB_PASSWORD"] = neon_password
os.environ["DB_PORT"] = "5432"
os.environ["COOKIE_SECURE"] = "1"
os.environ["SECURE_SSL_REDIRECT"] = "1"
os.environ["SECURE_HSTS_SECONDS"] = "31536000"

from .settings import *  # noqa: E402,F401,F403

# Require certificate AND hostname verification for Neon.
# psycopg[binary] ships its own libpq/OpenSSL, whose default CA lookup may not
# match Debian's installed certificate store. Using sslrootcert=system caused
# Render's first deployment to fail with "SSL error: certificate verify failed"
# even though Dockerfile.render installs ca-certificates. Point libpq directly
# at the Debian CA bundle rather than weakening sslmode to "require".
DATABASES["default"]["OPTIONS"].update(  # noqa: F405
    {
        "sslmode": "verify-full",
        "sslrootcert": "/etc/ssl/certs/ca-certificates.crt",
        "connect_timeout": 15,
    }
)
# Avoid keeping stale persistent connections to autosuspending Neon compute.
DATABASES["default"]["CONN_MAX_AGE"] = 0  # noqa: F405

# On Render Free, default to DB-backed Django sessions without extra Redis.
# LocMemCache is sufficient for the single demo instance, not multi-node limits.
if not os.getenv("REDIS_URL"):
    SESSION_ENGINE = "django.contrib.sessions.backends.db"

# Unlike Docker Compose + Nginx, Render exposes Gunicorn directly to the web.
# Prometheus /metrics must not be reachable by anonymous Internet visitors.
OFFICEFLOW_EXPOSE_METRICS = False
