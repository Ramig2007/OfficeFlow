"""Regression tests for the hour-only reservation picker."""

from datetime import datetime

from django import forms
from django.utils import timezone

from workspace.forms import BookingForm, HourOnlyDateTimeWidget


def test_start_and_end_offer_valid_full_hours_only():
    form = BookingForm()
    expected = [f"{hour:02d}:00" for hour in range(24)]
    for field_name in ("starts_at", "ends_at"):
        widget = form.fields[field_name].widget
        assert isinstance(widget, HourOnlyDateTimeWidget)
        assert isinstance(widget.widgets[1], forms.Select)
        assert [value for value, _ in widget.widgets[1].choices] == expected


def test_prefilled_hour_is_selected_on_edit():
    initial = timezone.make_aware(datetime(2026, 11, 20, 15, 0))
    form = BookingForm(initial={"starts_at": initial})
    html = str(form["starts_at"])
    assert 'name="starts_at_0"' in html
    assert 'value="2026-11-20"' in html
    assert 'name="starts_at_1"' in html
    assert 'value="15:00" selected' in html


def test_booking_form_accepts_hour_selection(room, window):
    start = timezone.localtime(window[0])
    end = timezone.localtime(window[1])
    form = BookingForm(data={
        "room": str(room.pk),
        "title": "Проверка часов",
        "starts_at_0": start.date().isoformat(),
        "starts_at_1": start.strftime("%H:%M"),
        "ends_at_0": end.date().isoformat(),
        "ends_at_1": end.strftime("%H:%M"),
        "notes": "",
    })
    assert form.is_valid(), form.errors.as_json()
