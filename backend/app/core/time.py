import datetime as dt


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def business_date() -> dt.date:
    """'Today' for billing decisions. Business timezone is a team decision —
    default UTC (see architecture doc §7)."""
    return utc_now().date()
