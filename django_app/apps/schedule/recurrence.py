from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Iterable, List

from dateutil import rrule
from django.utils import timezone

from .models import Schedule, ScheduleRecurrence


FREQ_MAP = {
    "DAILY": rrule.DAILY,
    "WEEKLY": rrule.WEEKLY,
    "MONTHLY": rrule.MONTHLY,
    "YEARLY": rrule.YEARLY,
}


def create_recurrence(schedule: Schedule, data: dict | None) -> ScheduleRecurrence | None:
    if not data or not data.get("freq"):
        schedule.recurrence_id = None
        ScheduleRecurrence.objects.filter(schedule=schedule).delete()
        return None

    freq = data.get("freq")
    interval = int(data.get("interval", 1))
    weekdays = data.get("week_days") or data.get("weekDays") or []
    monthdays = data.get("month_days") or data.get("monthDays") or []
    count = data.get("count")
    until = data.get("until")
    timezone_name = data.get("timezone") or "Asia/Seoul"
    metadata = {
        "original_request": data,
    }

    if until:
        until_dt = datetime.fromisoformat(until)
        if timezone.is_naive(until_dt):
            until_dt = timezone.make_aware(until_dt, timezone.get_current_timezone())
    else:
        until_dt = None

    recurrence, _ = ScheduleRecurrence.objects.update_or_create(
        schedule=schedule,
        defaults={
            "freq": freq,
            "interval": interval,
            "week_days": weekdays,
            "month_days": monthdays,
            "count": count,
            "until": until_dt,
            "timezone": timezone_name,
            "metadata": metadata,
        },
    )
    return recurrence


def expand_recurrences(
    schedules: Iterable[Schedule],
    *,
    range_start: datetime,
    range_end: datetime,
    max_instances: int = 500,
) -> List["Occurrence"]:
    occurrence_maps: List[Occurrence] = []
    base_delta_cache = {}

    for schedule in schedules:
        recurrence = getattr(schedule, "recurrence", None)
        if not recurrence:
            occurrence_maps.append(
                Occurrence(
                    base=schedule,
                    start=schedule.start_date,
                    end=schedule.end_date,
                    instance_id=str(schedule.pk),
                )
            )
            continue

        freq = FREQ_MAP.get(recurrence.freq, rrule.DAILY)
        rule_kwargs = {
            "dtstart": schedule.start_date,
            "freq": freq,
            "interval": recurrence.interval or 1,
        }

        if recurrence.count:
            rule_kwargs["count"] = recurrence.count

        if recurrence.until:
            rule_kwargs["until"] = recurrence.until

        if recurrence.week_days:
            byweekday = []
            for entry in recurrence.week_days:
                if isinstance(entry, str) and hasattr(rrule, entry):
                    byweekday.append(getattr(rrule, entry))
                elif isinstance(entry, int) and 0 <= entry <= 6:
                    byweekday.append(rrule.weekday(entry))
            if byweekday:
                rule_kwargs["byweekday"] = byweekday

        if recurrence.month_days:
            rule_kwargs["bymonthday"] = recurrence.month_days

        rule = rrule.rrule(**rule_kwargs)
        base_delta = base_delta_cache.get(schedule.pk)
        if base_delta is None:
            base_delta = schedule.end_date - schedule.start_date
            if base_delta.total_seconds() <= 0:
                base_delta = timedelta(hours=1)
            base_delta_cache[schedule.pk] = base_delta

        for idx, start_dt in enumerate(rule.between(range_start, range_end, inc=True)):
            if idx >= max_instances:
                break
            occurrence_maps.append(
                Occurrence(
                    base=schedule,
                    start=start_dt,
                    end=start_dt + base_delta,
                    instance_id=f"{schedule.pk}-{start_dt.isoformat()}",
                )
            )

    return occurrence_maps


@dataclass
class Occurrence:
    base: Schedule
    start: datetime
    end: datetime
    instance_id: str = field(default="")
