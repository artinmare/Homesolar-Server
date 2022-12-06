from datetime import datetime, timedelta, date
from json import JSONEncoder
import pytz


class DateTimeEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.timestamp()


def get_timezone():
    from ..utils import config
    timezone = config.homesolar_config['INFLUXDB']['timezone']
    return pytz.timezone(timezone)


def stringify_timestamp(timestamp):
    return datetime.utcfromtimestamp(timestamp).strftime('%Y-%m-%dT%H:%M:%SZ')


def get_today():
    return datetime.now(get_timezone()).replace(hour=0, minute=0, second=0).timestamp()


def get_next_day(timestamp):
    return (datetime.utcfromtimestamp(timestamp) + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%SZ')


def get_first_day_of_month(timestamp):
    return datetime.fromtimestamp(timestamp, get_timezone()) \
        .replace(day=1) \
        .astimezone(pytz.utc) \
        .strftime('%Y-%m-%dT%H:%M:%SZ')


def get_last_day_of_month(timestamp):
    next_month = datetime.fromtimestamp(timestamp, get_timezone()).replace(day=28) + timedelta(days=4)
    return (next_month - timedelta(days=next_month.day) + timedelta(days=1)) \
        .astimezone(pytz.utc) \
        .strftime('%Y-%m-%dT%H:%M:%SZ')


def get_first_day_of_year(timestamp):
    return datetime.fromtimestamp(timestamp, get_timezone()) \
        .replace(day=1, month=1) \
        .astimezone(pytz.utc) \
        .strftime('%Y-%m-%dT%H:%M:%SZ')


def get_last_day_of_year(timestamp):
    return (datetime.fromtimestamp(timestamp, get_timezone())
            .replace(day=31, month=12) + timedelta(days=1)) \
        .astimezone(pytz.utc) \
        .strftime('%Y-%m-%dT%H:%M:%SZ')


def get_date_pair(date, timescale):
    if timescale == "MONTH":
        start_time = get_first_day_of_month(date)
        stop_time = get_last_day_of_month(date)
    elif timescale == "YEAR":
        start_time = get_first_day_of_year(date)
        stop_time = get_last_day_of_year(date)
    else:
        start_time = stringify_timestamp(date)
        stop_time = get_next_day(date)

    return start_time, stop_time
