# plateforme.core.types.enums
# ---------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing enum types within the Plateforme
framework leveraging Pydantic schemas for validation and serialization, and
compatibility with SQLAlchemy's data type system.
"""

import enum
import typing
from typing import Annotated, Any

from ..database.types import EnumEngine
from .base import BaseTypeFactory

__all__ = (
    'EnumFactory',
    'Enum',
    'StrictEnum',
)


class EnumFactory(BaseTypeFactory[enum.Enum]):
    """An enum type factory.

    It extends the built-in `enum.Enum` class with additional validation and
    schema methods.
    """

    @classmethod
    def __get_sqlalchemy_data_type__(cls, **kwargs: Any) -> EnumEngine:
        return EnumEngine(
            *kwargs.get('enums', ()),
            create_constraint=kwargs.get('create_constraint', False),
            metadata=kwargs.get('metadata', None),
            name=kwargs.get('name', None),
            native_enum=kwargs.get('native_enum', True),
            length=kwargs.get('length', None),
            schema=kwargs.get('schema', None),
            quote=kwargs.get('quote', False),
            inherit_schema=kwargs.get('inherit_schema', False),
            validate_strings=kwargs.get('validate_strings', False),
            values_callable=kwargs.get('values_callable', None),
            sort_key_function=kwargs.get('sort_key_function', None),
            omit_aliases=kwargs.get('omit_aliases', True),
        )

    def __new__(cls, *args: Any, **kwargs: Any) -> type[enum.Enum]:
        return super().__new__(cls, *args, **kwargs, force_build=True)


if typing.TYPE_CHECKING:
    Enum = Annotated[enum.Enum, ...]
    """The enum proxy."""

    StrictEnum = Annotated[enum.Enum, ...]
    """An enum that must be validated strictly."""

else:
    Enum = EnumFactory()
    StrictEnum = EnumFactory(strict=True)
