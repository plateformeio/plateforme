# plateforme.core.loaders
# -----------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing loaders used in settings within the
Plateforme framework.
"""

import typing
from typing import Any, Generic, Type, TypeVar

from .modules import import_object
from .representations import ReprArgs, Representation
from .schema import core as core_schema
from .schema.core import (
    CoreSchema,
    GetCoreSchemaHandler,
    GetJsonSchemaHandler,
    SerializationInfo,
)
from .schema.json import JsonSchemaDict
from .schema.types import TypeAdapter

_T = TypeVar('_T', bound=Any)

__all__ = (
    'Loader',
    'LoaderInfo',
)


class LoaderInfo(Representation):
    """Information about a loader.

    This class is used to store information about an object that is loaded
    using a fullname. It is used to serialize and deserialize the object.

    Attributes:
        name: The fullname of the object.
        static: Whether the object was loaded statically.
    """

    def __init__(self, name: str, *, static: bool = True) -> None:
        """Initialize the loader information."""
        self.name = name
        self.static = static

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source: Any,
        __handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        # Build json schema
        json_schema = core_schema.no_info_after_validator_function(
            source,
            core_schema.str_schema(),
        )

        # Build python schema
        python_schema= core_schema.union_schema(
            [
                core_schema.is_instance_schema(source),
                json_schema,
            ],
            strict=True,
            custom_error_type='string_type',
        )

        return core_schema.json_or_python_schema(
            json_schema,
            python_schema,
            serialization=core_schema.plain_serializer_function_ser_schema(
                str,
                info_arg=True,
                return_schema=core_schema.str_schema(),
                when_used='json',
            ),
        )

    def __repr_args__(self) -> ReprArgs:
        yield (None, self.name)
        if self.static is False:
            yield ('static', self.static)


class Loader(Generic[_T]):
    """A loader for objects.

    This class is used to load objects from a fullname. It is used to serialize
    and deserialize the object.

    Attributes:
        type_: The type of the object to load.
    """

    type_: type[_T]

    def __init__(self, type_: type[_T] = object) -> None:  # type: ignore
        """Initialize the loader."""
        self.type_ = type_

    def __get_pydantic_core_schema__(
        self,
        __source: Any,
        __handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        loader_info = TypeAdapter(LoaderInfo)

        def validator(strict: bool) -> Any:
            def validate(obj: Any) -> _T:
                return self.validate(obj, strict=strict)
            return validate

        lax_schema = core_schema.no_info_after_validator_function(
            validator(strict=False),
            core_schema.any_schema(),
        )

        strict_schema = core_schema.no_info_after_validator_function(
            validator(strict=True),
            loader_info.core_schema,
        )

        return core_schema.lax_or_strict_schema(
            lax_schema=lax_schema,
            strict_schema=strict_schema,
            serialization=core_schema.plain_serializer_function_ser_schema(
                self.serialize,
                info_arg=True,
            ),
        )

    def __get_pydantic_json_schema__(
        self,
        core_schema: CoreSchema,
        handler: GetJsonSchemaHandler,
    ) -> JsonSchemaDict:
        schema = handler(core_schema)
        return schema

    def serialize(
        self,
        obj: _T,
        info: SerializationInfo | None = None,
    ) -> LoaderInfo | str:
        """Serialize the loaded object."""
        if info and info.mode == 'python':
            return obj
        if loader := getattr(obj, '__config_loader__', None):
            assert isinstance(loader, LoaderInfo)
            return loader.name

        raise ValueError(
            f"Cannot serialize object {obj!r} in JSON mode without a loader "
            f"information."
        )

    def validate(
        self,
        obj: Any,
        *,
        strict: bool | None = None,
    ) -> _T:
        """Validate and load an object."""
        # Load object
        if isinstance(obj, (LoaderInfo, str)):
            loader = LoaderInfo(str(obj))
            instance = import_object(loader.name)
            if instance is self.type_:
                instance = instance()
            object.__setattr__(instance, '__config_loader__', loader)
        elif strict:
            raise ValueError(
                f"Cannot load object {obj!r} without a loader information."
            )
        else:
            instance = obj

        # Validate object instance
        if not self.validate_instance(instance, strict=strict):
            raise ValueError(
                f"Loaded object {instance!r} is not an instance of "
                f"{self.type_!r}."
            )
        return instance  # type: ignore[no-any-return]

    def validate_instance(
        self,
        obj: Any,
        *,
        strict: bool | None = None,
    ) -> bool:
        """Validate an object instance against the loader type."""
        origin = typing.get_origin(self.type_)
        if origin is None:
            return isinstance(obj, self.type_)
        if origin in (type, Type):
            args = typing.get_args(self.type_)
            return issubclass(obj, args[0])

        try:
            return isinstance(obj, origin)
        except TypeError:
            if strict:
                return False
        return True
