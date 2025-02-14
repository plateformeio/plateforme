# plateforme.core.types.strings
# -----------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing string types within the Plateforme
framework leveraging Pydantic schemas for validation and serialization, and
compatibility with SQLAlchemy's data type system.
"""

import typing
from typing import Annotated, Any

from annotated_types import Len

from ..database.types import StringEngine
from ..representations import Representation
from .base import BaseTypeFactory

__all__ = (
    'StringFactory',
    'String',
    'StrictString',
)


class StringFactory(BaseTypeFactory[str]):
    """A string type factory.

    It extends the built-in `str` class with additional validation and schema
    methods.
    """

    @classmethod
    def __get_sqlalchemy_data_type__(cls, **kwargs: Any) -> StringEngine:
        return StringEngine(
            length=kwargs.get('max_length', None),
            collation=kwargs.get('data_collation', None),
        )

    def __new__(
        cls,
        *,
        strict: bool | None = None,
        strip_whitespace: bool | None = None,
        to_upper: bool | None = None,
        to_lower: bool | None = None,
        min_length: int | None = None,
        max_length: int | None = None,
        pattern: str | None = None,
    ) -> type[str]:
        """Create a new string type with the given annotations.

        Args:
            strict: Whether to validate the value in strict mode.
                Defaults to ``None``.
            strip_whitespace: If True, strip whitespace from the beginning and
                end of the string. Defaults to ``None``.
            to_upper: If True, convert the string to uppercase.
                Defaults to ``None``.
            to_lower: If True, convert the string to lowercase.
                Defaults to ``None``.
            min_length: The minimum length of the string.
                Defaults to ``None``.
            max_length: The maximum length of the string.
                Defaults to ``None``.
            pattern: A regular expression that the string must match.
                Defaults to ``None``.

        Returns:
            The string type with the specified constraints.

        Examples:
            >>> StringFactory(min_length=3)
            Annotated[str, StringFactory, Ge(3)]
        """
        return super().__new__(
            cls,
            Len(min_length or 0, max_length),
            Representation(
                strip_whitespace=strip_whitespace,
                to_upper=to_upper,
                to_lower=to_lower,
                pattern=pattern,
            ),
            strict=strict,
            force_build=True,
        )


if typing.TYPE_CHECKING:
    String = Annotated[str, ...]
    """The string proxy."""

    StrictString = Annotated[str, ...]
    """A string that must be validated strictly."""

else:
    String = StringFactory()
    StrictString = StringFactory(strict=True)
