import datetime
from argparse import ArgumentTypeError


def parse_interval(value: str) -> datetime.timedelta:
    if not value:
        return None
    s = str(value).strip().lower()
    try:
        # Plain seconds
        seconds = int(s)
        return datetime.timedelta(seconds=seconds)
    except ValueError:
        pass
    # Suffixed formats
    if s.endswith("ms"):
        num = float(s[:-2])
        return datetime.timedelta(milliseconds=num)
    if s.endswith("s"):
        num = float(s[:-1])
        return datetime.timedelta(seconds=num)
    if s.endswith("m"):
        num = float(s[:-1])
        return datetime.timedelta(minutes=num)
    if s.endswith("h"):
        num = float(s[:-1])
        return datetime.timedelta(hours=num)
    if s.endswith("d"):
        num = float(s[:-1])
        return datetime.timedelta(days=num)
    # Fallback: try float seconds
    try:
        return datetime.timedelta(seconds=float(s))
    except Exception:
        raise ArgumentTypeError(f"Unrecognized interval format: {value}")


def to_days(interval: datetime.timedelta) -> float:
    """You can get just the int of days using the .days property, this returns fractional days too"""
    total_days_float = interval.total_seconds() / (24 * 60 * 60)
    return total_days_float


def guess_parse(value: str) -> datetime.datetime | bool | str | float | int:
    # Check if value is actually a string
    if not isinstance(value, str):
        return value

    # Handle empty or whitespace-only strings
    if not value or not value.strip():
        return value

    value = value.strip()

    # Try boolean first (case-insensitive, excluding '1' and '0')
    if value.lower() in ('true', 'false'):
        return value.lower() == 'true'

    # Try integer
    try:
        # Check if it looks like an integer (no decimal point)
        if '.' not in value and 'e' not in value.lower():
            return int(value)
    except ValueError:
        pass

    # Try float
    try:
        return float(value)
    except ValueError:
        pass

    # Try ISO datetime parsing first (most common in APIs)
    try:
        return datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        pass

    # Try other common datetime formats
    datetime_formats = [
        '%Y-%m-%d %H:%M:%S',  # 2023-12-25 14:30:00
        '%Y-%m-%d',  # 2023-12-25
        '%m/%d/%Y',  # 12/25/2023
        '%d/%m/%Y',  # 25/12/2023
        '%Y/%m/%d',  # 2023/12/25
        '%m-%d-%Y',  # 12-25-2023
        '%d-%m-%Y',  # 25-12-2023
    ]

    for fmt in datetime_formats:
        try:
            return datetime.datetime.strptime(value, fmt)
        except ValueError:
            continue

    # If nothing else worked, return as string
    return value


def to_utc_iso_8601(d: datetime.datetime) -> str:
    # Convert to UTC if it has timezone info
    if d.tzinfo is not None:
        d = d.astimezone(datetime.timezone.utc).replace(tzinfo=None)

    # Format as ISO 8601 string with Z suffix to indicate UTC
    return d.isoformat() + 'Z'
