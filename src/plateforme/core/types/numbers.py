# plateforme.core.types.numbers
# -----------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing number types within the Plateforme
framework leveraging Pydantic schemas for validation and serialization, and
compatibility with SQLAlchemy's data type system.
"""

import decimal
import typing
from typing import Annotated, Any

from annotated_types import Interval, MultipleOf

from ..database.types import BooleanEngine, IntegerEngine, NumericEngine
from ..schema.types import AllowInfNan
from .base import BaseTypeFactory

__all__ = (
    'AllowInfNan',
    # Boolean
    'BooleanFactory',
    'Boolean',
    'StrictBoolean',
    # Decimal
    'DecimalFactory',
    'Decimal',
    'PositiveDecimal',
    'NegativeDecimal',
    'NonPositiveDecimal',
    'NonNegativeDecimal',
    'FiniteDecimal',
    'StrictDecimal',
    # Float
    'FloatFactory',
    'Float',
    'PositiveFloat',
    'NegativeFloat',
    'NonPositiveFloat',
    'NonNegativeFloat',
    'FiniteFloat',
    'StrictFloat',
    # Integer
    'IntegerFactory',
    'Integer',
    'PositiveInteger',
    'NegativeInteger',
    'NonPositiveInteger',
    'NonNegativeInteger',
    'StrictInteger',
)


# MARK: Boolean

class BooleanFactory(BaseTypeFactory[bool]):
    """A boolean type factory.

    It extends the built-in `bool` class with additional validation and schema
    methods.
    """

    @classmethod
    def __get_sqlalchemy_data_type__(cls, **kwargs: Any) -> BooleanEngine:
        return BooleanEngine(
            create_constraint=kwargs.get('create_constraint', False),
            name=kwargs.get('name', None),
        )

    def __new__(cls, *args: Any, **kwargs: Any) -> type[bool]:
        return super().__new__(cls, *args, **kwargs, force_build=True)


if typing.TYPE_CHECKING:
    Boolean = Annotated[bool, ...]
    """The boolean proxy."""

    StrictBoolean = Annotated[bool, ...]
    """A boolean that must be strict."""

else:
    Boolean = BooleanFactory()
    StrictBoolean = BooleanFactory(strict=True)


# MARK: Decimal

class DecimalFactory(BaseTypeFactory[decimal.Decimal]):
    """A decimal type factory.

    It extends the built-in `decimal.Decimal` class with additional validation
    and schema methods.
    """

    @classmethod
    def __get_sqlalchemy_data_type__(
        cls, **kwargs: Any
    ) -> NumericEngine[decimal.Decimal]:
        return NumericEngine(
            precision=kwargs.get('max_digits', None),
            scale=kwargs.get('decimal_places', None),
            asdecimal=True,
        )

    def __new__(
        cls,
        *,
        strict: bool | None = None,
        gt: int | None = None,
        ge: int | None = None,
        lt: int | None = None,
        le: int | None = None,
        multiple_of: int | None = None,
        allow_inf_nan: bool | None = None,
    ) -> type[decimal.Decimal]:
        """Create a new decimal type with the given annotations.

        Args:
            strict: Whether to validate the value in strict mode.
                Defaults to ``None``.
            gt: The value must be greater than this value.
                Defaults to ``None``.
            ge: The value must be greater than or equal to this value.
                Defaults to ``None``.
            lt: The value must be less than this value.
                Defaults to ``None``.
            le: The value must be less than or equal to this value.
                Defaults to ``None``.
            multiple_of: The value must be a multiple of this value.
                Defaults to ``None``.
            allow_inf_nan: Whether to allow infinity and NaN.

        Returns:
            The decimal type with the specified constraints.

        Examples:
            >>> DecimalFactory(multiple_of=3)
            Annotated[decimal.Decimal, DecimalFactory, MultipleOf(3)]
        """
        return super().__new__(
            cls,
            Interval(gt=gt, ge=ge, lt=lt, le=le),
            MultipleOf(multiple_of) if multiple_of is not None else None,
            AllowInfNan(allow_inf_nan) if allow_inf_nan is not None else None,
            strict=strict,
            force_build=True,
        )


if typing.TYPE_CHECKING:
    Decimal = Annotated[decimal.Decimal, ...]
    """The decimal proxy."""

    PositiveDecimal = Annotated[decimal.Decimal, ...]
    """A decimal that must be positive."""

    NegativeDecimal = Annotated[decimal.Decimal, ...]
    """A decimal that must be negative."""

    NonPositiveDecimal = Annotated[decimal.Decimal, ...]
    """A decimal that must be non-positive."""

    NonNegativeDecimal = Annotated[decimal.Decimal, ...]
    """A decimal that must be non-negative."""

    FiniteDecimal = Annotated[decimal.Decimal, ...]
    """A decimal that must be finite."""

    StrictDecimal = Annotated[decimal.Decimal, ...]
    """A decimal that must be strict."""

else:
    Decimal = DecimalFactory()
    PositiveDecimal = DecimalFactory(gt=0)
    NegativeDecimal = DecimalFactory(lt=0)
    NonPositiveDecimal = DecimalFactory(le=0)
    NonNegativeDecimal = DecimalFactory(ge=0)
    FiniteDecimal = DecimalFactory(allow_inf_nan=False)
    StrictDecimal = DecimalFactory(strict=True)


# MARK: Float

class FloatFactory(BaseTypeFactory[float]):
    """A float type factory.

    It extends the built-in `float` class with additional validation and schema
    methods.
    """

    @classmethod
    def __get_sqlalchemy_data_type__(
        cls, **kwargs: Any
    ) -> NumericEngine[float]:
        return NumericEngine(
            precision=kwargs.get('max_digits', None),
            scale=kwargs.get('decimal_places', None),
            asdecimal=False,
        )

    def __new__(
        cls,
        *,
        strict: bool | None = None,
        gt: int | None = None,
        ge: int | None = None,
        lt: int | None = None,
        le: int | None = None,
        multiple_of: int | None = None,
        allow_inf_nan: bool | None = None,
    ) -> type[float]:
        """Create a new float type with the given annotations.

        Args:
            strict: Whether to validate the value in strict mode.
                Defaults to ``None``.
            gt: The value must be greater than this value.
                Defaults to ``None``.
            ge: The value must be greater than or equal to this value.
                Defaults to ``None``.
            lt: The value must be less than this value.
                Defaults to ``None``.
            le: The value must be less than or equal to this value.
                Defaults to ``None``.
            multiple_of: The value must be a multiple of this value.
                Defaults to ``None``.
            allow_inf_nan: Whether to allow infinity and NaN.
                Defaults to ``None``.

        Returns:
            The float type with the specified constraints.

        Examples:
            >>> FloatFactory(gt=0, le=10)
            Annotated[float, FloatFactory, Interval(gt=0, le=10)]
        """
        return super().__new__(
            cls,
            Interval(gt=gt, ge=ge, lt=lt, le=le),
            MultipleOf(multiple_of) if multiple_of is not None else None,
            AllowInfNan(allow_inf_nan) if allow_inf_nan is not None else None,
            strict=strict,
            force_build=True,
        )


if typing.TYPE_CHECKING:
    Float = Annotated[float, ...]
    """The float proxy."""

    PositiveFloat = Annotated[float, ...]
    """A float that must be positive."""

    NegativeFloat = Annotated[float, ...]
    """A float that must be negative."""

    NonPositiveFloat = Annotated[float, ...]
    """A float that must be non-positive."""

    NonNegativeFloat = Annotated[float, ...]
    """A float that must be non-negative."""

    FiniteFloat = Annotated[float, ...]
    """A float that must be finite."""

    StrictFloat = Annotated[float, ...]
    """A float that must be strict."""

else:
    Float = FloatFactory()
    PositiveFloat = FloatFactory(gt=0)
    NegativeFloat = FloatFactory(lt=0)
    NonPositiveFloat = FloatFactory(le=0)
    NonNegativeFloat = FloatFactory(ge=0)
    FiniteFloat = FloatFactory(allow_inf_nan=False)
    StrictFloat = FloatFactory(strict=True)


# MARK: Integer

class IntegerFactory(BaseTypeFactory[int]):
    """An integer type factory.

    It extends the built-in `int` class with additional validation and schema
    methods.
    """

    @classmethod
    def __get_sqlalchemy_data_type__(cls, **kwargs: Any) -> IntegerEngine:
        return IntegerEngine()

    def __new__(
        cls,
        *,
        strict: bool | None = None,
        gt: int | None = None,
        ge: int | None = None,
        lt: int | None = None,
        le: int | None = None,
        multiple_of: int | None = None,
    ) -> type[int]:
        """Create a new integer type with the given annotations.

        Args:
            strict: Whether to validate the value in strict mode.
                Defaults to ``None``.
            gt: The value must be greater than this value.
                Defaults to ``None``.
            ge: The value must be greater than or equal to this value.
                Defaults to ``None``.
            lt: The value must be less than this value.
                Defaults to ``None``.
            le: The value must be less than or equal to this value.
                Defaults to ``None``.
            multiple_of: The value must be a multiple of this value.
                Defaults to ``None``.

        Returns:
            The integer type with the specified constraints.

        Examples:
            >>> IntegerFactory(gt=0)
            Annotated[int, IntegerFactory, Interval(gt=0)]
        """
        return super().__new__(
            cls,
            Interval(gt=gt, ge=ge, lt=lt, le=le),
            MultipleOf(multiple_of) if multiple_of is not None else None,
            strict=strict,
            force_build=True,
        )


if typing.TYPE_CHECKING:
    Integer = Annotated[int, ...]
    """The integer proxy."""

    PositiveInteger = Annotated[int, ...]
    """An integer that must be positive."""

    NegativeInteger = Annotated[int, ...]
    """An integer that must be negative."""

    NonPositiveInteger = Annotated[int, ...]
    """An integer that must be non-positive."""

    NonNegativeInteger = Annotated[int, ...]
    """An integer that must be non-negative."""

    StrictInteger = Annotated[int, ...]
    """An integer that must be strict."""

else:
    Integer = IntegerFactory()
    PositiveInteger = IntegerFactory(gt=0)
    NegativeInteger = IntegerFactory(lt=0)
    NonPositiveInteger = IntegerFactory(le=0)
    NonNegativeInteger = IntegerFactory(ge=0)
    StrictInteger = IntegerFactory(strict=True)
