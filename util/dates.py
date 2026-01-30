from datetime import datetime, timedelta


def parse_date(d:str):
    if not d:
        return d
    d = d.lower()
    if d == "yesterday":
        return datetime.now() - timedelta(days=1)
    elif d == "today":
        return datetime.now()
    else:
        datetime.strptime(d, "%m/%d/%Y")

def as_casual_str(d:datetime):
    today = datetime.now()

    diff = d.date() - today.date()
    days = diff.days

    if -30 < days < 30:
        s = {
            0: 'today',
            1: 'tomorrow',
            -1: 'yesterday',
            -7: '-1 week ago',
            7: 'in 1 week'
        }.get(days)
        if s:
            return s
        if days < 0:
            return f"{days} days ago"
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
