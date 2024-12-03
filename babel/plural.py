"""
    babel.numbers
    ~~~~~~~~~~~~~

    CLDR Plural support.  See UTS #35.

    :copyright: (c) 2013-2023 by the Babel Team.
    :license: BSD, see LICENSE for more details.
"""
from __future__ import annotations
import decimal
import re
from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Any, Callable
if TYPE_CHECKING:
    from typing_extensions import Literal
    Symbol Value
    ------ ---------------------------------------------------------------
    n      absolute value of the source number (integer and decimals).
    i      integer digits of n.
    v      number of visible fraction digits in n, with trailing zeros.
    w      number of visible fraction digits in n, without trailing zeros.
    f      visible fractional digits in n, with trailing zeros.
    t      visible fractional digits in n, without trailing zeros.

    ====== ===============================================================
    Symbol Value
    ------ ---------------------------------------------------------------
    n      absolute value of the source number (integer and decimals).
    i      integer digits of n.
    v      number of visible fraction digits in n, with trailing zeros.
    w      number of visible fraction digits in n, without trailing zeros.
    f      visible fractional digits in n, with trailing zeros.
    t      visible fractional digits in n, without trailing zeros.
    c      compact decimal exponent value: exponent of the power of 10 used in compact decimal formatting.
    e      currently, synonym for ‘c’. however, may be redefined in the future.
    ====== ===============================================================

    .. _`CLDR rules`: https://www.unicode.org/reports/tr35/tr35-61/tr35-numbers.html#Operands

    :param source: A real number
    :type source: int|float|decimal.Decimal
    :return: A n-i-v-w-f-t-c-e tuple
    :rtype: tuple[decimal.Decimal, int, int, int, int, int, int, int]
    """
    pass

class PluralRule:
    """
    Represents a set of language pluralization rules.

    The constructor accepts a list of (tag, expr) tuples or a dict of `CLDR rules`_.
    The resulting object is callable and accepts one parameter with a positive or
    negative number (both integer and float) for the number that indicates the
    plural form for a string and returns the tag for the format.

    Currently the CLDR defines these tags: zero, one, two, few, many and
    other where other is an implicit default. Rules should be mutually
    exclusive; for a given numeric value, only one rule should apply.

    Example:
        >>> rule = PluralRule({'one': 'n is 1'})
        >>> rule(1)
        'one'
        >>> rule(2)
        'other'

    .. _`CLDR rules`: https://www.unicode.org/reports/tr35/tr35-33/tr35-numbers.html#Language_Plural_Rules
    """
    __slots__ = ('abstract', '_func')

    def __init__(self, rules: Mapping[str, str] | Iterable[tuple[str, str]]) -> None:
        """Initialize the rule instance.

        :param rules: a list of ``(tag, expr)``) tuples with the rules
                      conforming to UTS #35 or a dict with the tags as keys
                      and expressions as values.
        :raise RuleError: if the expression is malformed
        """
        if isinstance(rules, Mapping):
            rules = rules.items()
        found = set()
        self.abstract: list[tuple[str, Any]] = []
        for key, expr in sorted(rules):
            if key not in _plural_tags:
                raise ValueError(f'unknown tag {key!r}')
            elif key in found:
                raise ValueError(f'tag {key!r} defined twice')
            found.add(key)
            ast = _Parser(expr).ast
            if ast:
                self.abstract.append((key, ast))

    def __repr__(self) -> str:
        rules = self.rules
        args = ', '.join([f'{tag}: {rules[tag]}' for tag in _plural_tags if tag in rules])
        return f'<{type(self).__name__} {args!r}>'

    @classmethod
    def parse(cls, rules: Mapping[str, str] | Iterable[tuple[str, str]] | PluralRule) -> PluralRule:
        """
        Create a `PluralRule` instance for the given rules.

        If the rules are a `PluralRule` object, that object is returned.

        Args:
            rules: The rules as list or dict, or a `PluralRule` object

        Raises:
            RuleError: If the expression is malformed

        Returns:
            PluralRule: A new PluralRule instance
        """
        if isinstance(rules, PluralRule):
            return rules
        return cls(rules)

    @property
    def rules(self) -> Mapping[str, str]:
        """The `PluralRule` as a dict of unicode plural rules.

        >>> rule = PluralRule({'one': 'n is 1'})
        >>> rule.rules
        {'one': 'n is 1'}
        """
        return {tag: _UnicodeCompiler().compile(ast) for tag, ast in self.abstract}

    @property
    def tags(self) -> frozenset[str]:
        """
        A set of explicitly defined tags in this rule.

        The implicit default ``'other'`` rule is not part of this set unless
        there is an explicit rule for it.

        Returns:
            frozenset[str]: A set of tags
        """
        return frozenset(tag for tag, _ in self.abstract)

    def __getstate__(self) -> list[tuple[str, Any]]:
        return self.abstract

    def __setstate__(self, abstract: list[tuple[str, Any]]) -> None:
        self.abstract = abstract

    def __call__(self, n: float | decimal.Decimal) -> str:
        if not hasattr(self, '_func'):
            self._func = to_python(self)
        return self._func(n)

def to_javascript(rule: Mapping[str, str] | Iterable[tuple[str, str]] | PluralRule) -> str:
    """
    Convert a list/dict of rules or a `PluralRule` object into a JavaScript function.

    This function depends on no external library.

    Args:
        rule: The rules as list or dict, or a `PluralRule` object

    Raises:
        RuleError: If the expression is malformed

    Returns:
        str: A JavaScript function as a string

    Example:
        >>> to_javascript({'one': 'n is 1'})
        "(function(n) { return (n == 1) ? 'one' : 'other'; })"

    Note:
        The function generated will probably evaluate expressions involved in range
        operations multiple times. This has the advantage that external helper
        functions are not required and is not a big performance hit for these
        simple calculations.
    """
    if not isinstance(rule, PluralRule):
        rule = PluralRule.parse(rule)
    
    compiler = _JavaScriptCompiler()
    parts = []
    for tag, ast in rule.abstract:
        expr = compiler.compile(ast)
        parts.append(f"({expr}) ? '{tag}' : ")
    parts.append("'other'")
    return f"(function(n) {{ return {' '.join(parts)}; }})"

def to_python(rule: Mapping[str, str] | Iterable[tuple[str, str]] | PluralRule) -> Callable[[float | decimal.Decimal], str]:
    """
    Convert a list/dict of rules or a `PluralRule` object into a regular Python function.

    This is useful in situations where you need a real function and don't care about
    the actual rule object.

    Args:
        rule: The rules as list or dict, or a `PluralRule` object

    Raises:
        RuleError: If the expression is malformed

    Returns:
        Callable[[float | decimal.Decimal], str]: A Python function

    Examples:
        >>> func = to_python({'one': 'n is 1', 'few': 'n in 2..4'})
        >>> func(1)
        'one'
        >>> func(3)
        'few'
        >>> func = to_python({'one': 'n in 1,11', 'few': 'n in 3..10,13..19'})
        >>> func(11)
        'one'
        >>> func(15)
        'few'
    """
    if not isinstance(rule, PluralRule):
        rule = PluralRule.parse(rule)
    
    compiler = _PythonCompiler()
    parts = []
    for tag, ast in rule.abstract:
        expr = compiler.compile(ast)
        parts.append(f"if {expr}: return '{tag}'")
    parts.append("return 'other'")
    
    code = '\n'.join(parts)
    namespace = {'MOD': cldr_modulo, 'extract_operands': extract_operands}
    exec(f"def plural(n):\n    n, i, v, w, f, t, c, e = extract_operands(n)\n    {code}", namespace)
    return namespace['plural']

def to_gettext(rule: Mapping[str, str] | Iterable[tuple[str, str]] | PluralRule) -> str:
    """
    Convert the plural rule to a gettext expression.

    The gettext expression is technically limited to integers and returns
    indices rather than tags.

    Args:
        rule: The rules as list or dict, or a `PluralRule` object

    Raises:
        RuleError: If the expression is malformed

    Returns:
        str: A gettext expression

    Example:
        >>> to_gettext({'one': 'n is 1', 'two': 'n is 2'})
        'nplurals=3; plural=((n == 1) ? 0 : (n == 2) ? 1 : 2);'
    """
    if not isinstance(rule, PluralRule):
        rule = PluralRule.parse(rule)
    
    compiler = _GettextCompiler()
    parts = []
    for idx, (tag, ast) in enumerate(rule.abstract):
        expr = compiler.compile(ast)
        parts.append(f"({expr}) ? {idx} : ")
    parts.append(str(len(rule.abstract)))
    
    plural_expr = ''.join(parts)
    return f"nplurals={len(rule.abstract) + 1}; plural=({plural_expr});"

def in_range_list(num: float | decimal.Decimal, range_list: Iterable[Iterable[float | decimal.Decimal]]) -> bool:
    """
    Integer range list test.

    This is the callback for the "in" operator of the UTS #35 pluralization rule language.

    Args:
        num: The number to test
        range_list: A list of ranges to test against

    Returns:
        bool: True if the number is in any of the ranges, False otherwise

    Examples:
        >>> in_range_list(1, [(1, 3)])
        True
        >>> in_range_list(3, [(1, 3)])
        True
        >>> in_range_list(3, [(1, 3), (5, 8)])
        True
        >>> in_range_list(1.2, [(1, 4)])
        False
        >>> in_range_list(10, [(1, 4)])
        False
        >>> in_range_list(10, [(1, 4), (6, 8)])
        False
    """
    if isinstance(num, float):
        num = decimal.Decimal(str(num))
    
    for range_item in range_list:
        if isinstance(range_item, (int, float, decimal.Decimal)):
            if num == range_item:
                return True
        else:
            start, end = range_item
            if start <= num <= end and num.to_integral_value() == num:
                return True
    return False

def within_range_list(num: float | decimal.Decimal, range_list: Iterable[Iterable[float | decimal.Decimal]]) -> bool:
    """
    Float range test.

    This is the callback for the "within" operator of the UTS #35 pluralization rule language.

    Args:
        num: The number to test
        range_list: A list of ranges to test against

    Returns:
        bool: True if the number is within any of the ranges, False otherwise

    Examples:
        >>> within_range_list(1, [(1, 3)])
        True
        >>> within_range_list(1.0, [(1, 3)])
        True
        >>> within_range_list(1.2, [(1, 4)])
        True
        >>> within_range_list(8.8, [(1, 4), (7, 15)])
        True
        >>> within_range_list(10, [(1, 4)])
        False
        >>> within_range_list(10.5, [(1, 4), (20, 30)])
        False
    """
    if isinstance(num, float):
        num = decimal.Decimal(str(num))
    
    for range_item in range_list:
        if isinstance(range_item, (int, float, decimal.Decimal)):
            if num == range_item:
                return True
        else:
            start, end = range_item
            if start <= num <= end:
                return True
    return False

def cldr_modulo(a: float, b: float) -> float:
    """
    Javaish modulo.

    This modulo operator returns the value with the sign of the dividend
    rather than the divisor like Python does.

    Args:
        a: The dividend
        b: The divisor

    Returns:
        float: The result of the modulo operation

    Examples:
        >>> cldr_modulo(-3, 5)
        -3
        >>> cldr_modulo(-3, -5)
        -3
        >>> cldr_modulo(3, 5)
        3
    """
    return ((a % b) + b) % b if a < 0 else a % b

class RuleError(Exception):
    """Raised if a rule is malformed."""
_VARS = {'n', 'i', 'v', 'w', 'f', 't', 'c', 'e'}
_RULES: list[tuple[str | None, re.Pattern[str]]] = [(None, re.compile('\\s+', re.UNICODE)), ('word', re.compile(f'\\b(and|or|is|(?:with)?in|not|mod|[{''.join(_VARS)}])\\b')), ('value', re.compile('\\d+')), ('symbol', re.compile('%|,|!=|=')), ('ellipsis', re.compile('\\.{2,3}|\\u2026', re.UNICODE))]

class _Parser:
    """
    Internal parser.

    This class can translate a single rule into an abstract tree of tuples.
    It implements the following grammar:

    condition     = and_condition ('or' and_condition)*
                    ('@integer' samples)?
                    ('@decimal' samples)?
    and_condition = relation ('and' relation)*
    relation      = is_relation | in_relation | within_relation
    is_relation   = expr 'is' ('not')? value
    in_relation   = expr (('not')? 'in' | '=' | '!=') range_list
    within_relation = expr ('not')? 'within' range_list
    expr          = operand (('mod' | '%') value)?
    operand       = 'n' | 'i' | 'f' | 't' | 'v' | 'w'
    range_list    = (range | value) (',' range_list)*
    value         = digit+
    digit         = 0|1|2|3|4|5|6|7|8|9
    range         = value'..'value
    samples       = sampleRange (',' sampleRange)* (',' ('…'|'...'))?
    sampleRange   = decimalValue '~' decimalValue
    decimalValue  = value ('.' value)?

    Notes:
    - Whitespace can occur between or around any of the above tokens.
    - Rules should be mutually exclusive; for a given numeric value, only one
      rule should apply (i.e. the condition should only be true for one of
      the plural rule elements).
    - The in and within relations can take comma-separated lists, such as:
      'n in 3,5,7..15'.
    - Samples are ignored.

    The translator parses the expression on instantiation into an attribute
    called `ast`.
    """

    def __init__(self, string):
        self.tokens = tokenize_rule(string)
        if not self.tokens:
            self.ast = None
            return
        self.ast = self.condition()
        if self.tokens:
            raise RuleError(f'Expected end of rule, got {self.tokens[-1][1]!r}')

def _binary_compiler(tmpl):
    """Compiler factory for the `_Compiler`."""
    pass

def _unary_compiler(tmpl):
    """Compiler factory for the `_Compiler`."""
    pass
compile_zero = lambda x: '0'

class _Compiler:
    """The compilers are able to transform the expressions into multiple
    output formats.
    """
    compile_n = lambda x: 'n'
    compile_i = lambda x: 'i'
    compile_v = lambda x: 'v'
    compile_w = lambda x: 'w'
    compile_f = lambda x: 'f'
    compile_t = lambda x: 't'
    compile_c = lambda x: 'c'
    compile_e = lambda x: 'e'
    compile_value = lambda x, v: str(v)
    compile_and = _binary_compiler('(%s && %s)')
    compile_or = _binary_compiler('(%s || %s)')
    compile_not = _unary_compiler('(!%s)')
    compile_mod = _binary_compiler('(%s %% %s)')
    compile_is = _binary_compiler('(%s == %s)')
    compile_isnot = _binary_compiler('(%s != %s)')

class _PythonCompiler(_Compiler):
    """Compiles an expression to Python."""
    compile_and = _binary_compiler('(%s and %s)')
    compile_or = _binary_compiler('(%s or %s)')
    compile_not = _unary_compiler('(not %s)')
    compile_mod = _binary_compiler('MOD(%s, %s)')

class _GettextCompiler(_Compiler):
    """Compile into a gettext plural expression."""
    compile_i = _Compiler.compile_n
    compile_v = compile_zero
    compile_w = compile_zero
    compile_f = compile_zero
    compile_t = compile_zero

class _JavaScriptCompiler(_GettextCompiler):
    """Compiles the expression to plain of JavaScript."""
    compile_i = lambda x: 'parseInt(n, 10)'
    compile_v = compile_zero
    compile_w = compile_zero
    compile_f = compile_zero
    compile_t = compile_zero

class _UnicodeCompiler(_Compiler):
    """Returns a unicode pluralization rule again."""
    compile_is = _binary_compiler('%s is %s')
    compile_isnot = _binary_compiler('%s is not %s')
    compile_and = _binary_compiler('%s and %s')
    compile_or = _binary_compiler('%s or %s')
    compile_mod = _binary_compiler('%s mod %s')
    Symbol Value
    ------ ---------------------------------------------------------------
    n      absolute value of the source number (integer and decimals).
    i      integer digits of n.
    v      number of visible fraction digits in n, with trailing zeros.
    w      number of visible fraction digits in n, without trailing zeros.
    f      visible fractional digits in n, with trailing zeros.
    t      visible fractional digits in n, without trailing zeros.
    Symbol Value
    ------ ---------------------------------------------------------------
    n      absolute value of the source number (integer and decimals).
    i      integer digits of n.
    v      number of visible fraction digits in n, with trailing zeros.
    w      number of visible fraction digits in n, without trailing zeros.
    f      visible fractional digits in n, with trailing zeros.
    t      visible fractional digits in n, without trailing zeros.
    c      compact decimal exponent value: exponent of the power of 10 used in compact decimal formatting.
    e      currently, synonym for 'c'. however, may be redefined in the future.
