# Contains utility functions that are shared across multiple handler files

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Define the time zone for Saint Petersburg
ST_PETERSBURG = ZoneInfo('Europe/Moscow')  # Saint Petersburg uses Moscow's time zone

def convert_to_utc(date_str: str, time_str: str, add_hours: int = 0) -> str:
    """
    Converts a date and time string in 'YYYY-MM-DD' and 'HH:MM' format from
    Saint Petersburg time zone to UTC ISO8601 string.
    Optionally adds hours to the time.
    """
    local_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    local_dt = local_dt.replace(tzinfo=ST_PETERSBURG)
    if add_hours:
        local_dt += timedelta(hours=add_hours)
    utc_dt = local_dt.astimezone(ZoneInfo('UTC'))
    return utc_dt.isoformat()
