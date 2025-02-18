# plateforme.core.schema.core
# ---------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing core schema within the Plateforme
framework. It extends Pydantic's core schema features.
"""

import dataclasses
import typing
from contextlib import contextmanager
from enum import IntEnum
from typing import Iterator, Literal

from pydantic.annotated_handlers import (
    GetCoreSchemaHandler,
    GetJsonSchemaHandler,
)
from pydantic_core import (
    PydanticOmit,
    PydanticUseDefault,
    SchemaError,
    SchemaSerializer,
    SchemaValidator,
    Some,
    ValidationError,
)

from ..context import RECURSION_CONTEXT, VALIDATION_CONTEXT

if typing.TYPE_CHECKING:
    from pydantic_core.core_schema import (
        AfterValidatorFunctionSchema,
        AnySchema,
        ArgumentsSchema,
        BeforeValidatorFunctionSchema,
        BoolSchema,
        BytesSchema,
        CallableSchema,
        CallSchema,
        ChainSchema,
        CoreConfig,
        CoreSchema,
        DataclassSchema,
        DateSchema,
        DatetimeSchema,
        DecimalSchema,
        DefinitionsSchema,
        DictSchema,
        FloatSchema,
        FormatSerSchema,
        FrozenSetSchema,
        GeneratorSchema,
        IntSchema,
        JsonSchema,
        ListSchema,
        LiteralSchema,
        ModelSchema,
        ModelSerSchema,
        NoneSchema,
        NullableSchema,
        PlainSerializerFunctionSerSchema,
        PlainValidatorFunctionSchema,
        SerializationInfo,
        SerializerFunctionWrapHandler,
        SetSchema,
        SimpleSerSchema,
        StringSchema,
        TimedeltaSchema,
        TimeSchema,
        ToStringSerSchema,
        TypedDictSchema,
        UnionSchema,
        UuidSchema,
        ValidationInfo,
        ValidatorFunctionWrapHandler,
        WrapSerializerFunctionSerSchema,
        WrapValidatorFunctionSchema,
        any_schema,
        arguments_parameter,
        arguments_schema,
        bool_schema,
        bytes_schema,
        call_schema,
        callable_schema,
        chain_schema,
        computed_field,
        custom_error_schema,
        dataclass_args_schema,
        dataclass_field,
        dataclass_schema,
        date_schema,
        datetime_schema,
        decimal_schema,
        definition_reference_schema,
        definitions_schema,
        dict_schema,
        float_schema,
        format_ser_schema,
        frozenset_schema,
        generator_schema,
        int_schema,
        is_instance_schema,
        is_subclass_schema,
        json_or_python_schema,
        json_schema,
        lax_or_strict_schema,
        list_schema,
        literal_schema,
        model_field,
        model_fields_schema,
        model_schema,
        model_ser_schema,
        multi_host_url_schema,
        no_info_after_validator_function,
        no_info_before_validator_function,
        no_info_plain_validator_function,
        no_info_wrap_validator_function,
        none_schema,
        nullable_schema,
        plain_serializer_function_ser_schema,
        set_schema,
        simple_ser_schema,
        str_schema,
        tagged_union_schema,
        time_schema,
        timedelta_schema,
        to_string_ser_schema,
        tuple_positional_schema,
        tuple_schema,
        tuple_variable_schema,
        typed_dict_field,
        typed_dict_schema,
        union_schema,
        url_schema,
        uuid_schema,
        with_default_schema,
        with_info_after_validator_function,
        with_info_before_validator_function,
        with_info_plain_validator_function,
        with_info_wrap_validator_function,
        wrap_serializer_function_ser_schema,
    )

__all__ = (
    'GetCoreSchemaHandler',
    'GetJsonSchemaHandler',
    # Core schema
    'AfterValidatorFunctionSchema',
    'AnySchema',
    'ArgumentsSchema',
    'BeforeValidatorFunctionSchema',
    'BoolSchema',
    'BytesSchema',
    'CallableSchema',
    'CallSchema',
    'ChainSchema',
    'CoreConfig',
    'CoreSchema',
    'DataclassSchema',
    'DateSchema',
    'DatetimeSchema',
    'DecimalSchema',
    'DefinitionsSchema',
    'DictSchema',
    'FloatSchema',
    'FormatSerSchema',
    'FrozenSetSchema',
    'GeneratorSchema',
    'IntSchema',
    'JsonSchema',
    'ListSchema',
    'LiteralSchema',
    'ModelSchema',
    'ModelSerSchema',
    'NoneSchema',
    'NullableSchema',
    'PlainSerializerFunctionSerSchema',
    'PlainValidatorFunctionSchema',
    'PydanticOmit',
    'PydanticUseDefault',
    'SchemaError',
    'SchemaSerializer',
    'SchemaValidator',
    'SerializationInfo',
    'SerializerFunctionWrapHandler',
    'SetSchema',
    'SimpleSerSchema',
    'Some',
    'StringSchema',
    'TimedeltaSchema',
    'TimeSchema',
    'ToStringSerSchema',
    'TypedDictSchema',
    'UnionSchema',
    'UuidSchema',
    'ValidationError',
    'ValidationInfo',
    'ValidatorFunctionWrapHandler',
    'WrapSerializerFunctionSerSchema',
    'WrapValidatorFunctionSchema',
    'any_schema',
    'arguments_parameter',
    'arguments_schema',
    'bool_schema',
    'bytes_schema',
    'call_schema',
    'callable_schema',
    'chain_schema',
    'computed_field',
    'custom_error_schema',
    'dataclass_args_schema',
    'dataclass_field',
    'dataclass_schema',
    'date_schema',
    'datetime_schema',
    'decimal_schema',
    'definition_reference_schema',
    'definitions_schema',
    'dict_schema',
    'float_schema',
    'format_ser_schema',
    'frozenset_schema',
    'generator_schema',
    'int_schema',
    'is_instance_schema',
    'is_subclass_schema',
    'json_or_python_schema',
    'json_schema',
    'lax_or_strict_schema',
    'list_schema',
    'literal_schema',
    'model_field',
    'model_fields_schema',
    'model_schema',
    'model_ser_schema',
    'multi_host_url_schema',
    'no_info_after_validator_function',
    'no_info_before_validator_function',
    'no_info_plain_validator_function',
    'no_info_wrap_validator_function',
    'none_schema',
    'nullable_schema',
    'plain_serializer_function_ser_schema',
    'set_schema',
    'simple_ser_schema',
    'str_schema',
    'tagged_union_schema',
    'time_schema',
    'timedelta_schema',
    'to_string_ser_schema',
    'tuple_positional_schema',
    'tuple_schema',
    'tuple_variable_schema',
    'typed_dict_field',
    'typed_dict_schema',
    'union_schema',
    'url_schema',
    'uuid_schema',
    'with_default_schema',
    'with_info_after_validator_function',
    'with_info_before_validator_function',
    'with_info_plain_validator_function',
    'with_info_wrap_validator_function',
    'wrap_serializer_function_ser_schema',
    # Utilities
    'RecursionState'
    'ValidationMode',
    'has_recursion_error',
    'recursion_manager',
    'validation_manager',
)


def __dir__() -> list[str]:
    return list(__all__)


def __getattr__(name: str) -> object:
    from importlib import import_module

    module = import_module('pydantic_core.core_schema')
    return getattr(module, name)


# MARK: Utilities

class ValidationMode(IntEnum):
    """An enumeration of schema validation modes."""

    DISABLED = 0
    """The validation is disabled."""

    DEFAULT = 1
    """The validation is enabled."""

    STRICT = 2
    """The validation is strictly enforced."""


@dataclasses.dataclass(frozen=True, slots=True)
class RecursionState:
    """A data class to represent the recursion context state for validation.

    This class is used to store the recursion state for validation. It contains
    the set of recursive guard values and the mode for handling recursion
    errors.

    Attributes:
        state: The recursive guard frozen set values that are used to prevent
            infinite recursion. It initializes as an empty set.
        mode: The mode for handling recursion errors. It can be either
            ``'raise'`` to raise a validation error or ``'omit'`` to skip the
            validation and omit the source value. Defaults to ``'omit'``.
    """
    state: frozenset[str]
    mode: Literal['lax', 'omit', 'raise']


def has_recursion_error(error: ValidationError) -> bool:
    """Check if the given validation error is a recursion loop error."""
    errors = error.errors()
    return errors[0]['type'] == 'recursion_loop'


@typing.overload
@contextmanager
def recursion_manager(
    value: str | None = None,
    *,
    mode: Literal['lax', 'omit', 'raise'] | None = None,
    new: Literal[False] = False,
    on_missing: Literal['skip'],
) -> Iterator[RecursionState | None]:
    ...

@typing.overload
@contextmanager
def recursion_manager(
    value: str | None = None,
    *,
    mode: Literal['lax', 'omit', 'raise'] | None = None,
    new: bool = False,
    on_missing: Literal['create', 'raise'] = 'create',
) -> Iterator[RecursionState]:
    ...

@contextmanager
def recursion_manager(
    value: str | None = None,
    *,
    mode: Literal['lax', 'omit', 'raise'] | None = None,
    new: bool = False,
    on_missing: Literal['create', 'raise', 'skip'] = 'create',
) -> Iterator[RecursionState | None]:
    """A recursion context manager for validation.

    Args:
        value: The value to add to the recursion context. If set to ``None``,
            the recursion context is not modified when available.
            Defaults to ``None``.
        mode: The mode for handling recursion errors. It can be either:
            - ``'lax'``: Validate leniently the source value even when a
                recursion loop is detected, and omit only for recursion
                validation errors, i.e. when the same instance is visited
                twice.
            - ``'omit'``: Skip the validation and omit the source value.
            - ``'raise'``: Raise a validation error when a recursion loop is
                detected, or when the same instance is visited twice.
            When set to ``None``, the current mode found in recursion context
            is used, otherwise it falls back to ``'omit'``.
            Defaults to ``None``.
        new: Whether to initialize a new recursion context or not. If set to
            ``True``, a new recursion context is created. If set to ``False``,
            the current recursion context is used if available, otherwise it
            follows the `on_missing` behavior. Defaults to ``False``.
        on_missing: The behavior to follow when no current recursion context is
            available, either to create a new recursion context, raise an
            error, or skip the operation. Defaults to ``'create'``.

    Raises:
        PydanticOmit: Either if the recursion mode is set to ``'omit'`` and a
            recursion loop is detected or a recursion validation error occurs,
            or if the recursion mode is set to ``'lax'`` and a recursion
            validation error occurs.
        RecursionError: If the recursion mode is set to ``'raise'`` and a
            recursion loop is detected or a validation error occurs, i.e. when
            the same instance is visited twice.
        RuntimeError: If the recursion context is not set when required.
    """
    context = RECURSION_CONTEXT.get()

    # Resolve recursion context
    if new is False:
        context = RECURSION_CONTEXT.get()
        if context is not None:
            recursive_state = context.state
            recursive_mode = mode or context.mode
        elif on_missing == 'raise':
            raise RuntimeError(
                "No recursion available in the current context where creating "
                "a new recursion context is not allowed `on_missing='raise'`."
            )
        elif on_missing == 'skip':
            yield None
            return

    if new is True or context is None:
        recursive_state = frozenset()
        recursive_mode = mode or 'omit'

    # Helper function to handle recursion error
    def handle_error(source: ValidationError | None = None) -> None:
        if recursive_mode == 'omit':
            raise PydanticOmit
        elif recursive_mode == 'lax':
            if source is None:
                return
            raise PydanticOmit
        raise RecursionError(
            f"Recursion loop detected for field {value!r} within the "
            f"recursion context: {recursive_state}."
        ) from source

    # Update recursion context
    if value is not None:
        if value in recursive_state:
            handle_error()
        else:
            recursive_state = recursive_state | {value}

    recursion = RecursionState(recursive_state, recursive_mode)

    # Yield and reset recursion context
    token = RECURSION_CONTEXT.set(recursion)
    try:
        yield recursion
    except ValidationError as error:
        if has_recursion_error(error):
            handle_error(error)
        raise error
    finally:
        RECURSION_CONTEXT.reset(token)


@contextmanager
def validation_manager(
    *, mode: Literal['disabled', 'default', 'strict'] | None = None
) -> Iterator[ValidationMode]:
    """A context manager for validation and partial initialization.

    If the validation mode is not specified, either the current validation mode
    is set to ``'default'`` if no validation context is available, or the
    current validation mode is used. The validation mode is reset to the
    previous state after the context manager exits.

    Args:
        mode: The validation mode to set the context to. It can be either one
            of the following options:
            - ``None``: The validation mode is set to the current context mode
                if available, otherwise it falls back to ``'default'``.
            - ``'disabled'``: The validation is disabled.
            - ``'default'``: The validation is enabled.
            - ``'strict'``: The validation is strictly enforced.
            Defaults to ``None``.

    Raises:
        ValueError: If an invalid validation mode is provided.
    """
    context = VALIDATION_CONTEXT.get()

    # Set validation mode
    if mode is None:
        if context is not None:
            validation = context
        validation = ValidationMode.DEFAULT
    elif mode == 'disabled':
        validation = ValidationMode.DISABLED
    elif mode == 'default':
        validation = ValidationMode.DEFAULT
    elif mode == 'strict':
        validation = ValidationMode.STRICT
    else:
        raise ValueError(
            f"Invalid validation mode {mode!r} provided. Must be one of: "
            f"'disabled', 'default', or 'strict'."
        )

    # Yield and reset validation context
    token = VALIDATION_CONTEXT.set(validation)
    try:
        yield validation
    finally:
        VALIDATION_CONTEXT.reset(token)
