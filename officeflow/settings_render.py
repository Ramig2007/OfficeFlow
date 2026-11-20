"""Render + Neon production configuration (no VPS, Nginx or Redis required).

Use only on Render with DJANGO_SETTINGS_MODULE=officeflow.settings_render.
The local Docker Compose configuration remains in officeflow.settings.
"""

import os

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

for key in ("NEON_HOST", "NEON_DATABASE", "NEON_USER", "NEON_PASSWORD"):
    if not os.getenv(key, "").strip():
        raise RuntimeError(f"Set {key} in the Render environment for the Neon database")

neon_host = os.environ["NEON_HOST"].strip()
if "://" in neon_host or "/" in neon_host or ":" in neon_host:
    raise RuntimeError("NEON_HOST must contain only the direct Neon hostname")
if "-pooler." in neon_host:
    raise RuntimeError("Use the Direct connection hostname for OfficeFlow migrations")

os.environ["DB_HOST"] = neon_host
os.environ["DB_NAME"] = os.environ["NEON_DATABASE"]
os.environ["DB_USER"] = os.environ["NEON_USER"]
os.environ["DB_PASSWORD"] = os.environ["NEON_PASSWORD"]
os.environ["DB_PORT"] = "5432"
os.environ["COOKIE_SECURE"] = "1"
os.environ["SECURE_SSL_REDIRECT"] = "1"
os.environ["SECURE_HSTS_SECONDS"] = "31536000"

from .settings import *  # noqa: E402,F401,F403

# Require certificate and hostname verification when connecting to Neon.
# sslrootcert=system is supported by recent libpq bundled with psycopg[binary].
DATABASES["default"]["OPTIONS"].update(  # noqa: F405
    {
        "sslmode": "verify-full",
        "sslrootcert": "system",
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
