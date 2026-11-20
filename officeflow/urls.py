from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from workspace import api, views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/login/", views.OfficeLoginView.as_view(), name="login"),
    path("accounts/logout/", views.logout_view, name="logout"),
    path("accounts/register/", views.register_view, name="register"),
    path("", views.dashboard, name="dashboard"),
    path("schedule/", views.schedule, name="schedule"),
    path("rooms/", views.rooms, name="rooms"),
    path("rooms/<str:slug>/", views.room_detail, name="room-detail"),
    path("bookings/new/", views.booking_create, name="booking-create"),
    path("bookings/<int:pk>/edit/", views.booking_edit, name="booking-edit"),
    path("bookings/<int:pk>/cancel/", views.booking_cancel, name="booking-cancel"),
    path("my-bookings/", views.my_bookings, name="my-bookings"),
    path("approvals/", views.approvals, name="approvals"),
    path("approvals/<int:pk>/<str:action>/", views.approval_action, name="approval-action"),
    path("control/rooms/", views.manage_rooms, name="manage-rooms"),
    path("control/rooms/new/", views.manage_room_form, name="manage-room-new"),
    path("control/rooms/<int:pk>/", views.manage_room_form, name="manage-room-edit"),
    path("control/users/", views.manage_users, name="manage-users"),
    path("reports/", views.reports, name="reports"),
    path("reports/export.csv", views.report_csv, name="report-csv"),
    path("profile/", views.profile, name="profile"),
    path("api/v1/", include(api.router.urls)),
    path("api/v1/schedule/", api.ScheduleAPI.as_view(), name="api-schedule"),
    path("api/v1/reports/summary/", api.ReportSummaryAPI.as_view(), name="api-report"),
    path("api/v1/reports/export.csv", api.ExportAPI.as_view(), name="api-export"),
    path("api/schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="api-schema"), name="swagger-ui"),
    path("health/live/", views.health_live, name="health-live"),
    path("health/ready/", views.health_ready, name="health-ready"),
]

# Internal Compose metrics are protected by Nginx. Render serves Gunicorn directly,
# so do not expose potentially sensitive /metrics on the public Internet.
if getattr(settings, "OFFICEFLOW_EXPOSE_METRICS", True):
    urlpatterns.append(path("", include("django_prometheus.urls")))
