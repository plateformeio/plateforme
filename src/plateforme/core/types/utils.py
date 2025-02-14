# plateforme.core.types.utils
# ---------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing types within the Plateforme
framework leveraging Pydantic schemas for validation and serialization, and
compatibility with SQLAlchemy's data type system.
"""

import datetime
import decimal
import enum
import ipaddress
import pathlib
import typing
import uuid
from collections.abc import Iterable
from types import NoneType, UnionType
from typing import Annotated, Any, Literal, Union

from ..database.types import (
    BaseTypeEngine,
    DefaultEngine,
    combine_type_engines,
)
from ..typing import has_forwardref
from .binaries import BinaryFactory
from .datetimes import (
    DateFactory,
    DateTimeFactory,
    TimeDeltaFactory,
    TimeFactory,
)
from .enums import EnumFactory
from .networks import (
    IPvAddressFactory,
    IPvInterfaceFactory,
    IPvNetworkFactory,
)
from .numbers import (
    BooleanFactory,
    DecimalFactory,
    FloatFactory,
    IntegerFactory,
)
from .strings import StringFactory
from .uuid import UuidFactory

__all__ = (
    'resolve_data_type_engine',
)


def resolve_data_type_engine(
    annotation: Any,
    arbitrary_types_allowed: bool = False,
    /,
    **kwargs: Any
) -> BaseTypeEngine[Any]:
    """Resolve the data type engine for the given type annotation.

    Args:
        annotation: The annotation to resolve. If it's not provided, the
            `annotation` keyword argument if present will be used instead.
        arbitrary_types_allowed: Whether to allow arbitrary types. If ``True``,
            the annotation will be resolved to the default data type engine
            when no matching data type engine is found. Else, an error will be
            raised. Defaults to ``False``.
        kwargs: Additional keyword arguments to pass to the type engine. This
            allows to override the default type engine behavior. For example,
            the `length` attribute of the `String` type can be used to set the
            `length` keyword argument of the `StringFactory` type engine.

    Returns:
        The resolved data type engine.
    """
    # Check annotation
    annotation = annotation or kwargs.get('annotation', None)
    if not annotation:
        raise TypeError(
            "Unable to resolve data type engine, the annotation is missing."
        )
    if has_forwardref(annotation):
        raise TypeError(
            f"The annotation {annotation!r} contains forward references. "
            f"Please make sure all forward references are resolved before "
            f"resolving the data type engine."
        )

    # Check for explicit data type engine
    if engine := getattr(annotation, '__get_sqlalchemy_data_type__', None):
        return engine(**kwargs)  # type: ignore

    # Retrieve origin and args
    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)

    # Handle generics
    if origin:
        # Check for union generics and combine type engines
        if origin in (Union, UnionType):
            return combine_type_engines(*(
                resolve_data_type_engine(arg, **kwargs)
                for arg in args
                if arg is not NoneType
            ))

        # Check for annotated generics and extract underlying type and
        # metadata. If annotation type or metadata explicitly defines a data
        # type engine, return it.
        if origin is Annotated:
            annotation_type, *annotation_metadata = args
            for arg in (annotation_type, *annotation_metadata):
                engine = getattr(arg, '__get_sqlalchemy_data_type__', None)
                if engine:
                    return engine(**kwargs)  # type: ignore
            return resolve_data_type_engine(annotation_type, **kwargs)

        # Check for literal generics and combine value type engines
        if origin is Literal:
            def get_value_type(value: Any) -> type:
                return value if isinstance(value, type) else type(value)
            args = tuple(get_value_type(arg) for arg in args)
            return combine_type_engines(*(
                resolve_data_type_engine(arg, **kwargs)
                for arg in args
                if arg is not NoneType
            ))

        # Check for iterable generics (dict, list, set, tuple, etc.)
        if issubclass(origin, Iterable):
            return DefaultEngine

        # Raise error for unsupported generics
        raise TypeError(
            f"Invalid annotation, the generic type {origin!r} is not "
            f"supported. You may want to use a Plateforme built in type "
            f"instead."
        )

    try:
        # Check for uuid annotations
        if issubclass(annotation, uuid.UUID):
            return UuidFactory.__get_sqlalchemy_data_type__(**kwargs)

        # Check for string and enum annotations (enum must be checked first
        # as it can also be a subclass of a string)
        if issubclass(annotation, enum.Enum):
            return EnumFactory.__get_sqlalchemy_data_type__(**kwargs)
        if issubclass(annotation, str):
            return StringFactory.__get_sqlalchemy_data_type__(**kwargs)

        # Check for boolean annotations
        if issubclass(annotation, bool):
            return BooleanFactory.__get_sqlalchemy_data_type__(**kwargs)

        # Check for numeric annotations
        if issubclass(annotation, int):
            return IntegerFactory.__get_sqlalchemy_data_type__(**kwargs)
        if issubclass(annotation, float):
            return FloatFactory.__get_sqlalchemy_data_type__(**kwargs)
        if issubclass(annotation, decimal.Decimal):
            return DecimalFactory.__get_sqlalchemy_data_type__(**kwargs)

        # Check for date annotations
        if issubclass(annotation, datetime.date):
            return DateFactory.__get_sqlalchemy_data_type__(**kwargs)
        if issubclass(annotation, datetime.datetime):
            return DateTimeFactory.__get_sqlalchemy_data_type__(**kwargs)
        if issubclass(annotation, datetime.time):
            return TimeFactory.__get_sqlalchemy_data_type__(**kwargs)
        if issubclass(annotation, datetime.timedelta):
            return TimeDeltaFactory.__get_sqlalchemy_data_type__(**kwargs)

        # Check for ip annotations
        if issubclass(annotation, ipaddress.IPv4Address):
            return IPvAddressFactory.__get_sqlalchemy_data_type__(**kwargs)
        if issubclass(annotation, ipaddress.IPv6Address):
            return IPvAddressFactory.__get_sqlalchemy_data_type__(**kwargs)
        if issubclass(annotation, ipaddress.IPv4Interface):
            return IPvInterfaceFactory.__get_sqlalchemy_data_type__(**kwargs)
        if issubclass(annotation, ipaddress.IPv6Interface):
            return IPvInterfaceFactory.__get_sqlalchemy_data_type__(**kwargs)
        if issubclass(annotation, ipaddress.IPv4Network):
            return IPvNetworkFactory.__get_sqlalchemy_data_type__(**kwargs)
        if issubclass(annotation, ipaddress.IPv6Network):
            return IPvNetworkFactory.__get_sqlalchemy_data_type__(**kwargs)

        # Check for path annotations
        if issubclass(annotation, pathlib.Path):
            return StringFactory.__get_sqlalchemy_data_type__(**kwargs)

        # Check for binary annotations
        if issubclass(annotation, bytes):
            return BinaryFactory.__get_sqlalchemy_data_type__(**kwargs)

    except Exception as error:
        raise TypeError(
            f"Invalid annotation, the type {annotation!r} is not supported. "
            f"You may want to use a Plateforme built in type instead."
        ) from error

    # Handle non matching types
    if not arbitrary_types_allowed:
        raise TypeError(
            f"Invalid annotation, the type {annotation!r} matches neither a "
            f"standard Python concrete type, nor a Plateforme built in type, "
            f"nor a Plateforme valid model. You may want to authorize any "
            f"type by setting the `arbitrary_types_allowed` configuration to "
            f"`True` (not recommended, prefer using built in type instead)."
        )
    return DefaultEngine
