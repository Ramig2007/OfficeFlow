from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from workspace.models import AuditEvent, Booking, Room, User
from workspace.services import audit


@admin.register(User)
class OfficeUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("OfficeFlow", {"fields": ("role", "department")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("OfficeFlow", {"fields": ("role", "department")}),)
    list_display = ("username", "email", "role", "department", "is_active")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        audit(request.user, "user.admin_updated" if change else "user.admin_created", obj.pk)


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("name", "location", "capacity", "is_vip", "is_active")
    prepopulated_fields = {"slug": ("name",)}

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        audit(request.user, "room.admin_updated" if change else "room.admin_created", obj.pk)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("title", "room", "creator", "starts_at", "ends_at", "status")
    readonly_fields = ("created_at", "updated_at")
    def has_add_permission(self, request):
        return False  # business rules are enforced by the booking service

    def has_change_permission(self, request, obj=None):
        return False  # avoid bypassing VIP approval/overlap logic

    def has_delete_permission(self, request, obj=None):
        return False  # preserve history


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "action", "target")
    readonly_fields = [field.name for field in AuditEvent._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
