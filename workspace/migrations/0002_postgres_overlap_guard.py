"""PostgreSQL-enforced room/time exclusion constraint, including pending VIP holds.

SQLite is permitted for UI smoke tests; PostgreSQL is required for real concurrency safety.
"""
from django.db import migrations


CONSTRAINT = "booking_room_no_overlap"


def add_guard(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("CREATE EXTENSION IF NOT EXISTS btree_gist;")
    schema_editor.execute("""
        ALTER TABLE workspace_booking
        ADD CONSTRAINT booking_room_no_overlap
        EXCLUDE USING GIST (
            room_id WITH =,
            tstzrange(starts_at, ends_at, '[)') WITH &&
        ) WHERE (status IN ('confirmed', 'pending'));
    """)


def remove_guard(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("ALTER TABLE workspace_booking DROP CONSTRAINT IF EXISTS booking_room_no_overlap;")


class Migration(migrations.Migration):
    dependencies = [("workspace", "0001_initial")]
    operations = [migrations.RunPython(add_guard, reverse_code=remove_guard)]
