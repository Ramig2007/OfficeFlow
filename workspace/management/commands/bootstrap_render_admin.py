"""Create the configured Render admin from a short-lived secret.

The bootstrap is idempotent for the configured username. Other existing
superusers do not prevent creating this explicitly requested account.
Remove BOOTSTRAP_ADMIN_USERNAME and BOOTSTRAP_ADMIN_PASSWORD after verifying
the login. Existing accounts and passwords are never modified.
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = "Create the configured Render administrator without changing existing accounts."

    @transaction.atomic
    def handle(self, *args, **options):
        username = os.getenv("BOOTSTRAP_ADMIN_USERNAME", "").strip()
        password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
        if not username or not password:
            raise CommandError(
                "Both BOOTSTRAP_ADMIN_USERNAME and BOOTSTRAP_ADMIN_PASSWORD are required"
            )
        if len(password) < 16:
            raise CommandError("BOOTSTRAP_ADMIN_PASSWORD must contain at least 16 characters")

        User = get_user_model()
        existing_user = User.objects.filter(username=username).first()
        if existing_user is not None:
            if existing_user.is_superuser:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Configured administrator '{username}' already exists; no changes made."
                    )
                )
                return
            raise CommandError(
                f"Username '{username}' already belongs to a non-superuser; "
                "bootstrap will not modify that account"
            )

        # Do not block this named account just because another administrator
        # (for example, the earlier Neon admin123 account) already exists.
        User.objects.create_superuser(
            username=username,
            password=password,
            role=User.Roles.ADMIN,
        )
        self.stdout.write(
            self.style.SUCCESS(f"Administrator '{username}' created successfully.")
        )
