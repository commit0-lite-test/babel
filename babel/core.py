"""
    babel.core
    ~~~~~~~~~~

    Core locale representation and locale data access.

    :copyright: (c) 2013-2023 by the Babel Team.
    :license: BSD, see LICENSE for more details.
"""
from __future__ import annotations
import os
import pickle
from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Any
from babel import localedata
from babel.plural import PluralRule
__all__ = ['UnknownLocaleError', 'Locale', 'default_locale', 'negotiate_locale', 'parse_locale']
if TYPE_CHECKING:
    from typing_extensions import Literal, TypeAlias
    _GLOBAL_KEY: TypeAlias = Literal['all_currencies', 'currency_fractions', 'language_aliases', 'likely_subtags', 'meta_zones', 'parent_exceptions', 'script_aliases', 'territory_aliases', 'territory_currencies', 'territory_languages', 'territory_zones', 'variant_aliases', 'windows_zone_mapping', 'zone_aliases', 'zone_territories']
    _global_data: Mapping[_GLOBAL_KEY, Mapping[str, Any]] | None
_global_data = None
_default_plural_rule = PluralRule({})

def get_global(key: _GLOBAL_KEY) -> Mapping[str, Any]:
    """Return the dictionary for the given key in the global data.

    The global data is stored in the ``babel/global.dat`` file and contains
    information independent of individual locales.

    >>> get_global('zone_aliases')['UTC']
    u'Etc/UTC'
    >>> get_global('zone_territories')['Europe/Berlin']
    u'DE'

    The keys available are:

    - ``all_currencies``
    - ``currency_fractions``
    - ``language_aliases``
    - ``likely_subtags``
    - ``parent_exceptions``
    - ``script_aliases``
    - ``territory_aliases``
    - ``territory_currencies``
    - ``territory_languages``
    - ``territory_zones``
    - ``variant_aliases``
    - ``windows_zone_mapping``
    - ``zone_aliases``
    - ``zone_territories``

    .. note:: The internal structure of the data may change between versions.

    .. versionadded:: 0.9

    :param key: the data key
    """
    global _global_data
    if _global_data is None:
        dirname = os.path.join(os.path.dirname(__file__), 'global.dat')
        with open(dirname, 'rb') as f:
            _global_data = pickle.load(f)
    return _global_data[key]
LOCALE_ALIASES = {'ar': 'ar_SY', 'bg': 'bg_BG', 'bs': 'bs_BA', 'ca': 'ca_ES', 'cs': 'cs_CZ', 'da': 'da_DK', 'de': 'de_DE', 'el': 'el_GR', 'en': 'en_US', 'es': 'es_ES', 'et': 'et_EE', 'fa': 'fa_IR', 'fi': 'fi_FI', 'fr': 'fr_FR', 'gl': 'gl_ES', 'he': 'he_IL', 'hu': 'hu_HU', 'id': 'id_ID', 'is': 'is_IS', 'it': 'it_IT', 'ja': 'ja_JP', 'km': 'km_KH', 'ko': 'ko_KR', 'lt': 'lt_LT', 'lv': 'lv_LV', 'mk': 'mk_MK', 'nl': 'nl_NL', 'nn': 'nn_NO', 'no': 'nb_NO', 'pl': 'pl_PL', 'pt': 'pt_PT', 'ro': 'ro_RO', 'ru': 'ru_RU', 'sk': 'sk_SK', 'sl': 'sl_SI', 'sv': 'sv_SE', 'th': 'th_TH', 'tr': 'tr_TR', 'uk': 'uk_UA'}

class UnknownLocaleError(Exception):
    """Exception thrown when a locale is requested for which no locale data
    is available.
    """

    def __init__(self, identifier: str) -> None:
        """Create the exception.

        :param identifier: the identifier string of the unsupported locale
        """
        Exception.__init__(self, f'unknown locale {identifier!r}')
        self.identifier = identifier

class Locale:
    """Representation of a specific locale.

    >>> locale = Locale('en', 'US')
    >>> repr(locale)
    "Locale('en', territory='US')"
    >>> locale.display_name
    u'English (United States)'

    A `Locale` object can also be instantiated from a raw locale string:

    >>> locale = Locale.parse('en-US', sep='-')
    >>> repr(locale)
    "Locale('en', territory='US')"

    `Locale` objects provide access to a collection of locale data, such as
    territory and language names, number and date format patterns, and more:

    >>> locale.number_symbols['latn']['decimal']
    u'.'

    If a locale is requested for which no locale data is available, an
    `UnknownLocaleError` is raised:

    >>> Locale.parse('en_XX')
    Traceback (most recent call last):
        ...
    UnknownLocaleError: unknown locale 'en_XX'

    For more information see :rfc:`3066`.
    """

    def __init__(self, language: str, territory: str | None=None, script: str | None=None, variant: str | None=None, modifier: str | None=None) -> None:
        """Initialize the locale object from the given identifier components.

        >>> locale = Locale('en', 'US')
        >>> locale.language
        'en'
        >>> locale.territory
        'US'

        :param language: the language code
        :param territory: the territory (country or region) code
        :param script: the script code
        :param variant: the variant code
        :param modifier: a modifier (following the '@' symbol, sometimes called '@variant')
        :raise `UnknownLocaleError`: if no locale data is available for the
                                     requested locale
        """
        self.language = language
        self.territory = territory
        self.script = script
        self.variant = variant
        self.modifier = modifier
        self.__data: localedata.LocaleDataDict | None = None
        identifier = str(self)
        identifier_without_modifier = identifier.partition('@')[0]
        if not localedata.exists(identifier_without_modifier):
            raise UnknownLocaleError(identifier)

    @classmethod
    def default(cls, category: str | None=None, aliases: Mapping[str, str]=LOCALE_ALIASES) -> Locale:
        """Return the system default locale for the specified category.

        >>> for name in ['LANGUAGE', 'LC_ALL', 'LC_CTYPE', 'LC_MESSAGES']:
        ...     os.environ[name] = ''
        >>> os.environ['LANG'] = 'fr_FR.UTF-8'
        >>> Locale.default('LC_MESSAGES')
        Locale('fr', territory='FR')

        The following fallbacks to the variable are always considered:

        - ``LANGUAGE``
        - ``LC_ALL``
        - ``LC_CTYPE``
        - ``LANG``

        :param category: one of the ``LC_XXX`` environment variable names
        :param aliases: a dictionary of aliases for locale identifiers
        """
        locale_string = default_locale(category, aliases)
        if locale_string:
            return cls.parse(locale_string)
        return cls('en', 'US')

    @classmethod
    def negotiate(cls, preferred: Iterable[str], available: Iterable[str], sep: str='_', aliases: Mapping[str, str]=LOCALE_ALIASES) -> Locale | None:
        """Find the best match between available and requested locale strings.

        >>> Locale.negotiate(['de_DE', 'en_US'], ['de_DE', 'de_AT'])
        Locale('de', territory='DE')
        >>> Locale.negotiate(['de_DE', 'en_US'], ['en', 'de'])
        Locale('de')
        >>> Locale.negotiate(['de_DE', 'de'], ['en_US'])

        You can specify the character used in the locale identifiers to separate
        the different components. This separator is applied to both lists. Also,
        case is ignored in the comparison:

        >>> Locale.negotiate(['de-DE', 'de'], ['en-us', 'de-de'], sep='-')
        Locale('de', territory='DE')

        :param preferred: the list of locale identifiers preferred by the user
        :param available: the list of locale identifiers available
        :param aliases: a dictionary of aliases for locale identifiers
        """
        locale_identifier = negotiate_locale(preferred, available, sep, aliases)
        if locale_identifier:
            return cls.parse(locale_identifier, sep)
        return None

    @classmethod
    def parse(cls, identifier: str | Locale | None, sep: str='_', resolve_likely_subtags: bool=True) -> Locale:
        """Create a `Locale` instance for the given locale identifier.

        >>> l = Locale.parse('de-DE', sep='-')
        >>> l.display_name
        u'Deutsch (Deutschland)'

        If the `identifier` parameter is not a string, but actually a `Locale`
        object, that object is returned:

        >>> Locale.parse(l)
        Locale('de', territory='DE')

        If the `identifier` parameter is neither of these, such as `None`
        e.g. because a default locale identifier could not be determined,
        a `TypeError` is raised:

        >>> Locale.parse(None)
        Traceback (most recent call last):
            ...
        TypeError: ...

        This also can perform resolving of likely subtags which it does
        by default.  This is for instance useful to figure out the most
        likely locale for a territory you can use ``'und'`` as the
        language tag:

        >>> Locale.parse('und_AT')
        Locale('de', territory='AT')

        Modifiers are optional, and always at the end, separated by "@":

        >>> Locale.parse('de_AT@euro')
        Locale('de', territory='AT', modifier='euro')

        :param identifier: the locale identifier string
        :param sep: optional component separator
        :param resolve_likely_subtags: if this is specified then a locale will
                                       have its likely subtag resolved if the
                                       locale otherwise does not exist.  For
                                       instance ``zh_TW`` by itself is not a
                                       locale that exists but Babel can
                                       automatically expand it to the full
                                       form of ``zh_hant_TW``.  Note that this
                                       expansion is only taking place if no
                                       locale exists otherwise.  For instance
                                       there is a locale ``en`` that can exist
                                       by itself.
        :raise `ValueError`: if the string does not appear to be a valid locale
                             identifier
        :raise `UnknownLocaleError`: if no locale data is available for the
                                     requested locale
        :raise `TypeError`: if the identifier is not a string or a `Locale`
        """
        if isinstance(identifier, Locale):
            return identifier
        if not isinstance(identifier, str):
            raise TypeError('Locale identifier must be a string or Locale object')
        
        parts = parse_locale(identifier, sep)
        lang, territory, script, variant, modifier = parts
        
        if resolve_likely_subtags:
            likely_subtags = get_global('likely_subtags')
            if (lang, territory, script) in likely_subtags:
                lang, territory, script = likely_subtags[(lang, territory, script)]
        
        return cls(lang, territory, script, variant, modifier)

    def __eq__(self, other: object) -> bool:
        for key in ('language', 'territory', 'script', 'variant', 'modifier'):
            if not hasattr(other, key):
                return False
        return self.language == getattr(other, 'language') and self.territory == getattr(other, 'territory') and (self.script == getattr(other, 'script')) and (self.variant == getattr(other, 'variant')) and (self.modifier == getattr(other, 'modifier'))

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __hash__(self) -> int:
        return hash((self.language, self.territory, self.script, self.variant, self.modifier))

    def __repr__(self) -> str:
        parameters = ['']
        for key in ('territory', 'script', 'variant', 'modifier'):
            value = getattr(self, key)
            if value is not None:
                parameters.append(f'{key}={value!r}')
        return f'Locale({self.language!r}{', '.join(parameters)})'

    def __str__(self) -> str:
        return get_locale_identifier((self.language, self.territory, self.script, self.variant, self.modifier))

    def get_display_name(self, locale: Locale | str | None=None) -> str | None:
        """Return the display name of the locale using the given locale.

        The display name will include the language, territory, script, and
        variant, if those are specified.

        >>> Locale('zh', 'CN', script='Hans').get_display_name('en')
        u'Chinese (Simplified, China)'

        Modifiers are currently passed through verbatim:

        >>> Locale('it', 'IT', modifier='euro').get_display_name('en')
        u'Italian (Italy, euro)'

        :param locale: the locale to use
        """
        if locale is None:
            locale = self
        elif isinstance(locale, str):
            locale = Locale.parse(locale)

        locale_data = localedata.LocaleDataDict(self.languages)
        
        parts = []
        if self.language:
            parts.append(locale_data.get(self.language, self.language))
        if self.script:
            parts.append(f"({self.get_script_name(locale)})")
        if self.territory:
            parts.append(f"({self.get_territory_name(locale)})")
        if self.variant:
            parts.append(f"({self.variant})")
        if self.modifier:
            parts.append(f"({self.modifier})")

        return ' '.join(parts)
    display_name = property(get_display_name, doc="        The localized display name of the locale.\n\n        >>> Locale('en').display_name\n        u'English'\n        >>> Locale('en', 'US').display_name\n        u'English (United States)'\n        >>> Locale('sv').display_name\n        u'svenska'\n\n        :type: `unicode`\n        ")

    def get_language_name(self, locale: Locale | str | None=None) -> str | None:
        """Return the language of this locale in the given locale.

        >>> Locale('zh', 'CN', script='Hans').get_language_name('de')
        u'Chinesisch'

        .. versionadded:: 1.0

        :param locale: the locale to use
        """
        if locale is None:
            locale = self
        elif isinstance(locale, str):
            locale = Locale.parse(locale)

        locale_data = localedata.LocaleDataDict(locale.languages)
        return locale_data.get(self.language)
    language_name = property(get_language_name, doc="        The localized language name of the locale.\n\n        >>> Locale('en', 'US').language_name\n        u'English'\n    ")

    def get_territory_name(self, locale: Locale | str | None=None) -> str | None:
        """Return the territory name in the given locale."""
        if locale is None:
            locale = self
        elif isinstance(locale, str):
            locale = Locale.parse(locale)

        if self.territory is None:
            return None

        locale_data = localedata.LocaleDataDict(locale.territories)
        return locale_data.get(self.territory)
    territory_name = property(get_territory_name, doc="        The localized territory name of the locale if available.\n\n        >>> Locale('de', 'DE').territory_name\n        u'Deutschland'\n    ")

    def get_script_name(self, locale: Locale | str | None=None) -> str | None:
        """Return the script name in the given locale."""
        if locale is None:
            locale = self
        elif isinstance(locale, str):
            locale = Locale.parse(locale)

        if self.script is None:
            return None

        locale_data = localedata.LocaleDataDict(locale.scripts)
        return locale_data.get(self.script)
    script_name = property(get_script_name, doc="        The localized script name of the locale if available.\n\n        >>> Locale('sr', 'ME', script='Latn').script_name\n        u'latinica'\n    ")

    @property
    def english_name(self) -> str | None:
        """The english display name of the locale.

        >>> Locale('de').english_name
        u'German'
        >>> Locale('de', 'DE').english_name
        u'German (Germany)'

        :type: `unicode`"""
        return self.get_display_name(Locale('en'))

    @property
    def languages(self) -> localedata.LocaleDataDict:
        """Mapping of language codes to translated language names.

        >>> Locale('de', 'DE').languages['ja']
        u'Japanisch'

        See `ISO 639 <http://www.loc.gov/standards/iso639-2/>`_ for
        more information.
        """
        return localedata.LocaleDataDict(self.__data['languages'])

    @property
    def scripts(self) -> localedata.LocaleDataDict:
        """Mapping of script codes to translated script names.

        >>> Locale('en', 'US').scripts['Hira']
        u'Hiragana'

        See `ISO 15924 <http://www.evertype.com/standards/iso15924/>`_
        for more information.
        """
        return localedata.LocaleDataDict(self.__data['scripts'])

    @property
    def territories(self) -> localedata.LocaleDataDict:
        """Mapping of script codes to translated script names.

        >>> Locale('es', 'CO').territories['DE']
        u'Alemania'

        See `ISO 3166 <http://www.iso.org/iso/en/prods-services/iso3166ma/>`_
        for more information.
        """
        return localedata.LocaleDataDict(self.__data['territories'])

    @property
    def variants(self) -> localedata.LocaleDataDict:
        """Mapping of script codes to translated script names.

        >>> Locale('de', 'DE').variants['1901']
        u'Alte deutsche Rechtschreibung'
        """
        return localedata.LocaleDataDict(self.__data['variants'])

    @property
    def currencies(self) -> localedata.LocaleDataDict:
        """Mapping of currency codes to translated currency names.  This
        only returns the generic form of the currency name, not the count
        specific one.  If an actual number is requested use the
        :func:`babel.numbers.get_currency_name` function.

        >>> Locale('en').currencies['COP']
        u'Colombian Peso'
        >>> Locale('de', 'DE').currencies['COP']
        u'Kolumbianischer Peso'
        """
        return localedata.LocaleDataDict(self.__data['currencies'])

    @property
    def currency_symbols(self) -> localedata.LocaleDataDict:
        """Mapping of currency codes to symbols.

        >>> Locale('en', 'US').currency_symbols['USD']
        u'$'
        >>> Locale('es', 'CO').currency_symbols['USD']
        u'US$'
        """
        return localedata.LocaleDataDict(self.__data['currency_symbols'])

    @property
    def number_symbols(self) -> localedata.LocaleDataDict:
        """Symbols used in number formatting by number system.

        .. note:: The format of the value returned may change between
                  Babel versions.

        >>> Locale('fr', 'FR').number_symbols["latn"]['decimal']
        u','
        >>> Locale('fa', 'IR').number_symbols["arabext"]['decimal']
        u'٫'
        >>> Locale('fa', 'IR').number_symbols["latn"]['decimal']
        u'.'
        """
        return localedata.LocaleDataDict(self.__data['number_symbols'])

    @property
    def other_numbering_systems(self) -> localedata.LocaleDataDict:
        """
        Mapping of other numbering systems available for the locale.
        See: https://www.unicode.org/reports/tr35/tr35-numbers.html#otherNumberingSystems

        >>> Locale('el', 'GR').other_numbering_systems['traditional']
        u'grek'

        .. note:: The format of the value returned may change between
                  Babel versions.
        """
        return localedata.LocaleDataDict(self.__data['other_numbering_systems'])

    @property
    def default_numbering_system(self) -> str:
        """The default numbering system used by the locale.
        >>> Locale('el', 'GR').default_numbering_system
        u'latn'
        """
        return self.__data['default_numbering_system']

    @property
    def decimal_formats(self) -> localedata.LocaleDataDict:
        """Locale patterns for decimal number formatting.

        .. note:: The format of the value returned may change between
                  Babel versions.

        >>> Locale('en', 'US').decimal_formats[None]
        <NumberPattern u'#,##0.###'>
        """
        return localedata.LocaleDataDict(self.__data['decimal_formats'])

    @property
    def compact_decimal_formats(self) -> localedata.LocaleDataDict:
        """Locale patterns for compact decimal number formatting.

        .. note:: The format of the value returned may change between
                  Babel versions.

        >>> Locale('en', 'US').compact_decimal_formats["short"]["one"]["1000"]
        <NumberPattern u'0K'>
        """
        return localedata.LocaleDataDict(self.__data['compact_decimal_formats'])

    @property
    def currency_formats(self) -> localedata.LocaleDataDict:
        """Locale patterns for currency number formatting.

        .. note:: The format of the value returned may change between
                  Babel versions.

        >>> Locale('en', 'US').currency_formats['standard']
        <NumberPattern u'\\xa4#,##0.00'>
        >>> Locale('en', 'US').currency_formats['accounting']
        <NumberPattern u'\\xa4#,##0.00;(\\xa4#,##0.00)'>
        """
        return localedata.LocaleDataDict(self.__data['currency_formats'])

    @property
    def compact_currency_formats(self) -> localedata.LocaleDataDict:
        """Locale patterns for compact currency number formatting.

        .. note:: The format of the value returned may change between
                  Babel versions.

        >>> Locale('en', 'US').compact_currency_formats["short"]["one"]["1000"]
        <NumberPattern u'¤0K'>
        """
        return localedata.LocaleDataDict(self.__data['compact_currency_formats'])

    @property
    def percent_formats(self) -> localedata.LocaleDataDict:
        """Locale patterns for percent number formatting.

        .. note:: The format of the value returned may change between
                  Babel versions.

        >>> Locale('en', 'US').percent_formats[None]
        <NumberPattern u'#,##0%'>
        """
        return localedata.LocaleDataDict(self.__data['percent_formats'])

    @property
    def scientific_formats(self) -> localedata.LocaleDataDict:
        """Locale patterns for scientific number formatting.

        .. note:: The format of the value returned may change between
                  Babel versions.

        >>> Locale('en', 'US').scientific_formats[None]
        <NumberPattern u'#E0'>
        """
        return localedata.LocaleDataDict(self.__data['scientific_formats'])

    @property
    def periods(self) -> localedata.LocaleDataDict:
        """Locale display names for day periods (AM/PM).

        >>> Locale('en', 'US').periods['am']
        u'AM'
        """
        return localedata.LocaleDataDict(self.__data['periods'])

    @property
    def day_periods(self) -> localedata.LocaleDataDict:
        """Locale display names for various day periods (not necessarily only AM/PM).

        These are not meant to be used without the relevant `day_period_rules`.
        """
        return localedata.LocaleDataDict(self.__data['day_periods'])

    @property
    def day_period_rules(self) -> localedata.LocaleDataDict:
        """Day period rules for the locale.  Used by `get_period_id`.
        """
        return localedata.LocaleDataDict(self.__data['day_period_rules'])

    @property
    def days(self) -> localedata.LocaleDataDict:
        """Locale display names for weekdays.

        >>> Locale('de', 'DE').days['format']['wide'][3]
        u'Donnerstag'
        """
        return localedata.LocaleDataDict(self.__data['days'])

    @property
    def months(self) -> localedata.LocaleDataDict:
        """Locale display names for months.

        >>> Locale('de', 'DE').months['format']['wide'][10]
        u'Oktober'
        """
        return localedata.LocaleDataDict(self.__data['months'])

    @property
    def quarters(self) -> localedata.LocaleDataDict:
        """Locale display names for quarters.

        >>> Locale('de', 'DE').quarters['format']['wide'][1]
        u'1. Quartal'
        """
        return localedata.LocaleDataDict(self.__data['quarters'])

    @property
    def eras(self) -> localedata.LocaleDataDict:
        """Locale display names for eras.

        .. note:: The format of the value returned may change between
                  Babel versions.

        >>> Locale('en', 'US').eras['wide'][1]
        u'Anno Domini'
        >>> Locale('en', 'US').eras['abbreviated'][0]
        u'BC'
        """
        return localedata.LocaleDataDict(self.__data['eras'])

    @property
    def time_zones(self) -> localedata.LocaleDataDict:
        """Locale display names for time zones.

        .. note:: The format of the value returned may change between
                  Babel versions.

        >>> Locale('en', 'US').time_zones['Europe/London']['long']['daylight']
        u'British Summer Time'
        >>> Locale('en', 'US').time_zones['America/St_Johns']['city']
        u'St. John’s'
        """
        pass

    @property
    def meta_zones(self) -> localedata.LocaleDataDict:
        """Locale display names for meta time zones.

        Meta time zones are basically groups of different Olson time zones that
        have the same GMT offset and daylight savings time.

        .. note:: The format of the value returned may change between
                  Babel versions.

        >>> Locale('en', 'US').meta_zones['Europe_Central']['long']['daylight']
        u'Central European Summer Time'

        .. versionadded:: 0.9
        """
        return localedata.LocaleDataDict(self.__data['meta_zones'])

    @property
    def zone_formats(self) -> localedata.LocaleDataDict:
        """Patterns related to the formatting of time zones.

        .. note:: The format of the value returned may change between
                  Babel versions.

        >>> Locale('en', 'US').zone_formats['fallback']
        u'%(1)s (%(0)s)'
        >>> Locale('pt', 'BR').zone_formats['region']
        u'Hor\\xe1rio %s'

        .. versionadded:: 0.9
        """
        return localedata.LocaleDataDict(self.__data['zone_formats'])

    @property
    def first_week_day(self) -> int:
        """The first day of a week, with 0 being Monday.

        >>> Locale('de', 'DE').first_week_day
        0
        >>> Locale('en', 'US').first_week_day
        6
        """
        return self.__data['week_data']['first_day']

    @property
    def weekend_start(self) -> int:
        """The day the weekend starts, with 0 being Monday.

        >>> Locale('de', 'DE').weekend_start
        5
        """
        return self.__data['week_data']['weekend_start']

    @property
    def weekend_end(self) -> int:
        """The day the weekend ends, with 0 being Monday.

        >>> Locale('de', 'DE').weekend_end
        6
        """
        return self.__data['week_data']['weekend_end']

    @property
    def min_week_days(self) -> int:
        """The minimum number of days in a week so that the week is counted as
        the first week of a year or month.

        >>> Locale('de', 'DE').min_week_days
        4
        """
        return self.__data['week_data']['min_days']

    @property
    def date_formats(self) -> localedata.LocaleDataDict:
        """Locale patterns for date formatting.

        .. note:: The format of the value returned may change between
                  Babel versions.

        >>> Locale('en', 'US').date_formats['short']
        <DateTimePattern u'M/d/yy'>
        >>> Locale('fr', 'FR').date_formats['long']
        <DateTimePattern u'd MMMM y'>
        """
        return localedata.LocaleDataDict(self.__data['date_formats'])

    @property
    def time_formats(self) -> localedata.LocaleDataDict:
        """Locale patterns for time formatting.

        .. note:: The format of the value returned may change between
                  Babel versions.

        >>> Locale('en', 'US').time_formats['short']
        <DateTimePattern u'h:mm\u202fa'>
        >>> Locale('fr', 'FR').time_formats['long']
        <DateTimePattern u'HH:mm:ss z'>
        """
        return localedata.LocaleDataDict(self.__data['time_formats'])

    @property
    def datetime_formats(self) -> localedata.LocaleDataDict:
        """Locale patterns for datetime formatting.

        .. note:: The format of the value returned may change between
                  Babel versions.

        >>> Locale('en').datetime_formats['full']
        u'{1}, {0}'
        >>> Locale('th').datetime_formats['medium']
        u'{1} {0}'
        """
        return localedata.LocaleDataDict(self.__data['datetime_formats'])

    @property
    def datetime_skeletons(self) -> localedata.LocaleDataDict:
        """Locale patterns for formatting parts of a datetime.

        >>> Locale('en').datetime_skeletons['MEd']
        <DateTimePattern u'E, M/d'>
        >>> Locale('fr').datetime_skeletons['MEd']
        <DateTimePattern u'E dd/MM'>
        >>> Locale('fr').datetime_skeletons['H']
        <DateTimePattern u"HH 'h'">
        """
        return localedata.LocaleDataDict(self.__data['datetime_skeletons'])

    @property
    def interval_formats(self) -> localedata.LocaleDataDict:
        """Locale patterns for interval formatting.

        .. note:: The format of the value returned may change between
                  Babel versions.

        How to format date intervals in Finnish when the day is the
        smallest changing component:

        >>> Locale('fi_FI').interval_formats['MEd']['d']
        [u'E d.\u2009–\u2009', u'E d.M.']

        .. seealso::

           The primary API to use this data is :py:func:`babel.dates.format_interval`.


        :rtype: dict[str, dict[str, list[str]]]
        """
        return localedata.LocaleDataDict(self.__data['interval_formats'])

    @property
    def plural_form(self) -> PluralRule:
        """Plural rules for the locale.

        >>> Locale('en').plural_form(1)
        'one'
        >>> Locale('en').plural_form(0)
        'other'
        >>> Locale('fr').plural_form(0)
        'one'
        >>> Locale('ru').plural_form(100)
        'many'
        """
        return self.__data['plural_form']

    @property
    def list_patterns(self) -> localedata.LocaleDataDict:
        """Patterns for generating lists

        .. note:: The format of the value returned may change between
                  Babel versions.

        >>> Locale('en').list_patterns['standard']['start']
        u'{0}, {1}'
        >>> Locale('en').list_patterns['standard']['end']
        u'{0}, and {1}'
        >>> Locale('en_GB').list_patterns['standard']['end']
        u'{0} and {1}'
        """
        return localedata.LocaleDataDict(self.__data['list_patterns'])

    @property
    def ordinal_form(self) -> PluralRule:
        """Plural rules for the locale.

        >>> Locale('en').ordinal_form(1)
        'one'
        >>> Locale('en').ordinal_form(2)
        'two'
        >>> Locale('en').ordinal_form(3)
        'few'
        >>> Locale('fr').ordinal_form(2)
        'other'
        >>> Locale('ru').ordinal_form(100)
        'other'
        """
        return self.__data['ordinal_form']

    @property
    def measurement_systems(self) -> localedata.LocaleDataDict:
        """Localized names for various measurement systems.

        >>> Locale('fr', 'FR').measurement_systems['US']
        u'am\\xe9ricain'
        >>> Locale('en', 'US').measurement_systems['US']
        u'US'

        """
        return localedata.LocaleDataDict(self.__data['measurement_systems'])

    @property
    def character_order(self) -> str:
        """The text direction for the language.

        >>> Locale('de', 'DE').character_order
        'left-to-right'
        >>> Locale('ar', 'SA').character_order
        'right-to-left'
        """
        return self.__data['character_order']

    @property
    def text_direction(self) -> str:
        """The text direction for the language in CSS short-hand form.

        >>> Locale('de', 'DE').text_direction
        'ltr'
        >>> Locale('ar', 'SA').text_direction
        'rtl'
        """
        return 'rtl' if self.character_order == 'right-to-left' else 'ltr'

    @property
    def unit_display_names(self) -> localedata.LocaleDataDict:
        """Display names for units of measurement.

        .. seealso::

           You may want to use :py:func:`babel.units.get_unit_name` instead.

        .. note:: The format of the value returned may change between
                  Babel versions.

        """
        return localedata.LocaleDataDict(self.__data['unit_display_names'])

def default_locale(category: str | None=None, aliases: Mapping[str, str]=LOCALE_ALIASES) -> str | None:
    """Returns the system default locale for a given category, based on
    environment variables.

    >>> for name in ['LANGUAGE', 'LC_ALL', 'LC_CTYPE']:
    ...     os.environ[name] = ''
    >>> os.environ['LANG'] = 'fr_FR.UTF-8'
    >>> default_locale('LC_MESSAGES')
    'fr_FR'

    The "C" or "POSIX" pseudo-locales are treated as aliases for the
    "en_US_POSIX" locale:

    >>> os.environ['LC_MESSAGES'] = 'POSIX'
    >>> default_locale('LC_MESSAGES')
    'en_US_POSIX'

    The following fallbacks to the variable are always considered:

    - ``LANGUAGE``
    - ``LC_ALL``
    - ``LC_CTYPE``
    - ``LANG``

    :param category: one of the ``LC_XXX`` environment variable names
    :param aliases: a dictionary of aliases for locale identifiers
    """
    varnames = (category, 'LANGUAGE', 'LC_ALL', 'LC_CTYPE', 'LANG')
    for name in varnames:
        if name:
            locale = os.environ.get(name)
            if locale:
                if name == 'LANGUAGE' and ':' in locale:
                    # Language priority list
                    locale = locale.split(':')[0]
                if locale.lower() in ('c', 'posix'):
                    return 'en_US_POSIX'
                return aliases.get(locale, locale).replace('-', '_')
    return None

def negotiate_locale(preferred: Iterable[str], available: Iterable[str], sep: str='_', aliases: Mapping[str, str]=LOCALE_ALIASES) -> str | None:
    """Find the best match between available and requested locale strings.

    >>> negotiate_locale(['de_DE', 'en_US'], ['de_DE', 'de_AT'])
    'de_DE'
    >>> negotiate_locale(['de_DE', 'en_US'], ['en', 'de'])
    'de'

    Case is ignored by the algorithm, the result uses the case of the preferred
    locale identifier:

    >>> negotiate_locale(['de_DE', 'en_US'], ['de_de', 'de_at'])
    'de_DE'

    >>> negotiate_locale(['de_DE', 'en_US'], ['de_de', 'de_at'])
    'de_DE'

    By default, some web browsers unfortunately do not include the territory
    in the locale identifier for many locales, and some don't even allow the
    user to easily add the territory. So while you may prefer using qualified
    locale identifiers in your web-application, they would not normally match
    the language-only locale sent by such browsers. To workaround that, this
    function uses a default mapping of commonly used language-only locale
    identifiers to identifiers including the territory:

    >>> negotiate_locale(['ja', 'en_US'], ['ja_JP', 'en_US'])
    'ja_JP'

    Some browsers even use an incorrect or outdated language code, such as "no"
    for Norwegian, where the correct locale identifier would actually be "nb_NO"
    (Bokmål) or "nn_NO" (Nynorsk). The aliases are intended to take care of
    such cases, too:

    >>> negotiate_locale(['no', 'sv'], ['nb_NO', 'sv_SE'])
    'nb_NO'

    You can override this default mapping by passing a different `aliases`
    dictionary to this function, or you can bypass the behavior althogher by
    setting the `aliases` parameter to `None`.

    :param preferred: the list of locale strings preferred by the user
    :param available: the list of locale strings available
    :param sep: character that separates the different parts of the locale
                strings
    :param aliases: a dictionary of aliases for locale identifiers
    """
    available = [a.lower() for a in available]
    for locale in preferred:
        locale = locale.replace('-', '_')
        if aliases:
            locale = aliases.get(locale, locale)
        parts = locale.split(sep)
        if len(parts) > 1:
            for i in range(len(parts), 0, -1):
                candidate = sep.join(parts[:i]).lower()
                if candidate in available:
                    return candidate
        else:
            candidate = parts[0].lower()
            if candidate in available:
                return candidate
    return None

def parse_locale(identifier: str, sep: str='_') -> tuple[str, str | None, str | None, str | None] | tuple[str, str | None, str | None, str | None, str | None]:
    """Parse a locale identifier into a tuple of the form ``(language,
    territory, script, variant, modifier)``.

    >>> parse_locale('zh_CN')
    ('zh', 'CN', None, None)
    >>> parse_locale('zh_Hans_CN')
    ('zh', 'CN', 'Hans', None)
    >>> parse_locale('ca_es_valencia')
    ('ca', 'ES', None, 'VALENCIA')
    >>> parse_locale('en_150')
    ('en', '150', None, None)
    >>> parse_locale('en_us_posix')
    ('en', 'US', None, 'POSIX')
    >>> parse_locale('it_IT@euro')
    ('it', 'IT', None, None, 'euro')
    >>> parse_locale('it_IT@custom')
    ('it', 'IT', None, None, 'custom')
    >>> parse_locale('it_IT@')
    ('it', 'IT', None, None)

    The default component separator is "_", but a different separator can be
    specified using the `sep` parameter.

    The optional modifier is always separated with "@" and at the end:

    >>> parse_locale('zh-CN', sep='-')
    ('zh', 'CN', None, None)
    >>> parse_locale('zh-CN@custom', sep='-')
    ('zh', 'CN', None, None, 'custom')

    If the identifier cannot be parsed into a locale, a `ValueError` exception
    is raised:

    >>> parse_locale('not_a_LOCALE_String')
    Traceback (most recent call last):
      ...
    ValueError: 'not_a_LOCALE_String' is not a valid locale identifier

    Encoding information is removed from the identifier, while modifiers are
    kept:

    >>> parse_locale('en_US.UTF-8')
    ('en', 'US', None, None)
    >>> parse_locale('de_DE.iso885915@euro')
    ('de', 'DE', None, None, 'euro')

    See :rfc:`4646` for more information.

    :param identifier: the locale identifier string
    :param sep: character that separates the different components of the locale
                identifier
    :raise `ValueError`: if the string does not appear to be a valid locale
                         identifier
    """
    if identifier and sep in identifier:
        parts = identifier.split(sep)
    else:
        parts = [identifier]

    # Remove encoding if present
    if '.' in parts[-1]:
        parts[-1] = parts[-1].split('.')[0]

    # Extract modifier
    modifier = None
    if '@' in parts[-1]:
        parts[-1], modifier = parts[-1].split('@', 1)

    # Normalize case
    parts = [part.lower() for part in parts]
    if len(parts) == 1:
        return parts[0], None, None, None, modifier
    elif len(parts) == 2:
        return parts[0], parts[1].upper(), None, None, modifier
    elif len(parts) == 3:
        if len(parts[1]) == 4:  # Script
            return parts[0], parts[2].upper(), parts[1].title(), None, modifier
        else:  # Variant
            return parts[0], parts[1].upper(), None, parts[2].upper(), modifier
    elif len(parts) == 4:
        return parts[0], parts[2].upper(), parts[1].title(), parts[3].upper(), modifier
    else:
        raise ValueError(f"'{identifier}' is not a valid locale identifier")

def get_locale_identifier(tup: tuple[str] | tuple[str, str | None] | tuple[str, str | None, str | None] | tuple[str, str | None, str | None, str | None] | tuple[str, str | None, str | None, str | None, str | None], sep: str='_') -> str:
    """The reverse of :func:`parse_locale`.  It creates a locale identifier out
    of a ``(language, territory, script, variant, modifier)`` tuple.  Items can be set to
    ``None`` and trailing ``None``\\s can also be left out of the tuple.

    >>> get_locale_identifier(('de', 'DE', None, '1999', 'custom'))
    'de_DE_1999@custom'
    >>> get_locale_identifier(('fi', None, None, None, 'custom'))
    'fi@custom'


    .. versionadded:: 1.0

    :param tup: the tuple as returned by :func:`parse_locale`.
    :param sep: the separator for the identifier.
    """
    parts = []
    for part in tup:
        if part is not None:
            parts.append(part)
        else:
            break
    
    identifier = sep.join(parts[:-1]) if len(parts) > 1 else parts[0]
    
    if len(tup) == 5 and tup[4]:
        identifier += f'@{tup[4]}'
    
    return identifier
