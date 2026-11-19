import csv

from django.db.models import Count, Q
from django.http import HttpResponse
from django.utils.dateparse import parse_date

from workspace.models import Booking


def safe_parse_date(value):
    try:
        return parse_date(value or "")
    except ValueError:
        return None


def booking_report(request):
    queryset = Booking.objects.select_related("room", "creator").order_by("-starts_at")
    start = safe_parse_date(request.GET.get("from", ""))
    end = safe_parse_date(request.GET.get("to", ""))
    room = request.GET.get("room", "").strip()
    if start:
        queryset = queryset.filter(starts_at__date__gte=start)
    if end:
        queryset = queryset.filter(starts_at__date__lte=end)
    if room.isdigit():
        queryset = queryset.filter(room_id=int(room))
    return queryset


def report_summary(queryset):
    return queryset.aggregate(
        total=Count("pk"), confirmed=Count("pk", filter=Q(status=Booking.Status.CONFIRMED)),
        pending=Count("pk", filter=Q(status=Booking.Status.PENDING)),
        cancelled=Count("pk", filter=Q(status=Booking.Status.CANCELLED)),
        rejected=Count("pk", filter=Q(status=Booking.Status.REJECTED)),
    )


def _safe_csv_cell(value):
    """Prevent spreadsheet formula execution when CSV is opened in Excel/Sheets."""
    text = str(value or "")
    if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r", "\n")):
        return "'" + text
    return text


def export_csv(queryset):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="officeflow-bookings.csv"'
    response.write("\ufeff")
    writer = csv.writer(response, delimiter=";")
    writer.writerow(["ID", "Переговорная", "Организатор", "Тема", "Начало (UTC)", "Окончание (UTC)", "Статус"])
    for item in queryset.iterator():
        writer.writerow([
            item.pk, _safe_csv_cell(item.room.name), _safe_csv_cell(item.creator.username),
            _safe_csv_cell(item.title), item.starts_at.isoformat(), item.ends_at.isoformat(), item.get_status_display(),
        ])
    return response
