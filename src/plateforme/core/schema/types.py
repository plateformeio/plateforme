# plateforme.core.schema.types
# ----------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing schema types within the Plateforme
framework using Pydantic features.
"""

import dataclasses
import typing
from collections.abc import Iterable
from typing import Any, Generic, Literal, TypeVar

from pydantic.config import ConfigDict as PydanticConfigDict
from pydantic.networks import (
    IPvAnyAddress as PydanticIPvAnyAddress,
    IPvAnyInterface as PydanticIPvAnyInterface,
    IPvAnyNetwork as PydanticIPvAnyNetwork,
    UrlConstraints,
)
from pydantic.type_adapter import TypeAdapter
from pydantic.types import (
    AllowInfNan,
    AwareDatetime as PydanticAwareDateTime,
    Discriminator,
    FutureDate as PydanticFutureDate,
    FutureDatetime as PydanticFutureDateTime,
    NaiveDatetime as PydanticNaiveDateTime,
    PastDate as PydanticPastDate,
    PastDatetime as PydanticPastDateTime,
    PathType,
    Strict,
    Tag,
    UuidVersion,
)
from pydantic_core import (
    MultiHostUrl as PydanticMultiHostUrl,
    Url as PydanticUrl,
)

from ..expressions import IncEx
from . import core as core_schema
from .core import CoreSchema, GetCoreSchemaHandler, Some
from .json import (
    DEFAULT_REF_TEMPLATE,
    GenerateJsonSchema,
    JsonSchemaKeyT,
    JsonSchemaMode,
    JsonSchemaValue,
)

_T = TypeVar('_T', bound=object)

__all__ = (
    'AllowInfNan',
    'Discriminator',
    'OneOrMany',
    'PathType',
    'PydanticAwareDateTime',
    'PydanticConfigDict',
    'PydanticFutureDate',
    'PydanticFutureDateTime',
    'PydanticNaiveDateTime',
    'PydanticPastDate',
    'PydanticPastDateTime',
    'PydanticIPvAnyAddress',
    'PydanticIPvAnyInterface',
    'PydanticIPvAnyNetwork',
    'PydanticMultiHostUrl',
    'PydanticUrl',
    'Schema',
    'Strict',
    'Tag',
    'TypeAdapter',
    'TypeAdapterList',
    'UrlConstraints',
    'UuidVersion',
)


@dataclasses.dataclass(frozen=True, slots=True)
class Schema:
    """Representation of the model schema argument for annotations."""
    model: str

    def __hash__(self) -> int:
        return hash(self.model)

    def __repr__(self) -> str:
        return f'Schema({self.model!r})'


class OneOrMany(list[_T], Generic[_T]):
    """A class for representing a single value or a sequence of values."""

    @classmethod
    def validate(
        cls,
        obj: _T | list[_T] | set[_T] | tuple[_T],
    ) -> 'OneOrMany[_T]':
        """Validate the one or many given object.

        Args:
            obj: The input object to handle either as a single entry or a
                sequence of entries. If the object is a list, set, or tuple, it
                will be used as is. Otherwise, it will be wrapped in a list.

        Returns:
            The validated one or many object.
        """
        if isinstance(obj, (list, set, tuple)):
            return cls(obj)
        else:
            return cls([obj])

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        __source: type['OneOrMany[Any]'],
        __handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        # Retrieve type arguments from the source type
        args = typing.get_args(__source)
        if len(args) != 1:
            raise TypeError(
                f"Cannot generate core schema for {cls!r} without one type "
                f"argument. Got: {__source!r}."
            )

        # Generate schema for the item type
        item_schema = __handler.generate_schema(args[0])

        return core_schema.no_info_before_validator_function(
            cls.validate,
            core_schema.list_schema(item_schema)
        )


@typing.final
class TypeAdapterList(Generic[_T]):
    """A list type adapter for handling one or many input values.

    The type adapters provide a flexible way to perform validation and
    serialization based on a Python type. It proxies the `TypeAdapter` class
    with a list type checking mechanism that allows for a single value or a
    sequence of values.

    Attributes:
        core_schema: The core schema for the type.
        validator: The schema validator for the type.
        serializer: The schema serializer for the type.

    Note:
        `TypeAdapterList` instances are not types, and cannot be used as type
        annotations for fields.
    """
    if typing.TYPE_CHECKING:
        __pydantic_adapter__: TypeAdapter[_T]

    @typing.overload
    def __init__(
        self,
        type_: type[_T],
        *,
        config: PydanticConfigDict | None = None,
        _parent_depth: int = 2,
        module: str | None = None,
    ) -> None:
        ...

    @typing.overload
    def __init__(  # pyright: ignore[reportOverlappingOverload]
        self,
        type_: _T,
        *,
        config: PydanticConfigDict | None = None,
        _parent_depth: int = 2,
        module: str | None = None,
    ) -> None:
        ...

    def __init__(
        self,
        type_: type[_T] | _T,
        *,
        config: PydanticConfigDict | None = None,
        _parent_depth: int = 2,
        module: str | None = None,
    ) -> None:
        """Initialize a list type adapter.

        Args:
            type_: The type associated with the adapter.
            config: The configuration to use for the adapter.
            _parent_depth: The depth at which to search the parent
                namespace to construct the local namespace.
            module: The module that passes to plugin if provided.

        Returns:
            A type adapter configured for the specified `type`.
        """
        self.__pydantic_adapter__ = TypeAdapter(
            OneOrMany[type_],  # type: ignore
            config=config,
            _parent_depth=_parent_depth,
            module=module,
        )

    def validate_python(  # type: ignore[empty-body, unused-ignore]
        self,
        __object: Any,
        *,
        strict: bool | None = None,
        from_attributes: bool | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[_T]:
        """Validate a Python object against the model.

        Args:
            __object: The Python object to validate against the model.
            strict: Whether to strictly check types.
            from_attributes: Whether to extract data from object attributes.
            context: Additional context to pass to the validator.

        Returns:
            The validated object.

        Note:
            When using `TypeAdapterList` with a Pydantic `dataclass`, the use
            of the `from_attributes` argument is not supported.
        """

    def validate_json(  # type: ignore[empty-body, unused-ignore]
        self,
        __data: str | bytes,
        *,
        strict: bool | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[_T]:
        """Validate a JSON string or bytes against the model.

        Args:
            __data: The JSON data to validate against the model.
            strict: Whether to strictly check types.
            context: Additional context to use during validation.

        Returns:
            The validated object.
        """

    def validate_strings(  # type: ignore[empty-body, unused-ignore]
        self,
        __object: Any,
        *,
        strict: bool | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[_T]:
        """Validate object contains string data against the model.

        Args:
            __object: The object contains string data to validate.
            strict: Whether to strictly check types.
            context: Additional context to use during validation.

        Returns:
            The validated object.
        """

    def get_default_value(  # type: ignore[empty-body, unused-ignore]
        self,
        *,
        strict: bool | None = None,
        context: dict[str, Any] | None = None,
    ) -> Some[list[_T]] | None:
        """Get the default value for the wrapped type.

        Args:
            strict: Whether to strictly check types.
            context: Additional context to pass to the validator.

        Returns:
            The default value wrapped in a `Some` if there is one or ``None``
            if not.
        """

    def dump_python(  # type: ignore[empty-body, unused-ignore]
        self,
        __instances: _T | list[_T],
        *,
        mode: Literal['json', 'python'] = 'python',
        include: IncEx | None = None,
        exclude: IncEx | None = None,
        by_alias: bool = False,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        round_trip: bool = False,
        warnings: bool = True,
    ) -> Any:
        """Dump an instance of the adapted type to a Python object.

        Args:
            __instances: The Python object to serialize.
            mode: The output format.
            include: Fields to include in the output.
            exclude: Fields to exclude from the output.
            by_alias: Whether to use alias names for field names.
            exclude_unset: Whether to exclude unset fields.
            exclude_defaults: Whether to exclude fields with default values.
            exclude_none: Whether to exclude fields with ``None`` values.
            round_trip: Whether to output the serialized data in a way that is
                compatible with deserialization.
            warnings: Whether to display serialization warnings.

        Returns:
            The serialized object.
        """

    def dump_json(  # type: ignore[empty-body, unused-ignore]
        self,
        __instance: _T | list[_T],
        *,
        indent: int | None = None,
        include: IncEx | None = None,
        exclude: IncEx | None = None,
        by_alias: bool = False,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        round_trip: bool = False,
        warnings: bool = True,
    ) -> bytes:
        """Serialize an instance of the adapted type to JSON.

        Args:
            __instance: The instance to be serialized.
            indent: Number of spaces for JSON indentation.
            include: Fields to include.
            exclude: Fields to exclude.
            by_alias: Whether to use alias names for field names.
            exclude_unset: Whether to exclude unset fields.
            exclude_defaults: Whether to exclude fields with default values.
            exclude_none: Whether to exclude fields with a value of ``None``.
            round_trip: Whether to serialize and deserialize the instance to
                ensure round-tripping.
            warnings: Whether to emit serialization warnings.

        Returns:
            The JSON representation of the given instance as bytes.
        """

    def json_schema(  # type: ignore[empty-body, unused-ignore]
        self,
        *,
        by_alias: bool = True,
        ref_template: str = DEFAULT_REF_TEMPLATE,
        schema_generator: type[GenerateJsonSchema] = GenerateJsonSchema,
        mode: JsonSchemaMode = 'validation',
    ) -> dict[str, Any]:
        """Generate a JSON schema for the adapted type.

        Args:
            by_alias: Whether to use alias names for field names.
            ref_template: The format string used for generating $ref strings.
            schema_generator: The generator class used for creating the schema.
            mode: The mode to use for schema generation.

        Returns:
            The JSON schema for the model as a dictionary.
        """

    @staticmethod
    def json_schemas(  # type: ignore[empty-body, unused-ignore]
        __inputs: Iterable[
            tuple[JsonSchemaKeyT, JsonSchemaMode, TypeAdapter[Any]]
        ],
        *,
        by_alias: bool = True,
        title: str | None = None,
        description: str | None = None,
        ref_template: str = DEFAULT_REF_TEMPLATE,
        schema_generator: type[GenerateJsonSchema] = GenerateJsonSchema,
    ) -> tuple[
        dict[tuple[JsonSchemaKeyT, JsonSchemaMode], JsonSchemaValue],
        JsonSchemaValue,
    ]:
        """Generate a JSON schema from multiple type adapters.

        Args:
            __inputs: Inputs to schema generation. The first two items will
                form the keys of the (first) output mapping; the type adapters
                will provide the core schemas that get converted into
                definitions in the output JSON schema.
            by_alias: Whether to use alias names.
            title: The title for the schema.
            description: The description for the schema.
            ref_template: The format string used for generating $ref strings.
            schema_generator: The generator class used for creating the schema.

        Returns:
            A tuple where:
            - The first element is a dictionary whose keys are tuples of JSON
                schema key type and JSON mode, and whose values are the JSON
                schema corresponding to that pair of inputs. (These schemas may
                have JsonRef references to definitions that are defined in the
                second returned element).
            - The second element is a JSON schema containing all definitions
                referenced in the first returned element, along with the
                optional title and description keys.
        """

    def __getattribute__(self, name: str) -> Any:
        if name == '__pydantic_adapter__':
            return object.__getattribute__(self, name)
        return getattr(self.__pydantic_adapter__, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name == '__pydantic_adapter__':
            object.__setattr__(self, name, value)
            return
        setattr(self.__pydantic_adapter__, name, value)

    def __delattr__(self, name: str) -> None:
        if name == '__pydantic_adapter__':
            object.__delattr__(self, name)
            return
        delattr(self.__pydantic_adapter__, name)
