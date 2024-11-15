from __future__ import annotations

from babel.core import get_global


def get_official_languages(
    territory: str, regional: bool = False, de_facto: bool = False
) -> tuple[str, ...]:
    """
    Get the official language(s) for the given territory.

    The language codes, if any are known, are returned in order of descending popularity.

    If the `regional` flag is set, then languages which are regionally official are also returned.

    If the `de_facto` flag is set, then languages which are "de facto" official are also returned.

    .. warning:: Note that the data is as up to date as the current version of the CLDR used
                 by Babel.  If you need scientifically accurate information, use another source!

    :param territory: Territory code
    :type territory: str
    :param regional: Whether to return regionally official languages too
    :type regional: bool
    :param de_facto: Whether to return de-facto official languages too
    :type de_facto: bool
    :return: Tuple of language codes
    :rtype: tuple[str]
    """
    territory_data = get_global("territory_languages").get(territory, {})
    official_languages = []

    for lang, data in territory_data.items():
        status = data.get("official_status")
        if (
            status == "official"
            or (regional and status == "official_regional")
            or (de_facto and status == "de_facto_official")
        ):
            official_languages.append(lang)

    # Sort languages by population percentage (descending order)
    official_languages.sort(
        key=lambda x: territory_data[x].get("population_percent", 0),
        reverse=True,
    )

    return tuple(official_languages)


def get_territory_language_info(
    territory: str,
) -> dict[str, dict[str, float | str | None]]:
    """
    Get a dictionary of language information for a territory.

    The dictionary is keyed by language code; the values are dicts with more information.

    The following keys are currently known for the values:

    * `population_percent`: The percentage of the territory's population speaking the
                            language.
    * `official_status`: An optional string describing the officiality status of the language.
                         Known values are "official", "official_regional" and "de_facto_official".

    .. warning:: Note that the data is as up to date as the current version of the CLDR used
                 by Babel.  If you need scientifically accurate information, use another source!

    .. note:: Note that the format of the dict returned may change between Babel versions.

    See https://www.unicode.org/cldr/charts/latest/supplemental/territory_language_information.html

    :param territory: Territory code
    :type territory: str
    :return: Language information dictionary
    :rtype: dict[str, dict]
    """
    territory_data = get_global("territory_languages").get(territory, {})
    result = {}

    for lang, data in territory_data.items():
        lang_info = {
            "population_percent": data.get("population_percent"),
            "official_status": data.get("official_status"),
        }
        result[lang] = lang_info

    return result
