import calendar
from datetime import datetime, timedelta, timezone


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _start_of_day(dt: datetime) -> datetime:
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def _end_of_day(dt: datetime) -> datetime:
    return dt.replace(hour=23, minute=59, second=59, microsecond=999999)


_MONTH_NAMES_PT = [
    "",
    "Janeiro",
    "Fevereiro",
    "Março",
    "Abril",
    "Maio",
    "Junho",
    "Julho",
    "Agosto",
    "Setembro",
    "Outubro",
    "Novembro",
    "Dezembro",
]


def parse_today() -> tuple[datetime, datetime, str]:
    now = _now()
    label = f"Hoje ({now.day:02d}/{now.month:02d})"
    return _start_of_day(now), _end_of_day(now), label


def parse_yesterday() -> tuple[datetime, datetime, str]:
    now = _now()
    yesterday = now - timedelta(days=1)
    label = f"Ontem ({yesterday.day:02d}/{yesterday.month:02d})"
    return _start_of_day(yesterday), _end_of_day(yesterday), label


def parse_this_week() -> tuple[datetime, datetime, str]:
    now = _now()
    # Monday of current week
    monday = now - timedelta(days=now.weekday())
    sunday = monday + timedelta(days=6)
    label = (
        f"Esta semana "
        f"({monday.day:02d}/{monday.month:02d} a {sunday.day:02d}/{sunday.month:02d})"
    )
    return _start_of_day(monday), _end_of_day(sunday), label


def parse_this_month() -> tuple[datetime, datetime, str]:
    now = _now()
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    label = f"{_MONTH_NAMES_PT[now.month]}/{now.year}"
    return start, _end_of_day(now), label


def parse_last_month() -> tuple[datetime, datetime, str]:
    now = _now()
    first_of_this = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month_end = first_of_this - timedelta(days=1)
    last_month_start = last_month_end.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    last_day = calendar.monthrange(last_month_start.year, last_month_start.month)[1]
    last_month_end_full = last_month_start.replace(
        day=last_day, hour=23, minute=59, second=59, microsecond=999999
    )
    label = f"{_MONTH_NAMES_PT[last_month_start.month]}/{last_month_start.year}"
    return last_month_start, last_month_end_full, label
