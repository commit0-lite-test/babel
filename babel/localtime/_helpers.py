from typing import Optional
import zoneinfo

try:
    import pytz  # type: ignore
except ModuleNotFoundError:
    pytz = None


def _get_tzinfo(tzenv: str) -> Optional[zoneinfo.ZoneInfo]:
    """Get the tzinfo from `zoneinfo` or `pytz`

    :param tzenv: timezone in the form of Continent/City
    :return: tzinfo object or None if not found
    """
    if pytz is not None:
        try:
            return pytz.timezone(tzenv)  # type: ignore
        except pytz.exceptions.UnknownTimeZoneError:  # type: ignore
            return None
    else:
        try:
            return zoneinfo.ZoneInfo(tzenv)
        except zoneinfo.ZoneInfoNotFoundError:
            return None
