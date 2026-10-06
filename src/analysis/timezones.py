"""Cross-platform timezone/date boundary helpers.

Python's stdlib ``zoneinfo`` uses OS IANA data when available, but clean Windows
Python installations may not ship such a database.  Cost Guard therefore has a
small dependency-free fallback for its zero-config shipped timezone
``Europe/Stockholm`` plus UTC.  Other configured IANA zones remain fully
supported whenever the host Python can resolve them; otherwise startup/report
code receives an actionable error rather than silently using the wrong zone.
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class TimezoneUnavailableError(ValueError):
    pass


def _last_sunday(year: int, month: int) -> date:
    last_day = calendar.monthrange(year, month)[1]
    value = date(year, month, last_day)
    return value - timedelta(days=(value.weekday() - 6) % 7)


class _EuropeStockholm(tzinfo):
    """EU CET/CEST rules used by Europe/Stockholm for Cost Guard's date range.

    The fallback exists for clean Windows Python where stdlib zoneinfo has no
    IANA files.  Historical pre-EU rule archaeology is intentionally outside
    Cost Guard's usage-history horizon; current/future EU rules match the v77
    operational use case.
    """

    _standard = timedelta(hours=1)
    _daylight = timedelta(hours=2)

    @staticmethod
    def _utc_bounds(year: int) -> tuple[datetime, datetime]:
        start = datetime.combine(_last_sunday(year, 3), datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=1)
        end = datetime.combine(_last_sunday(year, 10), datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=1)
        return start, end

    def fromutc(self, dt: datetime) -> datetime:
        if dt.tzinfo is not self:
            raise ValueError("fromutc: dt.tzinfo is not self")
        naive_utc = dt.replace(tzinfo=timezone.utc)
        start, end = self._utc_bounds(dt.year)
        offset = self._daylight if start <= naive_utc < end else self._standard
        return (naive_utc + offset).replace(tzinfo=self)

    def utcoffset(self, dt: datetime | None) -> timedelta:
        if dt is None:
            return self._standard
        # Local wall-time rules: transition at 02:00 standard in March and at
        # 03:00 daylight in October.  Midnight boundaries are always unambiguous.
        start_day = _last_sunday(dt.year, 3)
        end_day = _last_sunday(dt.year, 10)
        local = dt.replace(tzinfo=None)
        start = datetime.combine(start_day, datetime.min.time()) + timedelta(hours=2)
        end = datetime.combine(end_day, datetime.min.time()) + timedelta(hours=3)
        return self._daylight if start <= local < end else self._standard

    def dst(self, dt: datetime | None) -> timedelta:
        return self.utcoffset(dt) - self._standard

    def tzname(self, dt: datetime | None) -> str:
        return "CEST" if self.dst(dt) else "CET"


_STOCKHOLM_FALLBACK = _EuropeStockholm()


def resolve_timezone(timezone_id: str) -> tzinfo:
    value = timezone_id.strip()
    if not value:
        raise TimezoneUnavailableError("Timezone ID cannot be empty")
    if value.upper() in {"UTC", "ETC/UTC", "GMT", "ETC/GMT"}:
        return timezone.utc
    try:
        return ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        if value == "Europe/Stockholm":
            return _STOCKHOLM_FALLBACK
        raise TimezoneUnavailableError(
            f"IANA timezone '{value}' is unavailable in this Python installation; "
            "use a host with IANA zoneinfo data or configure a supported timezone"
        ) from exc


@dataclass(frozen=True, slots=True)
class DateRange:
    text: str
    start_date: str
    end_date: str
    is_range: bool
    start_ms: int
    end_ms: int


def _parse_date(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"Invalid date '{text}'. Expected YYYY-MM-DD.") from exc


def local_date_range(day_text: str, timezone_id: str) -> DateRange:
    day = _parse_date(day_text)
    tz = resolve_timezone(timezone_id)
    start = datetime(day.year, day.month, day.day, tzinfo=tz)
    next_day = day + timedelta(days=1)
    end = datetime(next_day.year, next_day.month, next_day.day, tzinfo=tz)
    normalized = day.isoformat()
    return DateRange(
        text=normalized,
        start_date=normalized,
        end_date=normalized,
        is_range=False,
        start_ms=int(start.timestamp() * 1000),
        end_ms=int(end.timestamp() * 1000),
    )


def local_report_range(target: str, timezone_id: str) -> DateRange:
    pieces = target.split(":")
    if len(pieces) == 1:
        return local_date_range(target, timezone_id)
    if len(pieces) != 2 or not pieces[0].strip() or not pieces[1].strip():
        raise ValueError(f"Invalid date target '{target}'. Expected YYYY-MM-DD or YYYY-MM-DD:YYYY-MM-DD.")
    first = local_date_range(pieces[0], timezone_id)
    last = local_date_range(pieces[1], timezone_id)
    if first.start_ms > last.start_ms:
        raise ValueError(f"Invalid date range '{target}'. Start date must not be after end date.")
    return DateRange(
        text=f"{first.start_date}:{last.end_date}",
        start_date=first.start_date,
        end_date=last.end_date,
        is_range=True,
        start_ms=first.start_ms,
        end_ms=last.end_ms,
    )


def local_day_start_ms(timezone_id: str, *, now_ms: int | None = None) -> int:
    tz = resolve_timezone(timezone_id)
    now = datetime.now(tz=timezone.utc) if now_ms is None else datetime.fromtimestamp(now_ms / 1000, tz=timezone.utc)
    local = now.astimezone(tz)
    midnight = datetime(local.year, local.month, local.day, tzinfo=tz)
    return int(midnight.timestamp() * 1000)


def utc_month_start_ms(*, now_ms: int | None = None) -> int:
    now = datetime.now(tz=timezone.utc) if now_ms is None else datetime.fromtimestamp(now_ms / 1000, tz=timezone.utc)
    return int(datetime(now.year, now.month, 1, tzinfo=timezone.utc).timestamp() * 1000)


def format_local_timestamp(ms: int, timezone_id: str, pattern: str = "%Y-%m-%d %H:%M") -> str:
    if ms <= 0:
        return "unknown"
    value = datetime.fromtimestamp(ms / 1000, tz=timezone.utc).astimezone(resolve_timezone(timezone_id))
    return value.strftime(pattern)


def easter_sunday(year: int) -> date:
    # Gregorian Meeus/Jones/Butcher algorithm, matching the v77 implementation.
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def swedish_public_holidays(year: int) -> frozenset[date]:
    dates = {
        date(year, 1, 1), date(year, 1, 6), date(year, 5, 1), date(year, 6, 6),
        date(year, 12, 25), date(year, 12, 26),
    }
    easter = easter_sunday(year)
    dates.update({easter - timedelta(days=2), easter, easter + timedelta(days=1), easter + timedelta(days=39), easter + timedelta(days=49)})
    for day in range(20, 27):
        candidate = date(year, 6, day)
        if candidate.weekday() == 5:
            dates.add(candidate)
            break
    candidate = date(year, 10, 31)
    while candidate.weekday() != 5:
        candidate += timedelta(days=1)
    dates.add(candidate)
    return frozenset(dates)


@dataclass(frozen=True, slots=True)
class WorkdayStats:
    total: int
    current_day: int
    remaining_including_today: int
    today_is_workday: bool


def workday_stats(
    timezone_id: str,
    calendar_name: str = "SE",
    *,
    now_ms: int | None = None,
) -> WorkdayStats:
    """Return v77-compatible workday progression for the current UTC billing month."""
    utc_now = datetime.now(tz=timezone.utc) if now_ms is None else datetime.fromtimestamp(now_ms / 1000, tz=timezone.utc)
    year, month = utc_now.year, utc_now.month
    local_now = utc_now.astimezone(resolve_timezone(timezone_id))
    holidays = swedish_public_holidays(year) if (calendar_name or "SE").upper() == "SE" else frozenset()
    days = calendar.monthrange(year, month)[1]
    total = 0
    elapsed = 0
    today_is_workday = False
    same_month = local_now.year == year and local_now.month == month
    local_ordinal = local_now.year * 10000 + local_now.month * 100 + local_now.day
    start_ordinal = year * 10000 + month * 100 + 1
    end_ordinal = year * 10000 + month * 100 + days
    for day_number in range(1, days + 1):
        current = date(year, month, day_number)
        is_workday = current.weekday() < 5 and current not in holidays
        if not is_workday:
            continue
        total += 1
        if local_ordinal > end_ordinal or (same_month and day_number <= local_now.day):
            elapsed += 1
        if same_month and day_number == local_now.day:
            today_is_workday = True
    if local_ordinal < start_ordinal:
        elapsed = 0
        today_is_workday = False
    if local_ordinal > end_ordinal:
        elapsed = total
        today_is_workday = False
    remaining = max(0, total - elapsed + (1 if today_is_workday else 0))
    return WorkdayStats(total, elapsed, remaining, today_is_workday)
