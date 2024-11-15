"""
babel.messages.frontend
~~~~~~~~~~~~~~~~~~~~~~~

Frontends for the message extraction functionality.

:copyright: (c) 2013-2023 by the Babel Team.
:license: BSD, see LICENSE for more details.
"""

from __future__ import annotations

import fnmatch
import logging
from configparser import RawConfigParser
from typing import Iterable

from babel import __version__ as VERSION

log = logging.getLogger("babel")


class BaseError(Exception):
    pass


class OptionError(BaseError):
    pass


class SetupError(BaseError):
    pass


def listify_value(arg, split=None):
    """
    Make a list out of an argument.

    Values from `distutils` argument parsing are always single strings;
    values from `optparse` parsing may be lists of strings that may need
    to be further split.

    No matter the input, this function returns a flat list of whitespace-trimmed
    strings, with `None` values filtered out.

    >>> listify_value("foo bar")
    ['foo', 'bar']
    >>> listify_value(["foo bar"])
    ['foo', 'bar']
    >>> listify_value([["foo"], "bar"])
    ['foo', 'bar']
    >>> listify_value([["foo"], ["bar", None, "foo"]])
    ['foo', 'bar', 'foo']
    >>> listify_value("foo, bar, quux", ",")
    ['foo', 'bar', 'quux']

    :param arg: A string or a list of strings
    :param split: The argument to pass to `str.split()`.
    :return:
    """
    if isinstance(arg, str):
        return [item.strip() for item in arg.split(split) if item.strip()]

    result = []
    for item in arg:
        if isinstance(item, list):
            result.extend(listify_value(item, split))
        elif item is not None:
            result.extend(listify_value(str(item), split))

    return result


class CommandMixin:
    as_args = None
    multiple_value_options = ()
    boolean_options = ()
    option_aliases = {}
    option_choices = {}
    log = log

    def __init__(self, dist=None):
        self.distribution = dist
        self.initialize_options()
        self._dry_run = None
        self.verbose = False
        self.force = None
        self.help = 0
        self.finalized = 0


class CompileCatalog(CommandMixin):
    description = "compile message catalogs to binary MO files"
    user_options = [
        (
            "domain=",
            "D",
            "domains of PO files (space separated list, default 'messages')",
        ),
        ("directory=", "d", "path to base directory containing the catalogs"),
        ("input-file=", "i", "name of the input file"),
        (
            "output-file=",
            "o",
            "name of the output file (default '<output_dir>/<locale>/LC_MESSAGES/<domain>.mo')",
        ),
        ("locale=", "l", "locale of the catalog to compile"),
        ("use-fuzzy", "f", "also include fuzzy translations"),
        ("statistics", None, "print statistics about translations"),
    ]
    boolean_options = ["use-fuzzy", "statistics"]


def _make_directory_filter(ignore_patterns):
    """
    Build a directory_filter function based on a list of ignore patterns.
    """

    def directory_filter(dirname):
        for pattern in ignore_patterns:
            if fnmatch.fnmatch(dirname, pattern):
                return False
        return True

    return directory_filter


class ExtractMessages(CommandMixin):
    description = "extract localizable strings from the project code"
    user_options = [
        ("charset=", None, 'charset to use in the output file (default "utf-8")'),
        (
            "keywords=",
            "k",
            "space-separated list of keywords to look for in addition to the defaults (may be repeated multiple times)",
        ),
        ("no-default-keywords", None, "do not include the default keywords"),
        ("mapping-file=", "F", "path to the mapping configuration file"),
        (
            "no-location",
            None,
            "do not include location comments with filename and line number",
        ),
        (
            "add-location=",
            None,
            'location lines format. If it is not given or "full", it generates the lines with both file name and line number. If it is "file", the line number part is omitted. If it is "never", it completely suppresses the lines (same as --no-location).',
        ),
        ("omit-header", None, 'do not include msgid "" entry in header'),
        ("output-file=", "o", "name of the output file"),
        ("width=", "w", "set output line width (default 76)"),
        (
            "no-wrap",
            None,
            "do not break long message lines, longer than the output line width, into several lines",
        ),
        ("sort-output", None, "generate sorted output (default False)"),
        ("sort-by-file", None, "sort output by file location (default False)"),
        ("msgid-bugs-address=", None, "set report address for msgid"),
        ("copyright-holder=", None, "set copyright holder in output"),
        ("project=", None, "set project name in output"),
        ("version=", None, "set project version in output"),
        (
            "add-comments=",
            "c",
            "place comment block with TAG (or those preceding keyword lines) in output file. Separate multiple TAGs with commas(,)",
        ),
        ("strip-comments", "s", "strip the comment TAGs from the comments."),
        (
            "input-paths=",
            None,
            "files or directories that should be scanned for messages. Separate multiple files or directories with commas(,)",
        ),
        (
            "input-dirs=",
            None,
            "alias for input-paths (does allow files as well as directories).",
        ),
        (
            "ignore-dirs=",
            None,
            'Patterns for directories to ignore when scanning for messages. Separate multiple patterns with spaces (default ".* ._")',
        ),
        ("header-comment=", None, "header comment for the catalog"),
        (
            "last-translator=",
            None,
            "set the name and email of the last translator in output",
        ),
    ]
    boolean_options = [
        "no-default-keywords",
        "no-location",
        "omit-header",
        "no-wrap",
        "sort-output",
        "sort-by-file",
        "strip-comments",
    ]
    as_args = "input-paths"
    multiple_value_options = ("add-comments", "keywords", "ignore-dirs")
    option_aliases = {
        "keywords": ("--keyword",),
        "mapping-file": ("--mapping",),
        "output-file": ("--output",),
        "strip-comments": ("--strip-comment-tags",),
        "last-translator": ("--last-translator",),
    }
    option_choices = {"add-location": ("full", "file", "never")}


class InitCatalog(CommandMixin):
    description = "create a new catalog based on a POT file"
    user_options = [
        ("domain=", "D", "domain of PO file (default 'messages')"),
        ("input-file=", "i", "name of the input file"),
        ("output-dir=", "d", "path to output directory"),
        (
            "output-file=",
            "o",
            "name of the output file (default '<output_dir>/<locale>/LC_MESSAGES/<domain>.po')",
        ),
        ("locale=", "l", "locale for the new localized catalog"),
        ("width=", "w", "set output line width (default 76)"),
        (
            "no-wrap",
            None,
            "do not break long message lines, longer than the output line width, into several lines",
        ),
    ]
    boolean_options = ["no-wrap"]


class UpdateCatalog(CommandMixin):
    description = "update message catalogs from a POT file"
    user_options = [
        ("domain=", "D", "domain of PO file (default 'messages')"),
        ("input-file=", "i", "name of the input file"),
        ("output-dir=", "d", "path to base directory containing the catalogs"),
        (
            "output-file=",
            "o",
            "name of the output file (default '<output_dir>/<locale>/LC_MESSAGES/<domain>.po')",
        ),
        ("omit-header", None, "do not include msgid  entry in header"),
        ("locale=", "l", "locale of the catalog to compile"),
        ("width=", "w", "set output line width (default 76)"),
        (
            "no-wrap",
            None,
            "do not break long message lines, longer than the output line width, into several lines",
        ),
        ("ignore-obsolete=", None, "whether to omit obsolete messages from the output"),
        (
            "init-missing=",
            None,
            "if any output files are missing, initialize them first",
        ),
        ("no-fuzzy-matching", "N", "do not use fuzzy matching"),
        ("update-header-comment", None, "update target header comment"),
        ("previous", None, "keep previous msgids of translated messages"),
        (
            "check=",
            None,
            "don't update the catalog, just return the status. Return code 0 means nothing would change. Return code 1 means that the catalog would be updated",
        ),
        (
            "ignore-pot-creation-date=",
            None,
            "ignore changes to POT-Creation-Date when updating or checking",
        ),
    ]
    boolean_options = [
        "omit-header",
        "no-wrap",
        "ignore-obsolete",
        "init-missing",
        "no-fuzzy-matching",
        "previous",
        "update-header-comment",
        "check",
        "ignore-pot-creation-date",
    ]


class CommandLineInterface:
    """Command-line interface.

    This class provides a simple command-line interface to the message
    extraction and PO file generation functionality.
    """

    usage = "%%prog %s [options] %s"
    version = f"%prog {VERSION}"
    commands = {
        "compile": "compile message catalogs to MO files",
        "extract": "extract messages from source files and generate a POT file",
        "init": "create new message catalogs from a POT file",
        "update": "update existing message catalogs from a POT file",
    }
    command_classes = {
        "compile": CompileCatalog,
        "extract": ExtractMessages,
        "init": InitCatalog,
        "update": UpdateCatalog,
    }
    log = None

    def run(self, argv=None):
        """Main entry point of the command-line interface.

        :param argv: list of arguments passed on the command-line
        """
        pass

    def _configure_command(self, cmdname, argv):
        """
        :type cmdname: str
        :type argv: list[str]
        """
        pass


def parse_mapping(fileobj, filename=None):
    """Parse an extraction method mapping from a file-like object.

    >>> buf = StringIO('''
    ... [extractors]
    ... custom = mypackage.module:myfunc
    ...
    ... # Python source files
    ... [python: **.py]
    ...
    ... # Genshi templates
    ... [genshi: **/templates/**.html]
    ... include_attrs =
    ... [genshi: **/templates/**.txt]
    ... template_class = genshi.template:TextTemplate
    ... encoding = latin-1
    ...
    ... # Some custom extractor
    ... [custom: **/custom/*.*]
    ... ''')

    >>> method_map, options_map = parse_mapping(buf)
    >>> len(method_map)
    4

    >>> method_map[0]
    ('**.py', 'python')
    >>> options_map['**.py']
    {}
    >>> method_map[1]
    ('**/templates/**.html', 'genshi')
    >>> options_map['**/templates/**.html']['include_attrs']
    ''
    >>> method_map[2]
    ('**/templates/**.txt', 'genshi')
    >>> options_map['**/templates/**.txt']['template_class']
    'genshi.template:TextTemplate'
    >>> options_map['**/templates/**.txt']['encoding']
    'latin-1'

    >>> method_map[3]
    ('**/custom/*.*', 'mypackage.module:myfunc')
    >>> options_map['**/custom/*.*']
    {}

    :param fileobj: a readable file-like object containing the configuration
                    text to parse
    :see: `extract_from_directory`
    """
    config = RawConfigParser()
    config.read_file(fileobj)

    method_map = []
    options_map = {}

    for section in config.sections():
        if section == "extractors":
            continue
        method, pattern = section.split(":", 1)
        method = method.strip()
        pattern = pattern.strip()
        method_map.append((pattern, method))
        options_map[pattern] = dict(config.items(section))

    extractors = dict(config.items("extractors"))
    for pattern, method in method_map:
        if method in extractors:
            method = extractors[method]
        options_map[pattern]["_extractor"] = method

    return method_map, options_map


def parse_keywords(strings: Iterable[str] = ()):
    """Parse keywords specifications from the given list of strings.

    >>> import pprint
    >>> keywords = ['_', 'dgettext:2', 'dngettext:2,3', 'pgettext:1c,2',
    ...             'polymorphic:1', 'polymorphic:2,2t', 'polymorphic:3c,3t']
    >>> pprint.pprint(parse_keywords(keywords))
    {'_': None,
     'dgettext': (2,),
     'dngettext': (2, 3),
     'pgettext': ((1, 'c'), 2),
     'polymorphic': {None: (1,), 2: (2,), 3: ((3, 'c'),)}}

    The input keywords are in GNU Gettext style; see :doc:`cmdline` for details.

    The output is a dictionary mapping keyword names to a dictionary of specifications.
    Keys in this dictionary are numbers of arguments, where ``None`` means that all numbers
    of arguments are matched, and a number means only calls with that number of arguments
    are matched (which happens when using the "t" specifier). However, as a special
    case for backwards compatibility, if the dictionary of specifications would
    be ``{None: x}``, i.e., there is only one specification and it matches all argument
    counts, then it is collapsed into just ``x``.

    A specification is either a tuple or None. If a tuple, each element can be either a number
    ``n``, meaning that the nth argument should be extracted as a message, or the tuple
    ``(n, 'c')``, meaning that the nth argument should be extracted as context for the
    messages. A ``None`` specification is equivalent to ``(1,)``, extracting the first
    argument.
    """

    def parse_spec(spec):
        if not spec:
            return None
        result = []
        for item in spec.split(","):
            if item.endswith("c"):
                result.append((int(item[:-1]), "c"))
            elif item.endswith("t"):
                return int(item[:-1])
            else:
                result.append(int(item))
        return tuple(result)

    keywords = {}
    for string in strings:
        if ":" in string:
            funcname, spec = string.split(":")
        else:
            funcname, spec = string, None
        keywords[funcname] = parse_spec(spec)

    # Handle polymorphic specifications
    for funcname, spec in list(keywords.items()):
        if isinstance(spec, int):
            keywords[funcname] = {spec: (spec,)}
        elif isinstance(spec, tuple) and any(isinstance(item, tuple) for item in spec):
            polymorphic_spec = {}
            for item in spec:
                if isinstance(item, tuple):
                    polymorphic_spec[item[0]] = (item,)
                else:
                    polymorphic_spec.setdefault(None, []).append(item)
            if None in polymorphic_spec:
                polymorphic_spec[None] = tuple(polymorphic_spec[None])
            keywords[funcname] = polymorphic_spec

    # Collapse single-spec dictionaries
    for funcname, spec in list(keywords.items()):
        if isinstance(spec, dict) and len(spec) == 1 and None in spec:
            keywords[funcname] = spec[None]

    return keywords


def __getattr__(name: str):
    if name in {
        "check_message_extractors",
        "compile_catalog",
        "extract_messages",
        "init_catalog",
        "update_catalog",
    }:
        from babel.messages import setuptools_frontend

        return getattr(setuptools_frontend, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


if __name__ == "__main__":
    main()
