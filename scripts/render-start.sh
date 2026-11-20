#!/bin/sh
# Render Free has no shell / one-off jobs; migrate at boot before accepting traffic.
# This runs only when starting the Render image, not on the existing Docker Compose stack.
set -eu

export DJANGO_SETTINGS_MODULE=officeflow.settings_render

python manage.py collectstatic --noinput
python manage.py migrate --noinput

# Set BOOTSTRAP_ADMIN_USERNAME/PASSWORD for the first successful deployment.
# After verifying the admin login, remove these env variables from Render.
if [ -n "${BOOTSTRAP_ADMIN_USERNAME:-}" ] || [ -n "${BOOTSTRAP_ADMIN_PASSWORD:-}" ]; then
    python manage.py bootstrap_render_admin
fi

exec gunicorn officeflow.wsgi:application \
    --bind "0.0.0.0:${PORT:-10000}" \
    --workers 2 \
    --threads 2 \
    --timeout 75 \
    --access-logfile -
