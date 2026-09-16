import time
from datetime import datetime, timedelta, timezone


def _to_aware(d: datetime) -> datetime:
    """Make a datetime timezone-aware, assuming local time if naive."""
    if d.tzinfo is None:
        local_offset = timedelta(seconds=-time.timezone if not time.daylight else -time.altzone)
        return d.replace(tzinfo=timezone(local_offset))
    return d


def parse_date(d: str) -> datetime:
    if not d:
        return d
    d = d.lower().strip()
    if d == "yesterday":
        return datetime.now() - timedelta(days=1)
    elif d == "today":
        return datetime.now()
    else:
        return datetime.strptime(d, "%m/%d/%Y")


def are_the_same(d: datetime | str, d2: datetime | str) -> bool:
    """Compare two datetimes for equality, handling strings and naive datetimes.
    Naive datetimes are assumed to be local time."""

    def normalize(val: datetime | str) -> datetime:
        if isinstance(val, str):
            val = parse_date(val)
        if not isinstance(val, datetime):
            raise TypeError(f"Expected datetime or str, got {type(val)}")
        return _to_aware(val)

    return normalize(d) == normalize(d2)


def as_casual_str(d: datetime) -> str:
    today = datetime.now()
    diff = d.date() - today.date()
    days = diff.days

    if -30 < days < 30:
        s = {
            0: 'today',
            1: 'tomorrow',
            -1: 'yesterday',
            -7: '1 week ago',
            7: 'in 1 week',
        }.get(days)
        if s:
            return s
        if days < 0:
            return f"{abs(days)} days ago"
        return f"in {days} days"
    return d.strftime("%m/%d/%Y")


if __name__ == '__main__':
    now = datetime.now()
    today = now - timedelta(hours=1)
    tomorrow = now + timedelta(days=1)
    yesterday = now - timedelta(days=1)
    next_week = now + timedelta(weeks=1)
    days_ago = now - timedelta(weeks=2)
    months_ago = now - timedelta(days=65)

    print("today", as_casual_str(today))
    print("tomorrow", as_casual_str(tomorrow))
    print("yesterday", as_casual_str(yesterday))
    print("next_week", as_casual_str(next_week))
    print("days ago", as_casual_str(days_ago))
    print("months ago", as_casual_str(months_ago))

    # are_the_same examples
    aware = datetime.now(tz=timezone.utc)
    naive = datetime.utcnow()
    print("same?", are_the_same(aware, naive))
