# plateforme.core.representations
# -------------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module defines classes for enhanced representation of objects within
the Plateforme framework. It provides more debugging and logging readability.

The `Representation` class is a mixin providing customized `__str__`,
`__repr__`, `__pretty__`, and `__rich_repr__` methods for detailed and
formatted object display, compatible with devtools and rich libraries.

The `PlainRepresentation` class is a string subclass where the representation
excludes quotes, ideal for creating Python-compatible string outputs.
"""

import dataclasses
from collections.abc import Iterable
from typing import Any, Callable, Generator, Iterable

__all__ = (
    'PlainRepresentation',
    'Representation',
    'ReprArgs',
    'ReprRich',
)


ReprArgs = Iterable[tuple[str | None, Any]]
"""A type alias for arguments representation."""


ReprRich = Iterable[
    Any | tuple[Any] | tuple[str, Any] | tuple[str, Any, Any]
]
"""A type alias for rich representation."""


class Representation:
    # A representation mixin.
    # It provides the "__str__", "__repr__", "__pretty__", and "__rich_repr__"
    # methods for detailed and formatted object display.
    # (this is not a docstring to avoid adding a docstring to classes which
    # inherit from the representation class).

    # Note:
    #   - "__pretty__" is used by devtools:
    #     https://python-devtools.helpmanual.io/
    #   - "__rich_repr__" is used by rich:
    #     https://rich.readthedocs.io/en/stable/pretty.html

    __slots__ = ('__dict__',)  # type: Iterable[str]

    def __init__(self, /, **kwargs: Any) -> None:
        """
        Initialize the instance dictionary with the provided keyword arguments.
        """
        self.__dict__ = kwargs

    def __repr_args__(self) -> ReprArgs:
        """Representation of the instance's attributes.

        It retrieves the attributes to show in `__str__`, `__repr__`, and
        `__pretty__` (this is generally overridden).

        Returns:
            It returns an iterable of name and value pairs, e.g.
            ``[('foo_name', 'foo'), ('bar_name', ['b', 'a', 'r'])]``
        """
        names = self.__slots__
        if hasattr(self, '__dict__') and names == ('__dict__',):
            names = self.__dict__.keys()
        if hasattr(self, '__dataclass_fields__'):
            fields: dict[str, dataclasses.Field[Any]] = \
                getattr(self, '__dataclass_fields__')
            names = [a for a in names if a in fields and fields[a].repr]

        repr_args = []
        for name in names:
            # Skip dunder attributes
            if name.startswith('__') and name.endswith('__'):
                continue
            if value := getattr(self, name):
                repr_args.append((name, value))

        return repr_args

    def __repr_name__(self) -> str:
        """Name of the instance's class, used in `__repr__`."""
        return self.__class__.__name__

    def __repr_str__(
        self,
        separator: str = ', ',
    ) -> str:
        """String representation of the instance's attributes.

        It is used in `__str__` and `__repr__` methods.

        Args:
            separator: The separator to use between attributes.
                Defaults to a semicolon ``', '``.
        """
        args = []
        for name, value in self.__repr_args__():
            value = repr(value)
            value = value if not name else f'{name}={value}'
            args.append(value)

        return separator.join(args)

    def __repr__(self) -> str:
        from .functions import caller_manager

        with caller_manager(self, salt='repr') as caller_stack:
            if caller_stack[-1] in caller_stack[:-1]:
                return '...'
            repr_name = self.__repr_name__()
            repr_str = self.__repr_str__()
            return f'{repr_name}({repr_str})'

    def __str__(self) -> str:
        from .functions import caller_manager

        with caller_manager(self, salt='repr') as caller_stack:
            if caller_stack[-1] in caller_stack[:-1]:
                return '...'
            return self.__repr_str__(' ')

    def __pretty__(
        self,
        fmt: Callable[[Any], Any],
        **kwargs: Any,
    ) -> Generator[Any, None, None]:
        """Provide a human-readable representation of the instance.

        Used by [devtools](https://python-devtools.helpmanual.io/).
        """
        yield self.__repr_name__() + '('
        yield 1
        for name, value in self.__repr_args__():
            if name is not None:
                yield name + '='
            yield fmt(value)
            yield ','
            yield 0
        yield -1
        yield ')'

    def __rich_repr__(self) -> ReprRich:
        """Provide a human-readable representation of the instance.

        Used by [rich](https://rich.readthedocs.io/en/stable/pretty.html).
        """
        for name, field_repr in self.__repr_args__():
            if name is None:
                yield field_repr
            else:
                yield name, field_repr


class PlainRepresentation(str):
    """A plain representation of a string.

    String class where representation doesn't include quotes. Useful with
    `Representation` when you want to return a string representation of an
    object that is valid (or pseudo-valid) python.
    """

    def __repr__(self) -> str:
        return str(self)
