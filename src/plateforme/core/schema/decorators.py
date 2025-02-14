# plateforme.core.schema.decorators
# ---------------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing schema decorators within the
Plateforme framework using Pydantic features.
"""

from typing import Any, Literal

from pydantic.functional_serializers import (
    PlainSerializer,
    SerializeAsAny,
    WrapSerializer,
    field_serializer,
    model_serializer,
)
from pydantic.functional_validators import (
    AfterValidator,
    BeforeValidator,
    InstanceOf,
    PlainValidator,
    SkipValidation,
    WrapValidator,
    field_validator,
    model_validator,
)
from pydantic.validate_call_decorator import validate_call

from ..typing import is_model
from . import core as core_schema
from .core import (
    CoreSchema,
    GetCoreSchemaHandler,
    ValidatorFunctionWrapHandler,
    recursion_manager,
)

__all__ = (
    'RecursiveGuard',
    # Serializers
    'PlainSerializer',
    'SerializeAsAny',
    'WrapSerializer',
    'field_serializer',
    'model_serializer',
    # Validators
    'AfterValidator',
    'BeforeValidator',
    'InstanceOf',
    'PlainValidator',
    'SkipValidation',
    'WrapValidator',
    'field_validator',
    'model_validator',
    'validate_call',
)


class RecursiveGuard:
    """A recursive guard for schema validation in model field annotations."""

    def __init__(
        self,
        value: str | None = None,
        *,
        mode: Literal['lax', 'omit', 'raise'] = 'raise',
    ) -> None:
        """Initialize the recursive guard.

        Args:
            value: The value to add to the recursion context. If set to
                ``None``, the recursion context is not modified when available.
                Defaults to ``None``.
            mode: The mode for handling recursion errors. It can be either:
                - ``'lax'``: Validate leniently the source value even when a
                    recursion loop is detected, and omit only for recursion
                    validation errors, i.e. when the same instance is visited
                    twice.
                - ``'omit'``: Skip the validation and omit the source value.
                - ``'raise'``: Raise a validation error when a recursion loop
                    is detected, or when the same instance is visited twice.
                Defaults to ``'raise'``.
        """
        self.value = value
        self.mode = mode

    def __get_pydantic_core_schema__(
        self,
        __source: Any,
        __handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        if not is_model(__source):
            raise TypeError(
                f"Cannot generate core schema with recursive guard without a "
                f"valid model. Got: {__source!r}."
            )

        def validate(
            obj: Any, handler: ValidatorFunctionWrapHandler,
        ) -> Any:
            with recursion_manager(self.value, mode=self.mode):
                return handler(obj)

        return core_schema.no_info_wrap_validator_function(
            validate,
            __handler(__source),
        )
