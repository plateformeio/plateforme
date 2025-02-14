# plateforme.core.types.json
# --------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing JSON type within the Plateforme
framework leveraging Pydantic schemas for validation and serialization, and
compatibility with SQLAlchemy's data type system.
"""

import typing
from typing import Annotated, Any, TypeVar

from ..database.types import JsonEngine
from ..schema import core as core_schema
from ..schema.core import CoreSchema, GetCoreSchemaHandler
from .base import BaseType

_T = TypeVar('_T')

__all__ = (
    'Json',
)


if typing.TYPE_CHECKING:
    Json = Annotated[_T, ...]
    """A type alias for the JSON data type."""

else:
    class Json(BaseType):
        """A special type wrapper which loads JSON before parsing.

        The `Json` data type makes Pydantic first load a raw JSON string before
        validating the loaded data into the parametrized type:

        When the model is dumped using `model_dump` or `model_dump_json`, the
        dumped value will be the result of validation, not the original JSON
        string. However, the argument `round_trip=True` can be used to get the
        original JSON string back.
        """

        @classmethod
        def __class_getitem__(cls, item: _T) -> _T:
            return Annotated[item, cls()]

        @classmethod
        def __get_pydantic_core_schema__(
            cls,
            source: Any,
            handler: GetCoreSchemaHandler
        ) -> CoreSchema:
            if cls is source:
                return core_schema.json_schema(None)
            else:
                return core_schema.json_schema(handler(source))

        @classmethod
        def __get_sqlalchemy_data_type__(cls, **kwargs: Any) -> JsonEngine:
            return JsonEngine(
                none_as_null=kwargs.get('data_none_as_null', True),
            )

        def __repr__(self) -> str:
            return 'Json'

        def __hash__(self) -> int:
            return hash(type(self))

        def __eq__(self, other: Any) -> bool:
            return type(other) == type(self)
