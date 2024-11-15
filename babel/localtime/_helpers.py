try:
    import pytz
except ModuleNotFoundError:
    pytz = None
    import zoneinfo

def _get_tzinfo(tzenv: str):
    """Get the tzinfo from `zoneinfo` or `pytz`

    :param tzenv: timezone in the form of Continent/City
    :return: tzinfo object or None if not found
    """
    if pytz is not None:
        try:
            return pytz.timezone(tzenv)
        except pytz.exceptions.UnknownTimeZoneError:
            return None
    else:
        try:
            return zoneinfo.ZoneInfo(tzenv)
        except zoneinfo.ZoneInfoNotFoundError:
            return None
