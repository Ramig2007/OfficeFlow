"""Create or repair the explicitly configured Render administrator.

The command only touches the exact username supplied through Render's
BOOTSTRAP_ADMIN_USERNAME. While the bootstrap variables remain configured,
its password is reset to BOOTSTRAP_ADMIN_PASSWORD on every service start.
Remove both variables after confirming the login. Never print the password.
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = "Create or repair the explicitly configured Render administrator."

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
        user = User.objects.filter(username=username).first()
        created = user is None
        if created:
            user = User(username=username)

        # Supplying these Render-only secrets is an explicit instruction to
        # provision this exact account. Repair an existing member/superuser
        # without touching any other account or profile data.
        user.role = User.Roles.ADMIN
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.set_password(password)
        user.save()

        action = "created" if created else "updated"
        self.stdout.write(
            self.style.SUCCESS(f"Render administrator '{username}' {action} successfully.")
        )
