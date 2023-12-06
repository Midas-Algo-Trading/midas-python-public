from datetime import date, timedelta, datetime, time
from pytz import timezone
from typing import Optional

import pandas_market_calendars as mcal

"""For utility functions that incorporate time."""


def get_tomorrow(tz=timezone('US/Eastern')) -> date:
    """
    Returns tomorrow's date.
    """
    return datetime.now(tz).date() + timedelta(days=1)


def get_yesterday(tz=timezone('US/Eastern')) -> date:
    """
    Returns tomorrow's date.
    """
    return datetime.now(tz).date() - timedelta(days=1)


def get_today(tz=timezone('US/Eastern')) -> date:
    """
    Returns today's date.
    """
    return datetime.now(tz).date()


def get_market_dates(start: date,
                     end: date,
                     exchange: str = 'NYSE'
                     ) -> list[date]:
    """
    Returns the dates the market has been open between 'start' and 'end' dates.

    Parameters
    ----------
    start : str
        Dates before this date will not be returned.
    end : str
        Dates after this date will not be returned.
    exchange : optional str, default 'NYSE'
        Dates for when this stock exchange was opened will be returned.
    Returns
    -------
    list of str
        of the dates the inputted stock exchange was open between the 'start' date and 'end' date.

    """
    nyse_calendar = mcal.get_calendar(exchange)
    days = nyse_calendar.valid_days(start_date=start, end_date=end)
    return [day.to_pydatetime().date() for day in days]


def get_market_open_time() -> time:
    return time(9, 30)


def get_market_close_time() -> time:
    return time(16)


def get_current_datetime(tz=timezone('US/Eastern')) -> datetime:
    return datetime.now(tz)


def get_current_time(tz=timezone('US/Eastern')) -> time:
    return datetime.now(tz).time()


def get_next_market_open_date(start: date) -> date:
    return get_market_dates(start=start, end=start + timedelta(days=4))[0]


def add_to_mkt_date(delta: int, day: Optional[date] = None) -> date:
    if not day:
        day = get_today()

    if delta >= 0:
        days = [day, day + timedelta(days=max(delta * (7 / 3), 5))]
    else:
        days = [day - timedelta(days=1), day + timedelta(days=min(delta * (7 / 3), -5))]

    market_dates = get_market_dates(min(days), max(days))

    return market_dates[delta]
