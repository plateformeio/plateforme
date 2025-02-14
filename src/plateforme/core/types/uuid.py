# plateforme.core.types.uuid
# --------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing UUID types within the Plateforme
framework leveraging Pydantic schemas for validation and serialization, and
compatibility with SQLAlchemy's data type system.
"""

import typing
import uuid
from typing import Annotated, Any, Literal

from ..database.types import UuidEngine
from ..schema.types import UuidVersion
from .base import BaseTypeFactory

__all__ = (
    'UuidFactory',
    'UuidVersion',
    'UUID',
    'UUID1',
    'UUID3',
    'UUID4',
    'UUID5',
)


class UuidFactory(BaseTypeFactory[uuid.UUID]):
    """An UUID type factory.

    It extends the built-in `uuid.UUID` class with additional validation and
    schema methods.
    """

    @classmethod
    def __get_sqlalchemy_data_type__(cls, **kwargs: Any) -> UuidEngine[Any]:
        return UuidEngine(
            as_uuid=kwargs.get('as_uuid', True),
            native_uuid=kwargs.get('native_uuid', True),
        )

    def __new__(
        cls,
        version: Literal[1, 3, 4, 5] | None = None,
    ) -> type[uuid.UUID]:
        """Create a new UUID type with version validation.

        Args:
            version: The UUID version to validate against.
                Defaults to ``None``.

        Returns:
            The UUID type with the specified version.

        Examples:
            >>> UuidFactory(version=3)
            Annotated[uuid.UUID, UuidFactory, UuidVersion(3)]
        """
        if version is None:
            return super().__new__(cls, force_build=True)
        return super().__new__(
            cls,
            UuidVersion(version),
            force_build=True,
        )


if typing.TYPE_CHECKING:
    UUID = Annotated[uuid.UUID, ...]
    """The UUID proxy."""

    UUID1 = Annotated[uuid.UUID, ...]
    """A UUID that must be of version 1."""

    UUID3 = Annotated[uuid.UUID, ...]
    """A UUID that must be of version 3."""

    UUID4 = Annotated[uuid.UUID, ...]
    """A UUID that must be of version 4."""

    UUID5 = Annotated[uuid.UUID, ...]
    """A UUID that must be of version 5."""

else:
    UUID = UuidFactory()
    UUID1 = UuidFactory(version=1)
    UUID3 = UuidFactory(version=3)
    UUID4 = UuidFactory(version=4)
    UUID5 = UuidFactory(version=5)
