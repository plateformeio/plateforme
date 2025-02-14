# plateforme.core.types.datetimes
# -------------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing datetime types within the
Plateforme framework leveraging Pydantic schemas for validation and
serialization, and compatibility with SQLAlchemy's data type system.
"""

import datetime
import typing
from typing import Annotated, Any, Literal

from annotated_types import Interval

from ..database.types import (
    DateEngine,
    DateTimeEngine,
    IntervalEngine,
    TimeEngine,
)
from ..schema.types import (
    PydanticAwareDateTime,
    PydanticFutureDate,
    PydanticFutureDateTime,
    PydanticNaiveDateTime,
    PydanticPastDate,
    PydanticPastDateTime,
)
from .base import BaseTypeFactory

__all__ = (
    # Date
    'DateFactory',
    'Date',
    'PastDate',
    'FutureDate',
    'StrictDate',
    # DateTime
    'DateTimeFactory',
    'DateTime',
    'PastDateTime',
    'FutureDateTime',
    'AwareDateTime',
    'NaiveDateTime',
    'StrictDateTime',
    # Time
    'TimeFactory',
    'Time',
    'StrictTime',
    # TimeDelta
    'TimeDeltaFactory',
    'TimeDelta',
    'StrictTimeDelta',
)


# MARK: Date

class DateFactory(BaseTypeFactory[datetime.date]):
    """A date type factory.

    It extends the built-in `datetime.date` class with additional validation
    and schema methods.
    """

    @classmethod
    def __get_sqlalchemy_data_type__(cls, **kwargs: Any) -> DateEngine:
        return DateEngine()

    def __new__(
        cls,
        *,
        strict: bool | None = None,
        gt: int | None = None,
        ge: int | None = None,
        lt: int | None = None,
        le: int | None = None,
        timeframe: Literal['past', 'future'] | None = None,
    ) -> type[datetime.date]:
        """Create a new date type with the given annotations.

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
            timeframe: The time frame to validate the date value against.
                Defaults to ``None``.

        Returns:
            The date type with the specified constraints.

        Examples:
            >>> DateFactory(
            ...     gt=datetime.date(2021, 1, 1),
            ...     le=datetime.date(2021, 12, 31),
            ... )
            Annotated[
                datetime.date,
                DateFactory,
                Interval(
                    gt=datetime.date(2021, 1, 1),
                    le=datetime.date(2021, 12, 31),
                )
            ]
        """
        return super().__new__(
            cls,
            Interval(gt=gt, ge=ge, lt=lt, le=le),
            PydanticPastDate if timeframe == 'past' else None,
            PydanticFutureDate if timeframe == 'future' else None,
            strict=strict,
            force_build=True,
        )


if typing.TYPE_CHECKING:
    Date = Annotated[datetime.date, ...]
    """The date proxy."""

    PastDate = Annotated[datetime.date, ...]
    """A date that must be in the past."""

    FutureDate = Annotated[datetime.date, ...]
    """A date that must be in the future."""

    StrictDate = Annotated[datetime.date, ...]
    """A date that must be validated strictly."""

else:
    Date = DateFactory()
    PastDate = DateFactory(timeframe='past')
    FutureDate = DateFactory(timeframe='future')
    StrictDate = DateFactory(strict=True)


# MARK: DateTime

class DateTimeFactory(BaseTypeFactory[datetime.datetime]):
    """A date time type factory.

    It extends the built-in `datetime.datetime` class with additional
    validation and schema methods.
    """

    @classmethod
    def __get_sqlalchemy_data_type__(cls, **kwargs: Any) -> DateTimeEngine:
        return DateTimeEngine(
            timezone=kwargs.get('timezone', False),
        )

    def __new__(
        cls,
        *,
        strict: bool | None = None,
        gt: int | None = None,
        ge: int | None = None,
        lt: int | None = None,
        le: int | None = None,
        timeframe: Literal['past', 'future'] | None = None,
        timezone: bool | None = None,
    ) -> type[datetime.datetime]:
        """Create a new date time type with the given annotations.

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
            timeframe: The time frame to validate the date time value against.
                Defaults to ``None``.
            timezone: Whether to validate the value as timezone aware.
                Defaults to ``None``.

        Returns:
            The date time type with the specified constraints.

        Examples:
            >>> DateTimeFactory(timezone=True)
            Annotated[datetime.datetime, DateTimeFactory, TimezoneAware]
        """
        return super().__new__(
            cls,
            Interval(gt=gt, ge=ge, lt=lt, le=le),
            PydanticPastDateTime if timeframe == 'past' else None,
            PydanticFutureDateTime if timeframe == 'future' else None,
            PydanticAwareDateTime if timezone is True else None,
            PydanticNaiveDateTime if timezone is False else None,
            strict=strict,
            force_build=True,
        )


if typing.TYPE_CHECKING:
    DateTime = Annotated[datetime.datetime, ...]
    """The date time proxy."""

    PastDateTime = Annotated[datetime.datetime, ...]
    """A date time that must be in the past."""

    FutureDateTime = Annotated[datetime.datetime, ...]
    """A date time that must be in the future."""

    AwareDateTime = Annotated[datetime.datetime, ...]
    """A date time that must be timezone aware."""

    NaiveDateTime = Annotated[datetime.datetime, ...]
    """A date time that must be timezone naive."""

    StrictDateTime = Annotated[datetime.datetime, ...]
    """A date time that must be validated strictly."""

else:
    DateTime = DateTimeFactory()
    PastDateTime = DateTimeFactory(timeframe='past')
    FutureDateTime = DateTimeFactory(timeframe='future')
    AwareDateTime = DateTimeFactory(timezone=True)
    NaiveDateTime = DateTimeFactory(timezone=False)
    StrictDateTime = DateTimeFactory(strict=True)


# MARK: Time

class TimeFactory(BaseTypeFactory[datetime.time]):
    """A time type factory.

    It extends the built-in `datetime.time` class with additional validation
    and schema methods.
    """

    @classmethod
    def __get_sqlalchemy_data_type__(cls, **kwargs: Any) -> TimeEngine:
        return TimeEngine()

    def __new__(
        cls,
        *,
        strict: bool | None = None,
        gt: int | None = None,
        ge: int | None = None,
        lt: int | None = None,
        le: int | None = None,
    ) -> type[datetime.time]:
        """Create a new time type with the given annotations.

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

        Returns:
            The time type with the specified constraints.

        Examples:
            >>> TimeFactory(
            ...     gt=datetime.time(0, 0, 0),
            ...     le=datetime.time(11, 59, 59),
            ... )
            Annotated[
                datetime.time,
                TimeFactory,
                Interval(gt=datetime.time(0, 0, 0), le=datetime.time(11, 59, 59)),
            ]
        """
        return super().__new__(
            cls,
            Interval(gt=gt, ge=ge, lt=lt, le=le),
            strict=strict,
            force_build=True,
        )


if typing.TYPE_CHECKING:
    Time = Annotated[datetime.time, ...]
    """The time proxy."""

    StrictTime = Annotated[datetime.time, ...]
    """A time that must be validated strictly."""

else:
    Time = TimeFactory()
    StrictTime = TimeFactory(strict=True)


# MARK: TimeDelta

class TimeDeltaFactory(BaseTypeFactory[datetime.timedelta]):
    """A time delta type factory.

    It extends the built-in `datetime.timedelta` class with additional
    validation and schema methods.
    """

    @classmethod
    def __get_sqlalchemy_data_type__(cls, **kwargs: Any) -> IntervalEngine:
        return IntervalEngine(
            native=kwargs.get('native', True),
            second_precision=kwargs.get('second_precision', None),
            day_precision=kwargs.get('day_precision', None),
        )

    def __new__(cls, *args: Any, **kwargs: Any) -> type[datetime.timedelta]:
        return super().__new__(cls, *args, **kwargs, force_build=True)


if typing.TYPE_CHECKING:
    TimeDelta = Annotated[datetime.timedelta, ...]
    """The time delta proxy."""

    StrictTimeDelta = Annotated[datetime.timedelta, ...]
    """A time delta that must be validated strictly."""

else:
    TimeDelta = TimeDeltaFactory()
    StrictTimeDelta = TimeDeltaFactory(strict=True)
