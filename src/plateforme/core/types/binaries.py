# plateforme.core.types.binaries
# ------------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing binary types within the Plateforme
framework leveraging Pydantic schemas for validation and serialization, and
compatibility with SQLAlchemy's data type system.
"""

import typing
from typing import Annotated, Any

from annotated_types import Len

from ..database.types import BinaryEngine
from .base import BaseTypeFactory

__all__ = (
    'BinaryFactory',
    'Binary',
    'StrictBinary',
)


class BinaryFactory(BaseTypeFactory[bytes]):
    """A binary type factory.

    It extends the built-in `bytes` class with additional validation and schema
    methods.
    """

    @classmethod
    def __get_sqlalchemy_data_type__(cls, **kwargs: Any) -> BinaryEngine:
        return BinaryEngine(
            length=kwargs.get('max_length', None),
        )

    def __new__(
        cls,
        *,
        strict: bool | None = None,
        max_length: int | None = None,
    ) -> type[bytes]:
        """Create a new binary type with the given annotations.

        Args:
            strict: Whether to validate the value in strict mode.
                Defaults to ``None``.
            max_length: The maximum length of the binary.
                Defaults to ``None``.

        Returns:
            The binary type with the specified constraints.

        Examples:
            >>> BinaryFactory(max_length=256)
            Annotated[bytes, BinaryFactory, Len(Le(256))]
        """
        return super().__new__(
            cls,
            Len(0, max_length),
            strict=strict,
            force_build=True,
        )


if typing.TYPE_CHECKING:
    Binary = Annotated[bytes, ...]
    """The binary proxy."""

    StrictBinary = Annotated[str, ...]
    """A binary that must be validated strictly."""

else:
    Binary = BinaryFactory()
    StrictBinary = BinaryFactory(strict=True)
