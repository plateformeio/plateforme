# plateforme.core.patterns
# ------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities to interact with Python patterns such as regular
expressions within the Plateforme framework.
"""

import re
from enum import StrEnum
from typing import Any, Callable, Literal

from .typing import Deferred

__all__ = (
    'CHAR_MARK',
    'CHAR_SEP',
    'EMAIL_MAX_LENGTH',
    'WILDCARD',
    'RegexPattern',
    'match_any_pattern',
    'parse_email',
    'parse_selection_assignment',
    'parse_selection',
    'pluralize',
    'to_camel_case',
    'to_kebab_case',
    'to_name_case',
    'to_pascal_case',
    'to_path_case',
    'to_snake_case',
    'to_title_case',
)


CHAR_MARK = '\uE000'
"""A special character used as a placeholder for string transformations."""


CHAR_SEP = '\uE001'
"""A special character used as a separator for string transformations."""


EMAIL_MAX_LENGTH = 2048
"""The maximum accepted length for an email address."""


WILDCARD = '*'
"""The wildcard entry name used for selection assignments."""


BracketType = Literal['all', 'curly', 'round', 'square']
"""A type alias used for bracket removal options."""


def _build_email_formatted_pattern() -> str:
    """Build a regular expression pattern for formatted email parsing."""
    name_chars = r'[\w!#$%&\'*+\-/=?^_`{|}~]'
    unquoted_name_group = rf'((?:{name_chars}+\s+)*{name_chars}+)'
    quoted_name_group = r'"((?:[^"]|\")+)"'
    email_group = r'<\s*(\w[\w!.%+-]*@[a-zA-Z\d.-]+\.[a-zA-Z]{2,})\s*>'
    return (
        rf'^\s*(?:{unquoted_name_group}|{quoted_name_group})?'
        rf'\s*{email_group}\s*$'
    )


def _build_brackets_pattern(brackets: BracketType | set[BracketType]) -> str:
    """Build a regular expression pattern for bracket content matching.

    Args:
        brackets: The type of brackets to match. The options are ``'all'``,
            ``'curly'``, ``'round'``, and ``'square'``. If a set is provided,
            all brackets in the set will be matched.

    Returns:
        A regular expression pattern for matching the content enclosed within
        specific brackets.
    """
    if isinstance(brackets, str):
        brackets = {brackets}
    if 'all' in brackets:
        brackets = {'curly', 'round', 'square'}

    pattern: list[str] = []
    for bracket in brackets:
        if bracket == 'curly':
            pattern.append(r'\{[^\{\(\)\[\]]*?\}')
        elif bracket == 'round':
            pattern.append(r'\([^\{\}\(\[\]]*?\)')
        elif bracket == 'square':
            pattern.append(r'\[[^\{\}\(\)\[]*?\]')

    return '|'.join(pattern)


def _build_brackets_replacements(
    string: str,
    *,
    brackets: BracketType | set[BracketType],
    processor: Callable[[str], str] | None = None,
    replacements: list[str] | None = None,
) -> tuple[str, list[str]]:
    """Build a list of bracket content replacements in a string.

    It processes the string to find and replace the content enclosed within
    specific brackets with a placeholder. The enclosed content is then stored
    in a list for later retrieval and replacements. The processor function can
    be used to modify the enclosed content before storing it in the list.

    Args:
        string: The string to process.
        brackets: The type of brackets to process. The options are ``'all'``,
            ``'curly'``, ``'round'``, and ``'square'``. If a set is provided,
            all brackets in the set will be processed.
        processor: The processor function to apply on the enclosed content. The
            function should accept a string argument and return a string. If
            set to ``None``, the enclosed content will be removed from the
            string. Defaults to ``None``.
        replacements: The list to store the bracket content replacements. If
            not provided, a new list will be created.
            Defaults to ``None``.

    Returns:
        A tuple containing the processed string and the bracket content
        replacements.
    """
    pattern = _build_brackets_pattern(brackets)
    processor = processor or (lambda x: '')
    replacements = replacements or []

    processed = string
    while True:
        for match in re.finditer(pattern, string):
            content = match.group()
            placeholder = f'{CHAR_MARK}{len(replacements)}{CHAR_MARK}'
            replacements.append(processor(content))
            processed = string.replace(content, placeholder)
        if processed == string:
            break
        string = processed
    return string, replacements


class RegexPattern(StrEnum):
    """A enumeration of regex patterns used within the Plateforme framework."""

    ALIAS = r'^[a-z][a-z\d]*(?:_[a-z\d]+)*$'
    """Pattern for validating aliases.

    It should start with a lowercase letter, followed by lowercase letters or
    digits. Underscores can be used to separate words within the name.
    """

    ALIAS_EXP = r'^[a-z][a-z\d]*(?:_[a-z\d]+)*\*?$'
    """Pattern for validating alias expressions.

    It is the same as the ``ALIAS`` pattern but allows an optional expression
    spread symbol character ``'*'`` at the end of the name, which is used to
    indicate list expansion.
    """

    ASSIGNMENT = r'^(?:([a-zA-Z][a-zA-Z\d]*(?:_[a-zA-Z\d]+)*)=)?(\?|.+)$'
    """Pattern for validating a selector assignment.

    It can be prefixed with a case-insensitive version of an assignment alias
    matching the ``ALIAS`` pattern followed by an equal character. The
    assignment value can contain any character other than newline. Optionally,
    the value can be a question mark ``'?'`` to represent a deferred value that
    should be inferred when resolving the selection.

    It captures the selection assignment in two groups:
    1.  ``alias`` (optional): The selection assignment alias.
    2.  ``value``: The selection assignment value, or ``'?'`` for deferred one.
    """

    EMAIL_FORMATTED = _build_email_formatted_pattern()
    """Pattern for validating formatted email addresses.

    It captures the email address in three groups:
    1.  ``unquoted_name`` (optional): The unquoted email address name.
    2.  ``quoted_name`` (optional): The quoted email address name.
    3.  ``email``: The email address in angle brackets without leading and
        trailing spaces.
    """

    EMAIL_PLAIN = r'^(\w[\w!.%+-]*)@([a-zA-Z\d.-]+\.[a-zA-Z]{2,})$'
    """Pattern for validating plain email addresses.

    It captures the email address in two groups:
    1.  ``username``: The email address username.
    2.  ``domain``: The email address domain.
    """

    ENGINE_SCHEME = r'^((\w+)(?:\+(\w+))?)$'
    """Pattern for validating database engine URL schemes.

    It captures and validates the scheme part of the connection string and with
    the dialect and driver parts separated in groups. The capturing groups are
    as follows:

    1.  ``scheme``: The full scheme string including both dialect and driver
        parts (e.g. ``mysql+aiomysql`` where ``mysql`` is the dialect part and
        ``aiomysql`` is the driver part).

    2.  ``dialect``: The dialect part of the database scheme
        (e.g. ``mysql`` in ``mysql+aiomysql``).

    3.  ``driver`` (optional): The driver part of the database scheme, if
        present (e.g. ``aiomysql`` in ``mysql+aiomysql``).

    """

    ENGINE_ADDRESS = r'^(?:(\w+):(\w+)@)?(?:(\w+)(?::(\w+))?)?\/(.+)$'
    """Pattern for validating database engine URL addresses.

    It captures and validates the address part of the connection string with
    the username, password, host, port, and database separated in groups. The
    capturing groups are as follows:

    1.  ``username`` (optional): The username for database authentication
        (e.g. ``user`` in ``user:password@localhost:5432/dbname``).

    2.  ``password`` (optional): The password for database authentication
        (e.g. ``password`` in ``user:password@localhost:5432/dbname``).

    3.  ``host`` (optional): The hostname or IP address of the database server
        (e.g. ``localhost`` in ``user:password@localhost:5432/dbname``).

    4.  ``port`` (optional): The port number for the database server, if
        specified (e.g. ``5432`` in ``user:password@localhost:5432/dbname``).

    5.  ``database``: The name or path of the database to connect to
        (e.g. ``dbname`` in ``user:password@localhost:5432/dbname``).
    """

    ENGINE = (
        r'^((\w+)(?:\+(\w+))?):\/\/'
        r'(?:(\w+):(\w+)@)?(?:(\w+)(?::(\w+))?)?\/(.+)$'
    )
    """Pattern for validating database engine URLs.

    It captures and validates the whole connection string and each of its parts
    in separate groups. The capturing groups are as follows:

    1.  ``scheme``: The full scheme string including both dialect and driver
        parts (e.g. ``mysql+aiomysql`` where ``mysql`` is the dialect part and
        ``aiomysql`` is the driver part).

    2.  ``dialect``: The dialect part of the database scheme
        (e.g. ``mysql`` in ``mysql+aiomysql``).

    3.  ``driver`` (optional): The driver part of the database scheme, if
        present (e.g. ``aiomysql`` in ``mysql+aiomysql``).

    4.  ``username`` (optional): The username for database authentication
        (e.g. ``user`` in ``user:password@localhost:5432/dbname``).

    5.  ``password`` (optional): The password for database authentication
        (e.g. ``password`` in ``user:password@localhost:5432/dbname``).

    6.  ``host`` (optional): The hostname or IP address of the database server
        (e.g. ``localhost`` in ``user:password@localhost:5432/dbname``).

    7.  ``port`` (optional): The port number for the database server, if
        specified (e.g. ``5432`` in ``user:password@localhost:5432/dbname``).

    8.  ``database``: The name or path of the database to connect to
        (e.g. ``dbname`` in ``user:password@localhost:5432/dbname``).
    """

    LANGUAGE = r'^[a-zA-Z]{2}(?:-[a-zA-Z]{2})?$'
    """Pattern for validating language codes.

    It should start with two letters, followed by a hyphen and two more letters
    (optional). It enforces the language code to follow the ISO 639-1 standard.
    """

    MODULE = r'^[a-zA-Z_][a-zA-Z\d_]*(?:\.[a-zA-Z_][a-zA-Z\d_]*)*$'
    """Pattern for validating module names.

    It should start with a letter or an underscore, followed by letters, digits
    or underscores. Module segments can be separated by dots while underscores
    can be used within each segment to separate words.
    """

    NAME = (
        r'^[a-z][a-z\d]*(?:_[a-z\d]+)*'
        r'(?:\.[a-z][a-z\d]*(?:_[a-z\d]+)*)*$'
    )
    """Pattern for validating names.

    It should start with a lowercase letter, followed by lowercase letters or
    digits. Segments of the name can be separated by dots while underscores can
    be used within each segment to separate words.
    """

    NAME_EXP = (
        r'^[a-z][a-z\d]*(?:_[a-z\d]+)*\*?'
        r'(?:\.[a-z][a-z\d]*(?:_[a-z\d]+)*\*?)*$'
    )
    """Pattern for validating name expressions.

    It is the same as the ``NAME`` pattern but allows an optional expression
    spread symbol character ``'*'`` at the end of each segment, which is used
    to indicate list expansion.
    """

    PATH = (
        r'^\/[a-z][a-z\d]*(?:-[a-z\d]+)*'
        r'(?:\/(?:[a-z][a-z\d]*(?:-[a-z\d]+)*'
        r'|\{[a-z_][a-z\d]*(?:_[a-z\d]+)*\}))*$'
    )
    """Pattern for validating paths.

    It should start with a slash and then for each segment a lowercase letter,
    followed by lowercase letters or digits. Path segments can be separated by
    slashes while hyphens can be used within each segment to separate words.
    Optionally segments can be enclosed in curly braces for path parameters,
    where the parameter name should start with a lowercase letter or an
    underscore, followed by letters, digits or underscores.
    """

    SLUG = r'^[a-z][a-z\d]*(?:-[a-z\d]+)*$'
    """Pattern for validating slugs.

    It should start with a lowercase letter, followed by lowercase letters or
    digits. Hyphens can be used to separate words within the slug.
    """

    TITLE = (
        r'^[A-Z][a-zA-Z\d]*(?:-[a-zA-Z\d]+)*'
        r'(?:(?:\s|\s-\s)[a-zA-Z\d]+(?:-[a-zA-Z\d]+)*)*$'
    )
    """Pattern for validating titles.

    It should start with an uppercase letter, followed by any alphanumeric
    characters that can be separated by a hyphen. Additional words are
    separated by spaces, where hyphens can be used to separate parts of the
    title. More information can be found for the title case format standard at
    https://en.wikipedia.org/wiki/title_case.
    """

    VERSION = r'^(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:\-([a-z]+\d*))?$'
    """Pattern for validating version numbers.

    It should start with a number, followed by a dot and another number
    (optional), followed by a hyphen and a string of lowercase letters and zero
    or more digits (optional).

    It captures the version information in four groups:

    1.  ``major``: The major version number.
    2.  ``minor`` (optional): The minor version number.
    3.  ``patch`` (optional): The patch version number.
    4.  ``tag`` (optional): The version tag, e.g. ``alpha1``, ``beta2``, etc.
    """


def match_any_pattern(string: str, *patterns: str) -> bool:
    """Check if the input string matches any of the provided patterns.

    This function iterates through a list of patterns and checks if the input
    string matches any of them from start to end. Each pattern is anchored to
    the start and end of the string to ensure a full match.

    Args:
        string: The string to be checked against the patterns.
        *patterns: Variable length argument list of string patterns.

    Returns:
        ``True`` if the string matches any of the provided patterns, ``False``
        otherwise.
    """
    for pattern in patterns:
        pattern = r'^' + pattern + r'$'
        if re.search(pattern, string):
            return True
    return False


def parse_email(string: str) -> tuple[str | None, str]:
    """Parse a string containing a formatted email address into a tuple.

    It parses an email address that is either plain or formatted as a name
    followed by an email address in angle brackets. The email address is
    validated against the ``EMAIL_FORMATTED`` and ``EMAIL_PLAIN`` patterns.

    Args:
        string: The string containing the email address to parse.

    Returns:
        A tuple containing the parsed email address name and email address.

    Note:
        Spaces are striped from the beginning and end of addresses.
    """
    # Validate email length
    if len(string) > EMAIL_MAX_LENGTH:
        raise ValueError(
            f"Email address exceeds the maximum length of {EMAIL_MAX_LENGTH} "
            f"characters. Got: {string!r}."
        )

    # Try to match the email formatted pattern
    if match := re.match(RegexPattern.EMAIL_FORMATTED, string):
        unquoted_name, quoted_name, email = match.groups()
        return unquoted_name or quoted_name, email
    # Try to match the plain email pattern
    if match := re.match(RegexPattern.EMAIL_PLAIN, string):
        return None, string

    raise ValueError(
        f"Invalid email address format, expected `name <email>` or plain "
        f"`email` format. Got: {string!r}."
    )


def parse_selection_assignment(string: str) -> tuple[str, Any]:
    """Parse a string containing a selection assignment into a tuple.

    It parses a selection assignment that is formatted either as an alias
    followed by an equal character and a value ``alias=value``, or just a
    value. The assignment alias is case-insensitive and parsed as a lowercase
    string, while the value can be any string other than a newline character.
    Optionally, the value can be a question mark ``'?'`` to represent a
    deferred value that should be inferred when resolving the selection, it is
    replaced with a ``Deferred`` object.

    In addition, the alias is optional and can be omitted, in which case the
    wildcard character ``*`` is returned as the alias.

    Args:
        string: The string containing the selection assignment to parse.

    Returns:
        A tuple containing the parsed selection assignment alias and value.
    """
    # Retrieve the selection assignment alias and value
    assignment = re.match(RegexPattern.ASSIGNMENT, string)
    if not assignment:
        raise ValueError(
            f"Invalid selection assignment format, expected `alias=value` or "
            f"`value` format. Got: {string!r}."
        )

    # Parse the selection assignment alias and value
    alias, value = assignment.groups()
    alias = WILDCARD if alias is None else alias.lower()
    value = Deferred if value == '?' else value

    return alias, value


def parse_selection(
    string: str, *, separator: str = ';'
) -> dict[str, Any]:
    """Parse a string containing selection assignments into a dictionary.

    It parses a composite selection that is formatted as a list of selection
    assignments separated by a specified separator (by default a semicolons
    ``';'``). Each selection assignment alias and value are parsed using the
    regular expression pattern ``ASSIGNMENT`` (see the function
    `parse_selection_assignment` for more details). Only one wildcard selection
    assignment ``*``, i.e. a selection assignment without an alias, is allowed
    in the selection assignments string.

    Args:
        string: The string containing the selection assignments to parse.
        separator: The separator used to split the selection assignments.
            Defaults to a semicolon ``';'``.

    Returns:
        A base selection dictionary containing the parsed selection assignments
        where a wildcard alias ``'*'``is used for assignments without an alias
        and values ``'?'`` replaced with ``Deferred``.
    """
    selection = {}

    assignments = string.split(separator)
    for assignment in assignments:
        # Retrieve selection assignment alias and value
        alias, value = parse_selection_assignment(assignment)

        # Check for duplicate selection assignment aliases
        if alias in selection:
            raise KeyError(
                f"Duplicate selection assignment aliases found for {alias!r} "
                f"in selection {string!r}."
            )

        # Add the parsed selection assignment to the dictionary
        selection[alias] = value

    return selection


def pluralize(string: str) -> str:
    """Convert a singular string to its plural form.

    It's a simple pluralization function that handles common English
    pluralization patterns. The function is not perfect and may not cover all
    edge cases, but it should work well for most common words.

    Args:
        string: The singular string to pluralize.

    Returns:
        The pluralized form of the input string.

    Examples:
        >>> pluralize('user')      # -> users
        >>> pluralize('box')       # -> boxes
        >>> pluralize('category')  # -> categories
        >>> pluralize('day')       # -> days
        >>> pluralize('leaf')      # -> leaves
    """
    # Handle words ending in "s", "sh", "ch", "x", and "z" -> add "es"
    if string.lower().endswith(('s', 'sh', 'ch', 'x', 'z')):
        return string + 'es'

    # Handle words ending in "f" or "fe" -> replace with "ves"
    if string.lower().endswith(('f', 'fe')):
        if string.lower().endswith('fe'):
            return string[:-2] + 'ves'
        return string[:-1] + 'ves'

    # Handle words ending in "y"
    if string.lower().endswith('y'):
        # If "y" is preceded by a consonant -> replace with "ies"
        if len(string) > 1 and string[-2].lower() not in 'aeiou':
            return string[:-1] + 'ies'
        # If "y" is preceded by a vowel -> add "s"
        return string + 's'

    # Default -> add "s"
    return string + 's'


def to_camel_case(string: str) -> str:
    """Convert a string to camel case.

    Args:
        string: The string to convert.

    Returns:
        The converted string to camel case.

    Examples:
        >>> to_camel_case('camel case example')
        'camelCaseExample'
    """
    s = string
    s = re.sub(r'[\s\-\_]', CHAR_SEP, s)
    s = re.sub(r'(?<![\.\/\\])(?=[A-Z][a-z\d]+)', CHAR_SEP, s)
    s = re.sub(rf'^{CHAR_SEP}+|{CHAR_SEP}+$', '', s)
    s = re.sub(rf'{CHAR_SEP}+(.)', lambda m: m.group(1).upper(), s)
    return ''.join([s[0].lower(), s[1:]])


def to_kebab_case(string: str) -> str:
    """Convert a string to kebab case.

    Args:
        string: The string to convert.

    Returns:
        The converted string to kebab case.

    Examples:
        >>> to_kebab_case('kebab case example')
        'kebab-case-example'
    """
    s = string
    s = re.sub(r'[\s\-\_]', CHAR_SEP, s)
    s = re.sub(r'(?<![\.\/\\])(?=[A-Z][a-z\d]+)', CHAR_SEP, s)
    s = re.sub(rf'^{CHAR_SEP}+|{CHAR_SEP}+$', '', s)
    s = re.sub(rf'{CHAR_SEP}+', '-', s)
    return s.lower()


def to_pascal_case(string: str) -> str:
    """Convert a string to pascal case.

    Args:
        string: The string to convert.

    Returns:
        The converted string to pascal case.

    Examples:
        >>> to_pascal_case('pascal case example')
        'PascalCaseExample'
    """
    s = string
    s = re.sub(r'[\s\-\_]', CHAR_SEP, s)
    s = re.sub(r'(?<![\.\/\\])(?=[A-Z][a-z\d]+)', CHAR_SEP, s)
    s = re.sub(rf'^{CHAR_SEP}+|{CHAR_SEP}+$', '', s)
    s = re.sub(rf'{CHAR_SEP}+(.)', lambda m: m.group(1).upper(), s)
    return ''.join([s[0].upper(), s[1:]])


def to_snake_case(string: str) -> str:
    """Convert a string to snake case.

    Args:
        string: The string to convert.

    Returns:
        The converted string to snake case.

    Examples:
        >>> to_snake_case('snake case example')
        'snake_case_example'
    """
    s = string
    s = re.sub(r'[\s\-\_]', CHAR_SEP, s)
    s = re.sub(r'(?<![\.\/\\])(?=[A-Z][a-z\d]+)', CHAR_SEP, s)
    s = re.sub(rf'^{CHAR_SEP}+|{CHAR_SEP}+$', '', s)
    s = re.sub(rf'{CHAR_SEP}+', '_', s)
    return s.lower()


def to_title_case(string: str) -> str:
    """Convert a string to title case.

    Args:
        string: The string to convert.

    Returns:
        The converted string to title case.

    Examples:
        >>> to_title_case('title_case_example')
        'Title Case Example'
    """
    s = string
    s = re.sub(r'[\s\-\_]', CHAR_SEP, s)
    s = re.sub(r'(?<![\.\/\\])(?=[A-Z][a-z\d]+)', CHAR_SEP, s)
    s = re.sub(rf'^{CHAR_SEP}+|{CHAR_SEP}+$', '', s)
    s = re.sub(rf'{CHAR_SEP}+', ' ', s)
    return s.title()


def to_name_case(
    string: str,
    *brackets_handlers: tuple[
        BracketType | set[BracketType], Callable[[str], str] | None
    ],
) -> str:
    """Convert a string to name case.

    Args:
        string: The string to convert.
        *brackets_handlers: List of brackets handler tuples containing the type
            of brackets for which the enclosed content should be processed and
            the processor function to apply on the enclosed content. The
            options for brackets are ``'all'``, ``'curly'``, ``'round'``, and
            ``'square'``. If a set is provided, all brackets in the set will be
            processed. The processor function should accept a string argument
            and return a string. If set to ``None``, the enclosed content will
            be removed from the string.

    Returns:
        The converted string to name case.

    Examples:
        >>> to_name_case('name-case/example')
        'name_case.example'
        >>> to_name_case('NameCase[Example]', ('square', None))
        'name_case'
    """
    replacements: list[str] = []
    for brackets, processor in brackets_handlers:
        string, replacements = _build_brackets_replacements(
            string,
            brackets=brackets,
            processor=processor,
            replacements=replacements,
        )
    s = string
    s = to_snake_case(s)
    s = re.sub(r'[\/\\]', '.', s)
    for count, replacement in enumerate(replacements):
        s = s.replace(f'{CHAR_MARK}{count}{CHAR_MARK}', replacement)
    return s


def to_path_case(
    string: str,
    *brackets_handlers: tuple[
        BracketType | set[BracketType], Callable[[str], str] | None
    ],
) -> str:
    """Convert a string to path case.

    Args:
        string: The string to convert.
        *brackets_handlers: List of brackets handler tuples containing the type
            of brackets for which the enclosed content should be processed and
            the processor function to apply on the enclosed content. The
            options for brackets are ``'all'``, ``'curly'``, ``'round'``, and
            ``'square'``. If a set is provided, all brackets in the set will be
            processed. The processor function should accept a string argument
            and return a string. If set to ``None``, the enclosed content will
            be removed from the string.

    Returns:
        The converted string to path case.

    Examples:
        >>> to_path_case('path_case.example')
        'path-case/example'
        >>> to_path_case('PathCase[Example]', ('square', None))
    """
    replacements: list[str] = []
    for brackets, processor in brackets_handlers:
        string, replacements = _build_brackets_replacements(
            string,
            brackets=brackets,
            processor=processor,
            replacements=replacements,
        )
    s = string
    s = to_kebab_case(s)
    s = re.sub(r'\.\\', '/', s)
    for count, replacement in enumerate(replacements):
        s = s.replace(f'{CHAR_MARK}{count}{CHAR_MARK}', replacement)
    return s
