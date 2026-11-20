#!/bin/sh
set -eu

# The shared staticfiles volume may outlive an image update. Re-collect on each
# start so Nginx always serves assets matching the running application image.
python manage.py collectstatic --noinput

exec "$@"
