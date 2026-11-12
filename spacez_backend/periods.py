"""Anniversary-based billing periods.

Start 10 May → end 9 June → next 10 June → 9 July.
Never start + 30 days. Month-end anchors clamp only for short months
(31 Jan → 28/29 Feb → 31 Mar), they do not permanently drift to the 1st.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from typing import NamedTuple


class Period(NamedTuple):
    start: date
    end: date


def parse_iso_date(value) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    return date.fromisoformat(str(value)[:10])


def add_days(value: date, days: int) -> date:
    return value + timedelta(days=days)


def days_between(start: date, end: date) -> int:
    return (end - start).days


def period_length(start: date, end: date) -> int:
    """Inclusive day count (10 May → 9 Jun = 31)."""
    return days_between(start, end) + 1


def clamp_day(year: int, month: int, day: int) -> date:
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(day, last))


def add_months(value: date, months: int, *, day: int | None = None) -> date:
    """Advance calendar months, clamping to the last valid day for `day` (default: value.day)."""
    anchor = day if day is not None else value.day
    month_index = value.year * 12 + (value.month - 1) + months
    year, month = divmod(month_index, 12)
    month += 1
    return clamp_day(year, month, anchor)


def period_from_start(start: date, *, anchor_day: int | None = None) -> Period:
    day = anchor_day or start.day
    next_start = add_months(start, 1, day=day)
    end = next_start - timedelta(days=1)
    return Period(start=start, end=end)


def next_period(period_end: date, *, anchor_day: int | None = None) -> Period:
    start = add_days(period_end, 1)
    day = anchor_day or start.day
    # Snap short-month stand-ins (e.g. 28 Feb after a 31st anchor) back to the anniversary day
    # in the following month when needed.
    snapped = clamp_day(start.year, start.month, day)
    if snapped > start:
        start = snapped
    elif snapped < start:
        start = add_months(start, 1, day=day)
    return period_from_start(start, anchor_day=day)


def current_period_for(anchor: date, reference: date | None = None) -> Period:
    reference = reference or date.today()
    day = anchor.day
    period = period_from_start(anchor, anchor_day=day)
    guard = 0
    while period.end < reference and guard < 600:
        period = next_period(period.end, anchor_day=day)
        guard += 1
    return period


class Proration(NamedTuple):
    total_days: int
    remaining_days: int
    daily_rate_delta: float
    amount_delta: int
    adjustment: int
    old_amount: int
    new_amount: int


def prorate(*, old_amount: int, new_amount: int, period_start: date, period_end: date, change_date: date) -> Proration:
    total_days = period_length(period_start, period_end)
    effective = period_start if change_date < period_start else change_date
    remaining_days = max(0, min(total_days, period_length(effective, period_end)))
    amount_delta = new_amount - old_amount
    daily_rate_delta = amount_delta / total_days if total_days else 0
    adjustment = round(daily_rate_delta * remaining_days)
    return Proration(
        total_days=total_days,
        remaining_days=remaining_days,
        daily_rate_delta=round(daily_rate_delta, 2),
        amount_delta=amount_delta,
        adjustment=adjustment,
        old_amount=old_amount,
        new_amount=new_amount,
    )
