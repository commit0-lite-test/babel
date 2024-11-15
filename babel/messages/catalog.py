"""
babel.messages.catalog
~~~~~~~~~~~~~~~~~~~~~~

Data structures for message catalogs.

:copyright: (c) 2013-2023 by the Babel Team.
:license: BSD, see LICENSE for more details.
"""

from __future__ import annotations

import datetime
import re
from collections import OrderedDict
from collections.abc import Iterable, Iterator
from difflib import SequenceMatcher
from email import message_from_string
from heapq import nlargest
from typing import TYPE_CHECKING

from babel.core import Locale
from babel.messages.plurals import get_plural
from babel.util import LOCALTZ, distinct

if TYPE_CHECKING:
    from typing_extensions import TypeAlias

    _MessageID: TypeAlias = str | tuple[str, ...] | list[str]

from babel.messages.catalog_utils import (
    _get_header_comment,
    _get_locale,
    _get_locale_identifier,
    _get_mime_headers,
    _set_header_comment,
    _set_locale,
    _set_mime_headers,
)

__all__ = ["Message", "Catalog", "TranslationError"]


def get_close_matches(word, possibilities, n=3, cutoff=0.6):
    """A modified version of ``difflib.get_close_matches``.

    It just passes ``autojunk=False`` to the ``SequenceMatcher``, to work
    around https://github.com/python/cpython/issues/90825.
    """
    if not n > 0:
        raise ValueError(f"n must be > 0: {n!r}")
    if not 0.0 <= cutoff <= 1.0:
        raise ValueError(f"cutoff must be in [0.0, 1.0]: {cutoff!r}")
    result = []
    s = SequenceMatcher(autojunk=False)
    s.set_seq2(word)
    for x in possibilities:
        s.set_seq1(x)
        if (
            s.real_quick_ratio() >= cutoff
            and s.quick_ratio() >= cutoff
            and s.ratio() >= cutoff
        ):
            result.append((s.ratio(), x))

    # Move the best scorers to head of list
    result = nlargest(n, result)
    # Strip scores for the best n matches
    return [x for score, x in result]


PYTHON_FORMAT = re.compile(
    "\n    \\%\n        (?:\\(([\\w]*)\\))?\n        (\n            [-#0\\ +]?(?:\\*|[\\d]+)?\n            (?:\\.(?:\\*|[\\d]+))?\n            [hlL]?\n        )\n        ([diouxXeEfFgGcrs%])\n",
    re.VERBOSE,
)


class Message:
    """Representation of a single message in a catalog."""

    def __init__(
        self,
        id: _MessageID,
        string: _MessageID | None = "",
        locations: Iterable[tuple[str, int]] = (),
        flags: Iterable[str] = (),
        auto_comments: Iterable[str] = (),
        user_comments: Iterable[str] = (),
        previous_id: _MessageID = (),
        lineno: int | None = None,
        context: str | None = None,
    ) -> None:
        """Create the message object.

        :param id: the message ID, or a ``(singular, plural)`` tuple for
                   pluralizable messages
        :param string: the translated message string, or a
                       ``(singular, plural)`` tuple for pluralizable messages
        :param locations: a sequence of ``(filename, lineno)`` tuples
        :param flags: a set or sequence of flags
        :param auto_comments: a sequence of automatic comments for the message
        :param user_comments: a sequence of user comments for the message
        :param previous_id: the previous message ID, or a ``(singular, plural)``
                            tuple for pluralizable messages
        :param lineno: the line number on which the msgid line was found in the
                       PO file, if any
        :param context: the message context
        """
        self.id = id
        if not string and self.pluralizable:
            string = ("", "")
        self.string = string
        self.locations = list(distinct(locations))
        self.flags = set(flags)
        if id and self.python_format:
            self.flags.add("python-format")
        else:
            self.flags.discard("python-format")
        self.auto_comments = list(distinct(auto_comments))
        self.user_comments = list(distinct(user_comments))
        if isinstance(previous_id, str):
            self.previous_id = [previous_id]
        else:
            self.previous_id = list(previous_id)
        self.lineno = lineno
        self.context = context

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.id!r} (flags: {list(self.flags)!r})>"

    def __cmp__(self, other: object) -> int:
        """Compare Messages, taking into account plural ids"""

        def values_to_compare(obj):
            if isinstance(obj, Message) and obj.pluralizable:
                return (obj.id[0], obj.context or "")
            return (obj.id, obj.context or "")

        return _cmp(values_to_compare(self), values_to_compare(other))

    def __gt__(self, other: object) -> bool:
        return self.__cmp__(other) > 0

    def __lt__(self, other: object) -> bool:
        return self.__cmp__(other) < 0

    def __ge__(self, other: object) -> bool:
        return self.__cmp__(other) >= 0

    def __le__(self, other: object) -> bool:
        return self.__cmp__(other) <= 0

    def __eq__(self, other: object) -> bool:
        return self.__cmp__(other) == 0

    def __ne__(self, other: object) -> bool:
        return self.__cmp__(other) != 0

    def is_identical(self, other: Message) -> bool:
        """Checks whether messages are identical, taking into account all
        properties.
        """
        return (
            self.id == other.id
            and self.string == other.string
            and self.locations == other.locations
            and self.flags == other.flags
            and self.auto_comments == other.auto_comments
            and self.user_comments == other.user_comments
            and self.previous_id == other.previous_id
            and self.lineno == other.lineno
            and self.context == other.context
        )

    def check(self, catalog: Catalog | None = None) -> list[TranslationError]:
        """Run various validation checks on the message.  Some validations
        are only performed if the catalog is provided.  This method returns
        a sequence of `TranslationError` objects.

        :rtype: ``iterator``
        :param catalog: A catalog instance that is passed to the checkers
        :see: `Catalog.check` for a way to perform checks for all messages
              in a catalog.
        """
        errors = []

        if self.pluralizable:
            if not isinstance(self.string, (list, tuple)):
                errors.append(
                    TranslationError(
                        "Pluralizable message has a non-pluralized translation"
                    )
                )
            elif len(self.string) != 2:
                errors.append(
                    TranslationError(
                        f"Pluralizable message has {len(self.string)} plural forms, expected 2"
                    )
                )

        if self.python_format:
            if isinstance(self.id, (list, tuple)):
                ids = self.id
            else:
                ids = [self.id]

            if isinstance(self.string, (list, tuple)):
                strings = self.string
            elif self.string:
                strings = [self.string]
            else:
                strings = []

            for id, string in zip(ids, strings):
                id_placeholders = set(PYTHON_FORMAT.findall(id))
                string_placeholders = set(PYTHON_FORMAT.findall(string))

                if id_placeholders != string_placeholders:
                    errors.append(
                        TranslationError(
                            "The translation contains placeholders that are not in the message string"
                        )
                    )

        if catalog and self.context and self.id in catalog._messages:
            errors.append(TranslationError("Duplicate message with context"))

        return errors

    @property
    def fuzzy(self) -> bool:
        """Whether the translation is fuzzy.

        >>> Message('foo').fuzzy
        False
        >>> msg = Message('foo', 'foo', flags=['fuzzy'])
        >>> msg.fuzzy
        True
        >>> msg
        <Message 'foo' (flags: ['fuzzy'])>

        :type:  `bool`"""
        return "fuzzy" in self.flags

    @property
    def pluralizable(self) -> bool:
        """Whether the message is plurizable.

        >>> Message('foo').pluralizable
        False
        >>> Message(('foo', 'bar')).pluralizable
        True

        :type:  `bool`"""
        return isinstance(self.id, (list, tuple))

    @property
    def python_format(self) -> bool:
        """Whether the message contains Python-style parameters.

        >>> Message('foo %(name)s bar').python_format
        True
        >>> Message(('foo %(name)s', 'foo %(name)s')).python_format
        True

        :type:  `bool`"""
        if isinstance(self.id, (list, tuple)):
            return any(PYTHON_FORMAT.search(id) for id in self.id)
        return bool(PYTHON_FORMAT.search(self.id))


class TranslationError(Exception):
    """Exception thrown by translation checkers when invalid message
    translations are encountered."""


DEFAULT_HEADER = "# Translations template for PROJECT.\n# Copyright (C) YEAR ORGANIZATION\n# This file is distributed under the same license as the PROJECT project.\n# FIRST AUTHOR <EMAIL@ADDRESS>, YEAR.\n#"


class Catalog:
    """Representation of a message catalog."""

    def __init__(
        self,
        locale: str | Locale | None = None,
        domain: str | None = None,
        header_comment: str | None = DEFAULT_HEADER,
        project: str | None = None,
        version: str | None = None,
        copyright_holder: str | None = None,
        msgid_bugs_address: str | None = None,
        creation_date: datetime.datetime | str | None = None,
        revision_date: datetime.datetime | datetime.time | float | str | None = None,
        last_translator: str | None = None,
        language_team: str | None = None,
        charset: str | None = None,
        fuzzy: bool = True,
    ) -> None:
        """Initialize the catalog object.

        :param locale: the locale identifier or `Locale` object, or `None`
                       if the catalog is not bound to a locale (which basically
                       means it's a template)
        :param domain: the message domain
        :param header_comment: the header comment as string, or `None` for the
                               default header
        :param project: the project's name
        :param version: the project's version
        :param copyright_holder: the copyright holder of the catalog
        :param msgid_bugs_address: the email address or URL to submit bug
                                   reports to
        :param creation_date: the date the catalog was created
        :param revision_date: the date the catalog was revised
        :param last_translator: the name and email of the last translator
        :param language_team: the name and email of the language team
        :param charset: the encoding to use in the output (defaults to utf-8)
        :param fuzzy: the fuzzy bit on the catalog header
        """
        self.domain = domain
        self.locale = locale
        self._header_comment = header_comment
        self._messages: OrderedDict[str | tuple[str, str], Message] = OrderedDict()
        self.project = project or "PROJECT"
        self.version = version or "VERSION"
        self.copyright_holder = copyright_holder or "ORGANIZATION"
        self.msgid_bugs_address = msgid_bugs_address or "EMAIL@ADDRESS"
        self.last_translator = last_translator or "FULL NAME <EMAIL@ADDRESS>"
        "Name and email address of the last translator."
        self.language_team = language_team or "LANGUAGE <LL@li.org>"
        "Name and email address of the language team."
        self.charset = charset or "utf-8"
        if creation_date is None:
            creation_date = datetime.datetime.now(LOCALTZ)
        elif isinstance(creation_date, datetime.datetime) and (
            not creation_date.tzinfo
        ):
            creation_date = creation_date.replace(tzinfo=LOCALTZ)
        self.creation_date = creation_date
        if revision_date is None:
            revision_date = "YEAR-MO-DA HO:MI+ZONE"
        elif isinstance(revision_date, datetime.datetime) and (
            not revision_date.tzinfo
        ):
            revision_date = revision_date.replace(tzinfo=LOCALTZ)
        self.revision_date = revision_date
        self.fuzzy = fuzzy
        self.obsolete: OrderedDict[str | tuple[str, str], Message] = OrderedDict()
        self._num_plurals = None
        self._plural_expr = None

    locale = property(_get_locale, _set_locale)
    locale_identifier = property(_get_locale_identifier)
    header_comment = property(
        _get_header_comment,
        _set_header_comment,
        doc="    The header comment for the catalog.\n\n    >>> catalog = Catalog(project='Foobar', version='1.0',\n    ...                   copyright_holder='Foo Company')\n    >>> print(catalog.header_comment) #doctest: +ELLIPSIS\n    # Translations template for Foobar.\n    # Copyright (C) ... Foo Company\n    # This file is distributed under the same license as the Foobar project.\n    # FIRST AUTHOR <EMAIL@ADDRESS>, ....\n    #\n\n    The header can also be set from a string. Any known upper-case variables\n    will be replaced when the header is retrieved again:\n\n    >>> catalog = Catalog(project='Foobar', version='1.0',\n    ...                   copyright_holder='Foo Company')\n    >>> catalog.header_comment = '''\\\n    ... # The POT for my really cool PROJECT project.\n    ... # Copyright (C) 1990-2003 ORGANIZATION\n    ... # This file is distributed under the same license as the PROJECT\n    ... # project.\n    ... #'''\n    >>> print(catalog.header_comment)\n    # The POT for my really cool Foobar project.\n    # Copyright (C) 1990-2003 Foo Company\n    # This file is distributed under the same license as the Foobar\n    # project.\n    #\n\n    :type: `unicode`\n    ",
    )
    mime_headers = property(
        _get_mime_headers,
        _set_mime_headers,
        doc="    The MIME headers of the catalog, used for the special ``msgid \"\"`` entry.\n\n    The behavior of this property changes slightly depending on whether a locale\n    is set or not, the latter indicating that the catalog is actually a template\n    for actual translations.\n\n    Here's an example of the output for such a catalog template:\n\n    >>> from babel.dates import UTC\n    >>> from datetime import datetime\n    >>> created = datetime(1990, 4, 1, 15, 30, tzinfo=UTC)\n    >>> catalog = Catalog(project='Foobar', version='1.0',\n    ...                   creation_date=created)\n    >>> for name, value in catalog.mime_headers:\n    ...     print('%s: %s' % (name, value))\n    Project-Id-Version: Foobar 1.0\n    Report-Msgid-Bugs-To: EMAIL@ADDRESS\n    POT-Creation-Date: 1990-04-01 15:30+0000\n    PO-Revision-Date: YEAR-MO-DA HO:MI+ZONE\n    Last-Translator: FULL NAME <EMAIL@ADDRESS>\n    Language-Team: LANGUAGE <LL@li.org>\n    MIME-Version: 1.0\n    Content-Type: text/plain; charset=utf-8\n    Content-Transfer-Encoding: 8bit\n    Generated-By: Babel ...\n\n    And here's an example of the output when the locale is set:\n\n    >>> revised = datetime(1990, 8, 3, 12, 0, tzinfo=UTC)\n    >>> catalog = Catalog(locale='de_DE', project='Foobar', version='1.0',\n    ...                   creation_date=created, revision_date=revised,\n    ...                   last_translator='John Doe <jd@example.com>',\n    ...                   language_team='de_DE <de@example.com>')\n    >>> for name, value in catalog.mime_headers:\n    ...     print('%s: %s' % (name, value))\n    Project-Id-Version: Foobar 1.0\n    Report-Msgid-Bugs-To: EMAIL@ADDRESS\n    POT-Creation-Date: 1990-04-01 15:30+0000\n    PO-Revision-Date: 1990-08-03 12:00+0000\n    Last-Translator: John Doe <jd@example.com>\n    Language: de_DE\n    Language-Team: de_DE <de@example.com>\n    Plural-Forms: nplurals=2; plural=(n != 1);\n    MIME-Version: 1.0\n    Content-Type: text/plain; charset=utf-8\n    Content-Transfer-Encoding: 8bit\n    Generated-By: Babel ...\n\n    :type: `list`\n    ",
    )

    @property
    def num_plurals(self) -> int:
        """The number of plurals used by the catalog or locale.

        >>> Catalog(locale='en').num_plurals
        2
        >>> Catalog(locale='ga').num_plurals
        5

        :type: `int`"""
        if self._num_plurals is None:
            if self.locale:
                self._num_plurals = get_plural(self.locale)[0]
            else:
                self._num_plurals = 2
        return self._num_plurals

    @property
    def plural_expr(self) -> str:
        """The plural expression used by the catalog or locale.

        >>> Catalog(locale='en').plural_expr
        '(n != 1)'
        >>> Catalog(locale='ga').plural_expr
        '(n==1 ? 0 : n==2 ? 1 : n>=3 && n<=6 ? 2 : n>=7 && n<=10 ? 3 : 4)'
        >>> Catalog(locale='ding').plural_expr  # unknown locale
        '(n != 1)'

        :type: `str`"""
        if self._plural_expr is None:
            if self.locale:
                self._plural_expr = get_plural(self.locale)[1]
            else:
                self._plural_expr = "(n != 1)"
        return self._plural_expr

    @property
    def plural_forms(self) -> str:
        """Return the plural forms declaration for the locale.

        >>> Catalog(locale='en').plural_forms
        'nplurals=2; plural=(n != 1);'
        >>> Catalog(locale='pt_BR').plural_forms
        'nplurals=2; plural=(n > 1);'

        :type: `str`"""
        return f"nplurals={self.num_plurals}; plural={self.plural_expr};"

    def __contains__(self, id: _MessageID) -> bool:
        """Return whether the catalog has a message with the specified ID."""
        return self._key_for(id) in self._messages

    def __len__(self) -> int:
        """The number of messages in the catalog.

        This does not include the special ``msgid ""`` entry."""
        return len(self._messages)

    def __iter__(self) -> Iterator[Message]:
        """Iterates through all the entries in the catalog, in the order they
        were added, yielding a `Message` object for every entry.

        :rtype: ``iterator``"""
        buf = []
        for name, value in self.mime_headers:
            buf.append(f"{name}: {value}")
        flags = set()
        if self.fuzzy:
            flags |= {"fuzzy"}
        yield Message("", "\n".join(buf), flags=flags)
        for key in self._messages:
            yield self._messages[key]

    def __repr__(self) -> str:
        locale = ""
        if self.locale:
            locale = f" {self.locale}"
        return f"<{type(self).__name__} {self.domain!r}{locale}>"

    def __delitem__(self, id: _MessageID) -> None:
        """Delete the message with the specified ID."""
        self.delete(id)

    def __getitem__(self, id: _MessageID) -> Message:
        """Return the message with the specified ID.

        :param id: the message ID
        """
        return self.get(id)

    def __setitem__(self, id: _MessageID, message: Message) -> None:
        """Add or update the message with the specified ID.

        >>> catalog = Catalog()
        >>> catalog[u'foo'] = Message(u'foo')
        >>> catalog[u'foo']
        <Message u'foo' (flags: [])>

        If a message with that ID is already in the catalog, it is updated
        to include the locations and flags of the new message.

        >>> catalog = Catalog()
        >>> catalog[u'foo'] = Message(u'foo', locations=[('main.py', 1)])
        >>> catalog[u'foo'].locations
        [('main.py', 1)]
        >>> catalog[u'foo'] = Message(u'foo', locations=[('utils.py', 5)])
        >>> catalog[u'foo'].locations
        [('main.py', 1), ('utils.py', 5)]

        :param id: the message ID
        :param message: the `Message` object
        """
        assert isinstance(message, Message), "expected a Message object"
        key = self._key_for(id, message.context)
        current = self._messages.get(key)
        if current:
            if message.pluralizable and (not current.pluralizable):
                current.id = message.id
                current.string = message.string
            current.locations = list(distinct(current.locations + message.locations))
            current.auto_comments = list(
                distinct(current.auto_comments + message.auto_comments)
            )
            current.user_comments = list(
                distinct(current.user_comments + message.user_comments)
            )
            current.flags |= message.flags
            message = current
        elif id == "":
            self.mime_headers = message_from_string(message.string).items()
            self.header_comment = "\n".join(
                [f"# {c}".rstrip() for c in message.user_comments]
            )
            self.fuzzy = message.fuzzy
        else:
            if isinstance(id, (list, tuple)):
                assert isinstance(
                    message.string, (list, tuple)
                ), f"Expected sequence but got {type(message.string)}"
            self._messages[key] = message

    def add(
        self,
        id: _MessageID,
        string: _MessageID | None = None,
        locations: Iterable[tuple[str, int]] = (),
        flags: Iterable[str] = (),
        auto_comments: Iterable[str] = (),
        user_comments: Iterable[str] = (),
        previous_id: _MessageID = (),
        lineno: int | None = None,
        context: str | None = None,
    ) -> Message:
        """Add or update the message with the specified ID.

        >>> catalog = Catalog()
        >>> catalog.add(u'foo')
        <Message ...>
        >>> catalog[u'foo']
        <Message u'foo' (flags: [])>

        This method simply constructs a `Message` object with the given
        arguments and invokes `__setitem__` with that object.

        :param id: the message ID, or a ``(singular, plural)`` tuple for
                   pluralizable messages
        :param string: the translated message string, or a
                       ``(singular, plural)`` tuple for pluralizable messages
        :param locations: a sequence of ``(filename, lineno)`` tuples
        :param flags: a set or sequence of flags
        :param auto_comments: a sequence of automatic comments
        :param user_comments: a sequence of user comments
        :param previous_id: the previous message ID, or a ``(singular, plural)``
                            tuple for pluralizable messages
        :param lineno: the line number on which the msgid line was found in the
                       PO file, if any
        :param context: the message context
        """
        message = Message(
            id,
            string,
            locations,
            flags,
            auto_comments,
            user_comments,
            previous_id,
            lineno,
            context,
        )
        self[id] = message
        return message

    def check(self) -> Iterable[tuple[Message, list[TranslationError]]]:
        """Run various validation checks on the translations in the catalog.

        For every message which fails validation, this method yield a
        ``(message, errors)`` tuple, where ``message`` is the `Message` object
        and ``errors`` is a sequence of `TranslationError` objects.

        :rtype: ``generator`` of ``(message, errors)``
        """
        for message in self._messages.values():
            errors = message.check(self)
            if errors:
                yield (message, errors)

    def get(self, id: _MessageID, context: str | None = None) -> Message | None:
        """Return the message with the specified ID and context.

        :param id: the message ID
        :param context: the message context, or ``None`` for no context
        """
        key = self._key_for(id, context)
        return self._messages.get(key)

    def delete(self, id: _MessageID, context: str | None = None) -> None:
        """Delete the message with the specified ID and context.

        :param id: the message ID
        :param context: the message context, or ``None`` for no context
        """
        key = self._key_for(id, context)
        if key in self._messages:
            del self._messages[key]

    def update(
        self,
        template: Catalog,
        no_fuzzy_matching: bool = False,
        update_header_comment: bool = False,
        keep_user_comments: bool = True,
        update_creation_date: bool = True,
    ) -> None:
        """Update the catalog based on the given template catalog.

        >>> from babel.messages import Catalog
        >>> template = Catalog()
        >>> template.add('green', locations=[('main.py', 99)])
        <Message ...>
        >>> template.add('blue', locations=[('main.py', 100)])
        <Message ...>
        >>> template.add(('salad', 'salads'), locations=[('util.py', 42)])
        <Message ...>
        >>> catalog = Catalog(locale='de_DE')
        >>> catalog.add('blue', u'blau', locations=[('main.py', 98)])
        <Message ...>
        >>> catalog.add('head', u'Kopf', locations=[('util.py', 33)])
        <Message ...>
        >>> catalog.add(('salad', 'salads'), (u'Salat', u'Salate'),
        ...             locations=[('util.py', 38)])
        <Message ...>

        >>> catalog.update(template)
        >>> len(catalog)
        3

        >>> msg1 = catalog['green']
        >>> msg1.string
        >>> msg1.locations
        [('main.py', 99)]

        >>> msg2 = catalog['blue']
        >>> msg2.string
        u'blau'
        >>> msg2.locations
        [('main.py', 100)]

        >>> msg3 = catalog['salad']
        >>> msg3.string
        (u'Salat', u'Salate')
        >>> msg3.locations
        [('util.py', 42)]

        Messages that are in the catalog but not in the template are removed
        from the main collection, but can still be accessed via the `obsolete`
        member:

        >>> 'head' in catalog
        False
        >>> list(catalog.obsolete.values())
        [<Message 'head' (flags: [])>]

        :param template: the reference catalog, usually read from a POT file
        :param no_fuzzy_matching: whether to use fuzzy matching of message IDs
        """
        messages = self._messages
        remaining = messages.copy()
        self._messages = OrderedDict()

        for message in template:
            if message.id:
                current = remaining.pop(
                    self._key_for(message.id, message.context), None
                )
                if current is None:
                    if not no_fuzzy_matching:
                        # Try to find a fuzzy match for the message
                        fuzzy_matches = get_close_matches(
                            self._to_fuzzy_match_key(message.id),
                            [self._to_fuzzy_match_key(key) for key in remaining.keys()],
                            n=1,
                            cutoff=0.7,
                        )
                        if fuzzy_matches:
                            fuzzy_match_key = fuzzy_matches[0]
                            current = remaining.pop(
                                next(
                                    key
                                    for key in remaining.keys()
                                    if self._to_fuzzy_match_key(key) == fuzzy_match_key
                                )
                            )
                            current.fuzzy = True
                    if current is None:
                        current = Message(
                            message.id,
                            message.string,
                            message.locations,
                            message.flags,
                            message.auto_comments,
                            message.user_comments,
                            message.previous_id,
                            message.lineno,
                            message.context,
                        )
                else:
                    current.locations = message.locations
                    current.auto_comments = message.auto_comments
                    if not keep_user_comments:
                        current.user_comments = message.user_comments
                self._messages[self._key_for(message.id, message.context)] = current

        for msgid in remaining:
            self.obsolete[msgid] = remaining[msgid]

        if update_header_comment:
            self.header_comment = template.header_comment

        if update_creation_date:
            self.creation_date = template.creation_date

    def _to_fuzzy_match_key(self, key: tuple[str, str] | str) -> str:
        """Converts a message key to a string suitable for fuzzy matching."""
        if isinstance(key, tuple):
            id, context = key
        else:
            id, context = key, None

        if isinstance(id, (list, tuple)):
            id = id[0]

        key = id.lower()
        if context:
            key += "\0" + context.lower()
        return key

    def _key_for(
        self, id: _MessageID, context: str | None = None
    ) -> tuple[str, str] | str:
        """The key for a message is just the singular ID even for pluralizable
        messages, but is a ``(msgid, msgctxt)`` tuple for context-specific
        messages.
        """
        if isinstance(id, (list, tuple)):
            id = id[0]
        if context is not None:
            return (id, context)
        return id

    def is_identical(self, other: Catalog) -> bool:
        """Checks if catalogs are identical, taking into account messages and
        headers.
        """
        if len(self._messages) != len(other._messages):
            return False

        for key, message in self._messages.items():
            other_message = other._messages.get(key)
            if not other_message or not message.is_identical(other_message):
                return False

        return (
            self.locale == other.locale
            and self.domain == other.domain
            and self.header_comment == other.header_comment
            and self.project == other.project
            and self.version == other.version
            and self.copyright_holder == other.copyright_holder
            and self.msgid_bugs_address == other.msgid_bugs_address
            and self.creation_date == other.creation_date
            and self.revision_date == other.revision_date
            and self.last_translator == other.last_translator
            and self.language_team == other.language_team
            and self.charset == other.charset
            and self.fuzzy == other.fuzzy
        )
