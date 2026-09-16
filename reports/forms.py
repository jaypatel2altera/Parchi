from datetime import timedelta

from django import forms
from django.utils import timezone


class DateRangeForm(forms.Form):
    start = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    end = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def range(self):
        today = timezone.localdate()
        start = self.cleaned_data.get("start") if self.is_valid() else None
        end = self.cleaned_data.get("end") if self.is_valid() else None
        start = start or (today - timedelta(days=30))
        end = end or today
        start_dt = timezone.make_aware(timezone.datetime.combine(start, timezone.datetime.min.time()))
        end_dt = timezone.make_aware(timezone.datetime.combine(end, timezone.datetime.max.time()))
        return start_dt, end_dt
