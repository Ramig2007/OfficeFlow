"""Create the very first Render admin from a short-lived secret.

Use BOOTSTRAP_ADMIN_USERNAME and BOOTSTRAP_ADMIN_PASSWORD only for the first
deployment; remove the variables afterward. Never reset an existing password.
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = "Create the first Render administrator; existing users are never modified."

    @transaction.atomic
    def handle(self, *args, **options):
        username = os.getenv("BOOTSTRAP_ADMIN_USERNAME", "").strip()
        password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
        if not username or not password:
            raise CommandError("Both BOOTSTRAP_ADMIN_USERNAME and BOOTSTRAP_ADMIN_PASSWORD are required")
        if len(password) < 16:
            raise CommandError("BOOTSTRAP_ADMIN_PASSWORD must contain at least 16 characters")

        User = get_user_model()
        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write("A superuser already exists; bootstrap skipped.")
            return
        if User.objects.filter(username=username).exists():
            raise CommandError("Username already exists; bootstrap will not alter that account")

        # The project's custom role must grant access to OfficeFlow approvals.
        User.objects.create_superuser(
            username=username,
            password=password,
            role=User.Roles.ADMIN,
        )
        self.stdout.write(self.style.SUCCESS("First administrator created successfully."))
