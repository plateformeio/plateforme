# plateforme.core.types.paths
# ---------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing path types within the Plateforme
framework leveraging Pydantic schemas for validation and serialization, and
compatibility with SQLAlchemy's data type system.
"""

import pathlib
import typing
from typing import Annotated, Any, Literal

from ..database.types import StringEngine
from ..schema.types import PathType
from .base import BaseTypeFactory

__all__ = (
    'AnyPath',
    'DirectoryPath',
    'FilePath',
    'NewPath',
    'PathFactory',
    'PathType',
)


class PathFactory(BaseTypeFactory[pathlib.Path]):
    """A path type factory.

    It extends the built-in `pathlib.Path` class with additional validation and
    schema methods.
    """

    @classmethod
    def __get_sqlalchemy_data_type__(cls, **kwargs: Any) -> StringEngine:
        return StringEngine(
            length=kwargs.get('max_length', None),
            collation=kwargs.get('data_collation', None),
        )

    def __new__(
        cls,
        path_type: Literal['dir', 'file', 'new'] | None = None,
    ) -> type[pathlib.Path]:
        """Create a new path type with either file or directory validation.

        Args:
            path_type: The path type to validate against.
                Defaults to ``None``.

        Returns:
            The path type with the specified validation.

        Examples:
            >>> PathFactory(path_type='file')
            Annotated[Path, PathFactory, PathType('file')]
        """
        if path_type is None:
            return super().__new__(cls, force_build=True)
        return super().__new__(
            cls,
            PathType(path_type),
            force_build=True,
        )


if typing.TYPE_CHECKING:
    AnyPath = Annotated[pathlib.Path, ...]
    """The path proxy."""

    DirectoryPath = Annotated[pathlib.Path, ...]
    """A path that must point to a directory."""

    FilePath = Annotated[pathlib.Path, ...]
    """A path that must point to a file."""

    NewPath = Annotated[pathlib.Path, ...]
    """A path for a new file or directory that must not already exist."""

else:
    AnyPath = PathFactory()
    DirectoryPath = PathFactory(path_type='dir')
    FilePath = PathFactory(path_type='file')
    NewPath = PathFactory(path_type='new')
