# plateforme.core.database.types
# ------------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing database types within the
Plateforme framework using SQLAlchemy features.
"""

import datetime
import decimal
import enum
import inspect
import json
import pickle
import typing
import uuid
from abc import ABCMeta, abstractmethod
from collections.abc import Sequence
from typing import Any, Callable, Dict, Literal, Tuple, Type, TypeVar, Union

from sqlalchemy.sql.operators import OperatorType as _OperatorType
from sqlalchemy.sql.type_api import to_instance as _to_instance
from sqlalchemy.types import (
    # Concrete
    ARRAY as _ARRAY,
    BIGINT as _BIGINT,
    BINARY as _BINARY,
    BLOB as _BLOB,
    BOOLEAN as _BOOLEAN,
    CHAR as _CHAR,
    CLOB as _CLOB,
    DATE as _DATE,
    DATETIME as _DATETIME,
    DECIMAL as _DECIMAL,
    DOUBLE as _DOUBLE,
    DOUBLE_PRECISION as _DOUBLE_PRECISION,
    FLOAT as _FLOAT,
    INTEGER as _INTEGER,
    JSON as _JSON,
    NCHAR as _NCHAR,
    NUMERIC as _NUMERIC,
    NVARCHAR as _NVARCHAR,
    REAL as _REAL,
    SMALLINT as _SMALLINT,
    TEXT as _TEXT,
    TIME as _TIME,
    TIMESTAMP as _TIMESTAMP,
    UUID as _UUID,
    VARBINARY as _VARBINARY,
    VARCHAR as _VARCHAR,
    # Engine
    Boolean as _Boolean,
    Date as _Date,
    DateTime as _DateTime,
    Enum as _Enum,
    Integer as _Integer,
    Interval as _Interval,
    LargeBinary as _LargeBinary,
    Numeric as _Numeric,
    String as _String,
    Text as _Text,
    Time as _Time,
    TypeDecorator as _TypeDecorator,
    TypeEngine as _TypeEngine,
    Unicode as _Unicode,
    UnicodeText as _UnicodeText,
    Uuid as _Uuid,
    _Binary,
)
from typing_extensions import TypedDict

from .engines import Dialect
from .orm import Mutable
from .schema import MetaData

_T = TypeVar('_T', bound=Any)
_TEngine = Union[Type['BaseTypeEngine[_T]'], 'BaseTypeEngine[_T]']
_TNumber = TypeVar('_TNumber', bound=(float | decimal.Decimal))
_TUuid = TypeVar('_TUuid', str, uuid.UUID)

__all__ = (
    # Base
    'BaseTypeEngine',
    'TypeEngineMeta',
    'TypeEnginePayload',
    'TypeEngine',
    'TypeEngineRules',
    # Concrete
    'ARRAY',
    'BIGINT',
    'BINARY',
    'BLOB',
    'BOOLEAN',
    'CHAR',
    'CLOB',
    'DATE',
    'DATETIME',
    'DECIMAL',
    'DOUBLE',
    'DOUBLE_PRECISION',
    'FLOAT',
    'INTEGER',
    'JSON',
    'NCHAR',
    'NUMERIC',
    'NVARCHAR',
    'REAL',
    'SMALLINT',
    'TEXT',
    'TIME',
    'TIMESTAMP',
    'UUID',
    'VARBINARY',
    'VARCHAR',
    # Engine
    'BinaryEngine',
    'BooleanEngine',
    'DateEngine',
    'DateTimeEngine',
    'DefaultEngine',
    'EnumEngine',
    'IntegerEngine',
    'IntervalEngine',
    'JsonEngine',
    'NumericEngine',
    'StringEngine',
    'TimeEngine',
    'UuidEngine',
    'combine_type_engines',
)


TypeEngine = Union[Type['BaseTypeEngine[Any]'], 'BaseTypeEngine[Any]']
"""A type alias for a type engine."""


TypeEngineRules = Dict[str, Callable[[Tuple[Any, Any]], Any]]
"""A type alias for the rules used to merge payloads"""


class TypeEnginePayload(TypedDict, total=True):
    """A typed dictionary used to store the arguments passed to a type engine.

    Attributes:
        engine: The type engine.
        arguments: The arguments passed to the type engine (``args`` and
            ``kwargs``).
    """
    engine: type['BaseTypeEngine[Any]']
    arguments: dict[str, Any]


class TypeEngineMeta(ABCMeta):
    """The type engine metaclass.

    The metaclass used to create a new type engines, while keeping track of the
    the parent and new type engine payloads arguments and keyword arguments
    implementations cascade.

    Attributes:
        payloads: A list of `TypeEnginePayload` instances used to determine the
            order in which the parent and new type engines are called, along
            with the arguments passed to each type engine.
        rules: A dictionary containing corresponding rules for merging payloads
            from two different instances of the new type engine.
    """

    def __new__(
        mcls,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        **kwargs: Any,
    ) -> type:
        """Create a new type engine class."""
        # Create the new type engine class
        cls = super().__new__(
            mcls, name, bases, namespace, **kwargs
        )

        # Return if the new type engine class is abstract
        if inspect.isabstract(cls):
            return cls

        # Check if rules is implemented and is a dictionary
        rules = getattr(cls, 'rules', None)
        if rules is None or not callable(rules):
            raise ValueError(
                "Type engine must have a `rules` dictionary."
            )
        rules = rules()
        if not isinstance(rules, dict):
            raise ValueError(
                "Type engine must have a `rules` dictionary."
            )

        # Check that all parameters from the "__init__" method signature have a
        # rule assigned to them (except for "cls", "mcls", and "self").
        init = namespace.get('__init__', None)
        if init is not None:
            signature = inspect.signature(init)
            parameters = [
                param_name
                for param_name in signature.parameters.keys()
                if param_name not in ('cls', 'mcls', 'self')
            ]
            for parameter in parameters:
                if parameter not in rules:
                    raise ValueError(
                        f"Missing rule for initialization parameter: "
                        f"{parameter}."
                    )

        # Update the "__init__" method payload
        def init_and_store_payload(
            self: BaseTypeEngine[Any],
            *args: Any,
            **kwargs: Any,
        ) -> None:
            if init is not None:
                signature = inspect.signature(init).bind(self, *args, **kwargs)
                signature.apply_defaults()
                self.payloads.append(TypeEnginePayload(
                    engine=cls,  # type: ignore
                    arguments={
                        key: value
                        for key, value in signature.arguments.items()
                        if key not in ('cls', 'mcls', 'self')
                    }
                ))
                init(self, *args, **kwargs)

        # Return the new type engine class
        setattr(cls, '__init__', init_and_store_payload)
        setattr(cls, 'payloads', list[TypeEnginePayload]())
        return cls


class BaseTypeEngine(_TypeDecorator[_T], metaclass=TypeEngineMeta):
    """The base type engine.

    Allows the creation of type engines which add additional functionality to
    an existing type.

    This method is preferred to direct subclassing of Plateforme's built-in
    type engines as it ensures that all required functionality of the
    underlying type is kept in place:

    Examples:
        >>> from plateforme.database import BaseTypeEngine, StringEngine
        >>> class MyTypeEngine(BaseTypeEngine):
        ...     '''
        ...     Prefixes Unicode values with on the way in and
        ...     strips it off on the way out.
        ...     '''
        ...     impl = StringEngine
        ...     cache_ok = True

        ...     @staticmethod
        ...     def rules():
        ...         return {length: lambda x: min(x[0], x[1])}

        ...     def coarse_type_engine(self):
        ...         return BinaryEngine()

    The `impl` class-level attribute is required, and can reference any
    `BaseTypeEngine` class. Alternatively, the `load_dialect_impl` method can
    be used to provide different type classes based on the dialect given; in
    this case, the `impl` variable can reference `BaseTypeEngine` as a
    placeholder.

    The `cache_ok` class-level flag indicates if this custom `BaseTypeEngine`
    is safe to be used as part of a cache key. This flag defaults to ``None``
    which will initially generate a warning when the SQL compiler attempts to
    generate a cache key for a statement that uses this type. If the
    `BaseTypeEngine` is not guaranteed to produce the same bind/result behavior
    and SQL generation every time, this flag should be set to ``False``;
    otherwise if the class produces the same behavior each time, it may be set
    to ``True``.

    The `rules` static-level method is required, and must return a dictionary
    of rules for merging payloads from two different instances of the new type
    engine. The keys of the dictionary are the names of the parameters passed
    to the `__init__` method, while the values are functions that take one
    tuple of two elements as arguments and return the merged value.

    The `coarse_type_engine` instance-level method is optional, and can be
    utilized to generate a more generalized representation of the current type
    engine class. This method proves particularly beneficial during the lookup
    process employed for merging type engines into a shared, coarser type
    engine.

    Types that receive a Python type that isn't similar to the ultimate type
    used may want to define the `coerce_compared_value` method. This is used to
    give the expression system a hint when coercing Python objects into bind
    parameters within expressions. Consider this expression:

    Examples:
        >>> mytable.c.somecol + datetime.date(2009, 5, 15)

    Above, if ``somecol`` is an ``Integer`` variant, it makes sense that we're
    doing date arithmetic, where above is usually interpreted by databases as
    adding a number of days to the given date. The expression system does the
    right thing by not attempting to coerce the ``date()`` value into an
    integer-oriented bind parameter.

    However, in the case of `BaseTypeEngine`, we are usually changing an
    incoming Python type to something new; `BaseTypeEngine` by default will
    coerce the non-typed side to be the same type as itself. Such as below, we
    define an ``epoch`` type that stores a date value as an integer:

    Examples:
        >>> from plateforme.database import BaseTypeEngine, IntegerEngine
        >>> class MyEpochTypeEngine(BaseTypeEngine):
        ...     impl = IntegerEngine
        ...     epoch = datetime.date(1970, 1, 1)

        ...     def process_bind_param(self, value, dialect):
        ...         return (value - self.epoch).days
        ...     def process_result_value(self, value, dialect):
        ...         return self.epoch + timedelta(days=value)

        ...     def copy(self, **kwargs):
        ...         return MyEpochTypeEngine()

    Our expression of ``somecol + date`` with the above type will coerce the
    ``date`` on the right side to also be treated as `MyEpochTypeEngine`.

    This behavior can be overridden via the `coerce_compared_value` method,
    which returns a type that should be used for the value of the expression.
    Below we set it such that an integer value will be treated as an
    `IntegerEngine`, and any other value is assumed to be a date and will be
    treated as a `MyEpochTypeEngine`:

    Examples:
        >>> def coerce_compared_value(self, op, value):
        ...     if isinstance(value, int):
        ...         return IntegerEngine()
        ...     else:
        ...         return self

    The behavior of `coerce_compared_value` is not inherited by default from
    that of the base type. If the `BaseTypeEngine` is augmenting a type that
    requires special logic for certain types of operators, this method must be
    overridden. A key example is when decorating the `JSON` and `JSONB` types;
    the default rules of `coerce_compared_value` method should be used in order
    to deal with operators like index operations:

    Examples:
        >>> from plateforme.database import BaseTypeEngine, JSON
        >>> class MyJsonTypeEngine(BaseTypeEngine):
        ...     impl = JSON
        ...     cache_ok = True

        ...     def coerce_compared_value(self, op, value):
        ...         return self.impl.coerce_compared_value(op, value)

    Without the above step, index operations such as ``mycol['foo']`` will
    cause the index value ``'foo'`` to be JSON encoded. Similarly, when working
    with the `ARRAY` datatype, the type coercion for index operations (e.g.
    ``mycol[5]``) is also handled by `coerce_compared_value` method, where
    again a simple override is sufficient unless special rules are needed for
    particular operators:

    Examples:
        >>> from plateforme.database import BaseTypeEngine, ARRAY
        >>> class MyArrayTypeEngine(BaseTypeEngine):
        ...     impl = ARRAY
        ...     cache_ok = True

        ...     def coerce_compared_value(self, op, value):
        ...         return self.impl.coerce_compared_value(op, value)
    """
    if typing.TYPE_CHECKING:
        impl: type[_TypeEngine[Any]]
        payloads: list[TypeEnginePayload]

    def __init__(self, *args: Any, **kwargs: Any):
        """Construct a type engine.

        Arguments sent here are passed to the constructor of the class assigned
        to the `impl` class level attribute, assuming the `impl` is a callable,
        and the resulting object is assigned to the ``self.impl`` instance
        attribute (thus overriding the class attribute of the same name).

        If the class level `impl` is not a callable (the unusual case), it will
        be assigned to the same instance attribute "as-is", ignoring those
        arguments passed to the constructor.

        Subclasses can override this to customize the generation of
        ``self.impl`` entirely.
        """
        super().__init__(*args, **kwargs)

    @staticmethod
    @abstractmethod
    def rules() -> TypeEngineRules:
        """The rules for merging payloads from two different type engines.

        Return a dictionary containing the selection rules for all the
        parameters that can be passed to the constructor of the type engine.

        Each key of the dictionary is the name of a parameter and the value is
        a callable that takes the values of a tuple of two type engines as
        arguments and should return the most conservative value between the
        two.
        """
        # Implement custom logic to decide how to merge payloads...
        ...

    @abstractmethod
    def coarse_type_engine(
        self, /, **kwargs: Any
    ) -> 'BaseTypeEngine[Any] | None':
        """Construct a coarser type engine.

        Return a coarser `BaseTypeEngine` object that is especially used to
        resolve the most granular common type between two type engines.

        Args:
            kwargs: Additional keyword arguments to pass for handling the
                construction of the coarser type engine.

        Returns:
            A coarser `BaseTypeEngine` object.
        """
        # Implement custom logic to construct a coarser type engine...
        ...


class BinaryEngine(BaseTypeEngine[bytes]):
    """A binary engine.

    The `BinaryEngine` corresponds to a large and/or unlengthed binary type for
    the target platform, such as ``BLOB`` on MySQL and ``BYTEA`` for
    PostgreSQL. It also handles the necessary conversions for the DBAPI.
    """
    impl: type[_Binary] = _LargeBinary
    cache_ok = True

    def __init__(self, length: int | None = None):
        """Construct a binary engine.

        Args:
            length: A length for the column for use in DDL statements, for
                those binary types that accept a length, such as the MySQL
                ``BLOB`` type.
        """
        super().__init__(length)

    @staticmethod
    def rules() -> TypeEngineRules:
        return {
            'length': lambda x: max(
                (i for i in x if i is not None),
                default=None,
            ),
        }

    def coarse_type_engine(self, /, **kwargs: Any) -> None:
        return None

    def coerce_compared_value(
        self, op: _OperatorType | None, value: Any
    ) -> Any:
        return self.impl.coerce_compared_value(op, value)  # type: ignore


class BooleanEngine(BaseTypeEngine[bool]):
    """A boolean engine.

    A boolean engine which typically uses `BOOLEAN` or `SMALLINT` on the DDL
    side, and on the Python side deals in ``True`` or ``False``.

    The `BooleanEngine` currently has two levels of assertion that the values
    persisted are simple true/false values. For all backends, only the Python
    values ``None``, ``True``, ``False``, ``1`` or ``0`` are accepted as
    parameter values. For those backends that don't support a "native boolean"
    datatype, an option exists to also create a ``CHECK`` constraint on the
    target column.
    """
    impl: type[_Boolean] = _Boolean
    cache_ok = True

    def __init__(
        self,
        create_constraint: bool = False,
        name: str | None = None,
    ) -> None:
        """Construct a boolean engine.

        Args:
            create_constraint: If the boolean is generated as an `INT` or
                `SMALLINT`, also create a ``CHECK`` constraint on the table
                that ensures ``1`` or ``0`` as a value.
            name: If a ``CHECK`` constraint is generated, specify the name of
                the constraint.
        """
        super().__init__(create_constraint, name)

    @staticmethod
    def rules() -> TypeEngineRules:
        return {
            'create_constraint': lambda x: any(x),
            'name': lambda x: x[0] or x[1],
        }

    def coarse_type_engine(self, /, **kwargs: Any) -> BaseTypeEngine[Any]:
        return JsonEngine()


class DateEngine(BaseTypeEngine[datetime.date]):
    """A date engine.

    The `DateEngine` returns objects from the Python `datetime.date`.
    """
    impl: type[_Date] = _Date
    cache_ok = True

    def __init__(self) -> None:
        """Construct a date engine."""
        super().__init__()

    @staticmethod
    def rules() -> TypeEngineRules:
        return {}

    def coarse_type_engine(self, /, **kwargs: Any) -> BaseTypeEngine[Any]:
        return DateTimeEngine()


class DateTimeEngine(BaseTypeEngine[datetime.datetime]):
    """A datetime engine.

    The `DateTimeEngine` returns objects from the Python `datetime` module.
    Most DBAPIs have built in support for the datetime module, with the noted
    exception of SQLite. In the case of SQLite, date and time types are stored
    as strings which are then converted back to datetime objects when rows are
    returned.

    For the time representation within the datetime type, some backends include
    additional options, such as timezone support and fractional seconds
    support.
    """
    impl: type[_DateTime] = _DateTime
    cache_ok = True

    def __init__(self, timezone: bool = False) -> None:
        """Construct a datetime engine.

        Args:
            timezone: Indicates that the datetime type should enable timezone
                support, if available on the base date/time-holding type only.
        """
        super().__init__(timezone)

    @staticmethod
    def rules() -> TypeEngineRules:
        return {'timezone': lambda x: any(x)}

    def coarse_type_engine(self, /, **kwargs: Any) -> BaseTypeEngine[Any]:
        return JsonEngine()


class EnumEngine(BaseTypeEngine[str | enum.Enum]):
    """An enumeration engine.

    The `EnumEngine` provides a set of possible string values which the column
    is constrained towards. It will make use of the backend's native
    enumeration type if one is available; otherwise, it uses a `VARCHAR`
    datatype. An option also exists to automatically produce a ``CHECK``
    constraint when the `VARCHAR` (so called "non-native") variant is produced;
    see the ``create_constraint`` flag.

    It also provides in-Python validation of string values during both read and
    write operations. When reading a value from the database in a result set,
    the string value is always checked against the list of possible values and
    a `LookupError` is raised if no match is found. When passing a value to the
    database as a plain string within a SQL statement, if the
    `validate_strings` parameter is set to ``True``, a `LookupError` is raised
    for any string value that's not located in the given list of possible
    values; note that this impacts usage of ``LIKE`` expressions with
    enumerated values (an unusual use case).

    When using an enumerated class, the enumerated objects are used both for
    input and output, rather than strings as is the case with a plain-string
    enumerated type:

    Examples:
        >>> import enum
        >>> from plateforme.database import EnumEngine
        >>> class MyEnum(enum.Enum):
        ...     one = 1
        ...     two = 2
        ...     three = 3
        >>> t = Table('data', MetaData(), Column('value', EnumEngine(MyEnum)))
        >>> connection.execute(t.insert(), {'value': MyEnum.two})
        >>> assert connection.scalar(t.select()) is MyEnum.two

    Above, the string names of each element, e.g. ``one``, ``two``, ``three``,
    are persisted to the database; the values of the Python `enum.Enum`, here
    indicated as integers, are not used; the value of each enum can therefore
    be any kind of Python object whether or not it is persistable.

    In order to persist the values and not the names, the `values_callable`
    parameter may be used. The value of this parameter is a user-supplied
    callable, which is intended to be used with a PEP-435-compliant enumerated
    class and returns a list of string values to be persisted. For a simple
    enumeration that uses string values, a callable such as
    ``lambda x: [e.value for e in x]`` is sufficient.
    """
    impl: type[_Enum] = _Enum
    cache_ok = True

    def __init__(
        self,
        *enums: Any,
        create_constraint: bool = False,
        metadata: MetaData | None = None,
        name: str | None = None,
        native_enum: bool = True,
        length: int | None = None,
        schema: str | None = None,
        quote: bool = False,
        inherit_schema: bool = False,
        validate_strings: bool = False,
        values_callable: Callable[[Any], list[str]] | None = None,
        sort_key_function: Callable[[Any], Any] | None = None,
        omit_aliases: bool = True,
    ):
        """Construct an enum.

        Keyword arguments which don't apply to a specific backend are ignored
        by that backend.

        Args:
            enums: Either exactly one PEP-435 compliant enumerated type or one
                or more string labels.
            create_constraint: When creating a non-native enumerated type, also
                build a ``CHECK`` constraint on the database against the valid
                values.
            metadata: Associates this type directly with a `MetaData` object.
                For types that exist on the target database as an independent
                schema construct (PostgreSQL), this type will be created and
                dropped within `create_all` and `drop_all` operations. If the
                type is not associated with any `MetaData` object, it will
                associate itself with each `Table` in which it is used, and
                will be created when any of those individual tables are
                created, after a check is performed for its existence. The type
                is only dropped when `drop_all` is called for that `Table`
                object's metadata, however.
            name: The name of this type. This is required for PostgreSQL
                and any future supported database which requires an explicitly
                named type, or an explicitly named constraint in order to
                generate the type and/or a table that uses it. If a PEP-435
                enumerated class was used, its name (converted to lower case)
                is used by default.
            native_enum: Uses the database's native enumeration type when
                available. When ``False``, uses `VARCHAR` and check constraint
                for all backends. When ``False``, the `VARCHAR` length can be
                controlled with `length` parameter; `length` is ignored if
                ``native_enum=True``.
            length: Allows specifying a custom length for the `VARCHAR` when a
                non-native enumeration datatype is used. By default it uses the
                length of the longest value.
            schema: Schema name of this type. For types that exist on the
                target database as an independent schema construct
                (PostgreSQL), this parameter specifies the named schema in
                which the type is present.
            quote: Sets explicit quoting preferences for the type's name.
            inherit_schema: When ``True``, the `schema` from the owning `Table`
                will be copied to the `schema` attribute of this `EnumEngine`,
                replacing whatever value was passed for the `schema` attribute.
            validate_strings: When ``True``, string values that are being
                passed to the database in a SQL statement will be checked for
                validity against the list of enumerated values. Unrecognized
                values will result in a `LookupError` being raised.
            values_callable: A callable which will be passed the PEP-435
                compliant enumerated type, which should then return a list of
                string values to be persisted. This allows for alternate usages
                such as using the string value of an enum to be persisted to
                the database instead of its name.
            sort_key_function: A Python callable which may be used as
                the ``key`` argument in the Python `sorted` built-in. The
                SQLAlchemy ORM requires that primary key columns which are
                mapped must be sortable in some way. When using an unsortable
                enumeration object such as a Python `enum.Enum`, this parameter
                may be used to set a default sort key function for the objects.
                By default, the database value of the enumeration is used as
                the sorting function.
            omit_aliases: A boolean that when true will remove aliases from
                PEP-435 enums.
        """
        super().__init__(
            *enums,
            create_constraint=create_constraint,
            metadata=metadata,
            name=name,
            native_enum=native_enum,
            length=length,
            schema=schema,
            quote=quote,
            inherit_schema=inherit_schema,
            validate_strings=validate_strings,
            values_callable=values_callable,
            sort_key_function=sort_key_function,
            omit_aliases=omit_aliases,
        )

    @staticmethod
    def rules() -> TypeEngineRules:
        return {
            'enums': lambda x: x[0] + x[1],
            'create_constraint': lambda x: any(x),
            'metadata': lambda x: x[0] or x[1],
            'name': lambda x: x[0] or x[1],
            'native_enum': lambda x: all(x),
            'length': lambda x: max(
                (i for i in x if i is not None),
                default=None,
            ),
            'schema': lambda x: x[0] or x[1],
            'quote': lambda x: any(x),
            'inherit_schema': lambda x: any(x),
            'validate_strings': lambda x: any(x),
            'values_callable': lambda x: x[0] or x[1],
            'sort_key_function': lambda x: x[0] or x[1],
            'omit_aliases': lambda x: all(x),
        }

    def coarse_type_engine(self, /, **kwargs: Any) -> BaseTypeEngine[Any]:
        return StringEngine()


class IntegerEngine(BaseTypeEngine[int]):
    """An integer engine.

    It typically uses `INTEGER`, or `BIGINT` on the DDL side, and on the Python
    side deals with `int` integers.
    """
    impl: type[_Integer] = _Integer
    cache_ok = True

    def __init__(self) -> None:
        """Construct an integer engine."""
        super().__init__()

    @staticmethod
    def rules() -> TypeEngineRules:
        return {}

    def coarse_type_engine(self, /, **kwargs: Any) -> BaseTypeEngine[Any]:
        return NumericEngine()


class IntervalEngine(BaseTypeEngine[datetime.timedelta]):
    """An interval engine.

    The `IntervalEngine` deals with `datetime.timedelta` objects. In
    PostgreSQL, the native `INTERVAL` type is used; for others, the value is
    stored as a date which is relative to the ``epoch`` (Jan. 1, 1970).

    Note that the `Interval` type does not currently provide date arithmetic
    operations on platforms which do not support interval types natively. Such
    operations usually require transformation of both sides of the expression
    (such as, conversion of both sides into integer epoch values first) which
    currently is a manual procedure.
    """
    impl: type[_Interval] = _Interval
    cache_ok = True

    def __init__(
        self,
        native: bool = True,
        second_precision: int | None = None,
        day_precision: int | None = None,
    ):
        """Construct an interval engine.

        Args:
            native: When True, use the actual `INTERVAL` type provided by the
                database, if supported (currently PostgreSQL, Oracle).
                Otherwise, represent the interval data as an epoch value
                regardless.
            second_precision: For native interval types which support a
                "fractional seconds precision" parameter (PostgreSQL, Oracle).
            day_precision: For native interval types which support a
                "day precision" parameter (Oracle).
        """
        super().__init__(native, second_precision, day_precision)

    @staticmethod
    def rules() -> TypeEngineRules:
        return {
            'native': lambda x: all(x),
            'second_precision': lambda x: max(
                (i for i in x if i is not None),
                default=None,
            ),
            'day_precision': lambda x: max(
                (i for i in x if i is not None),
                default=None,
            ),
        }

    def coarse_type_engine(self, /, **kwargs: Any) -> BaseTypeEngine[Any]:
        return JsonEngine()

    def coerce_compared_value(
        self, op: _OperatorType | None, value: Any
    ) -> Any:
        return self.impl.coerce_compared_value(op, value)  # type: ignore


class JsonEngine(BaseTypeEngine[_T]):
    """A json engine.

    The `JsonEngine` deals with JSON data. For some dialects, the native `JSON`
    type is used; for others, the value is stored as a string. The compatible
    database dialects with native JSON support are: PostgreSQL, MySQL, SQLite,
    and SQL Server.

    To allow ORM change events to propagate for elements associated with the
    `JsonEngine` class, use ``Mutable.as_mutable(JsonEngine)``.
    """
    impl: type[_TypeEngine[Any]] = _String
    cache_ok = True

    def __init__(self, none_as_null: bool = True):
        """
        Construct a json engine.

        Args:
            none_as_null: If ``True``, persist the value ``None`` as a SQL
                ``NULL`` value, not the JSON encoding of ``null``. Note that
                when this flag is ``False``, ``null`` construct can still be
                used to persist a ``NULL`` value, which may be passed directly
                as a parameter value that is specially interpreted by the
                `JSON` type as SQL ``NULL``.

        Examples:
            >>> from plateforme.database import null
            >>> conn.execute(table.insert(), {'data': null()})

        Note:
            The parameter `none_as_null` does not apply to the values passed to
            ``Column.default`` and ``Column.server_default``; a value of
            ``None`` passed for these parameters means "no default present".

            Additionally, when used in SQL comparison expressions, the Python
            value ``None`` continues to refer to SQL null, and not JSON NULL.
            The ``none_as_null`` flag refers explicitly to the persistence of
            the value within an ``INSERT`` or ``UPDATE`` statement. The
            ``JSON.NULL`` value should be used for SQL expressions that wish to
            compare to JSON null.
        """
        super().__init__(none_as_null)

    @staticmethod
    def rules() -> TypeEngineRules:
        return {
            'none_as_null': lambda x: any(x),
        }

    def coarse_type_engine(self, /, **kwargs: Any) -> None:
        return None

    def coerce_compared_value(
        self, op: _OperatorType | None, value: Any
    ) -> Any:
        return self.impl.coerce_compared_value(op, value)  # type: ignore

    def load_dialect_impl(self, dialect: Dialect) -> _TypeEngine[Any]:
        if self.impl is _TypeEngine:
            if dialect.name in ('postgresql', 'mysql', 'sqlite', 'sqlserver'):
                return dialect.type_descriptor(_JSON())
            else:
                return dialect.type_descriptor(_String())
        return self.impl_instance

    def process_bind_param(
        self, value: _T | None, dialect: Dialect
    ) -> Any:
        if isinstance(self.impl, _JSON):
            return None
        if value is not None:
            return json.dumps(value)
        return value

    def process_result_value(
        self, value: Any | None, dialect: Dialect
    ) -> _T | None:
        if isinstance(self.impl, _JSON):
            return value
        if value is not None:
            return json.loads(value)  # type: ignore
        return None


class NumericEngine(BaseTypeEngine[_TNumber]):
    """A numeric engine.

    A numeric engine for non-integer numeric types which typically uses
    `NUMERIC`, `FLOAT`, `DECIMAL`, or other variants on the DDL side, and on
    the Python side deals in `float` or `decimal.Decimal` types.

    Note:
        When using a `NumericEngine` against a database type that returns
        Python floating point values to the driver, the accuracy of the decimal
        conversion indicated by `asdecimal` may be limited. The behavior of
        specific numeric/floating point datatypes is a product of the SQL
        datatype in use, the Python DBAPI in use, as well as strategies that
        may be present within the SQLAlchemy dialect in use.
    """
    impl: type[_Numeric[Any]] = _Numeric[_TNumber]
    cache_ok = True

    @typing.overload
    def __init__(
        self: 'NumericEngine[float]',
        precision: int | None = ...,
        scale: int | None = ...,
        asdecimal: Literal[False] = ...,
        decimal_return_scale: int | None = ...,
    ):
        ...

    @typing.overload
    def __init__(
        self: 'NumericEngine[decimal.Decimal]',
        precision: int | None = ...,
        scale: int | None = ...,
        asdecimal: Literal[True] = ...,
        decimal_return_scale: int | None = ...,
    ):
        ...

    def __init__(
        self,
        precision: int | None = None,
        scale: int | None = None,
        asdecimal: bool = False,
        decimal_return_scale: int | None = None,
    ):
        """Construct a numeric engine.

        Args:
            precision: The numeric precision for use in DDL ``CREATE TABLE``.
            scale: The numeric scale for use in DDL ``CREATE TABLE``.
            asdecimal: Returns whether or not values should be sent as Python
                `decimal.Decimal` objects, or as floats. Different DBAPIs send
                one or the other based on datatypes - the Numeric type will
                ensure that return values are one or the other across DBAPIs
                consistently.
            decimal_return_scale: Default scale to use when converting from
                floats to Python decimals. Floating point values will typically
                be much longer due to decimal inaccuracy, and most floating
                point database types don't have a notion of `scale`, so by
                default the float type looks for the first ten decimal places
                when converting. Specifying this value will override that
                length. Types which do include an explicit `scale` value, such
                as the base `Numeric` as well as the MySQL float types, will
                use the value of `scale` as the default for
                `decimal_return_scale`, if not otherwise specified.

        When using the `NumericEngine`, care should be taken to ensure that the
        `asdecimal` setting is appropriate for the DBAPI in use. When base
        `Numeric` applies a conversion from decimal->float or float->decimal,
        this conversion incurs an additional performance overhead for all
        result columns received.

        DBAPIs that return `decimal.Decimal` natively (e.g. psycopg2) will have
        better accuracy and higher performance with a setting of ``True``, as
        the native translation to `decimal.Decimal` reduces the amount of
        floating point issues at play, and the Numeric type itself doesn't need
        to apply any further conversions. However, another DBAPI which returns
        floats natively will incur an additional conversion overhead, and is
        still subject to floating point data loss, in which case
        ``asdecimal=False`` will at least remove the extra conversion overhead.
        """
        super().__init__(
            precision,
            scale,
            decimal_return_scale,
            asdecimal,
        )

    @staticmethod
    def rules() -> TypeEngineRules:
        return {
            'precision': lambda x: max(
                (i for i in x if i is not None),
                default=None,
            ),
            'scale': lambda x: max(
                (i for i in x if i is not None),
                default=None,
            ),
            'asdecimal': lambda x: any(x),
            'decimal_return_scale': lambda x: max(
                (i for i in x if i is not None),
                default=None,
            ),
        }

    def coarse_type_engine(self, /, **kwargs: Any) -> BaseTypeEngine[Any]:
        return StringEngine()


class PickleEngine(BaseTypeEngine[object]):
    """A piclke engine for Python objects.

    The `PickleEngine` holds Python objects, which are serialized using pickle.
    It builds upon the binary type engine to apply Python's ``pickle.dumps()``
    to incoming objects, and ``pickle.loads()`` on the way out, allowing any
    pickleable Python object to be stored as a serialized binary field.

    To allow ORM change events to propagate for elements associated with the
    `PickleEngine` class, use ``Mutable.as_mutable(PickleEngine)``.
    """
    impl: type[_Binary] = _LargeBinary
    cache_ok = True

    def __init__(
        self,
        protocol: int = pickle.HIGHEST_PROTOCOL,
        pickler: Any | None = None,
        comparator: Callable[[Any, Any], bool] | None= None,
        impl: '_TEngine[Any] | None' = None,
    ) -> None:
        """Construct a piclke engine.

        Args:
            protocol: The pickle protocol to use.
            pickler: May be any object with ickle-compatible `dumps` and
                `loads` methods.
            comparator: a 2 arguments callable predicate used to compare values
                of this type. If left as ``None``, the Python ``equals``
                operator is used to compare values.
            impl: A binary-storing `BaseTypeEngine` class or instance to use in
                place of the default `Binary` type. For example the `BLOB`
                class may be more effective when using MySQL.
        """
        super().__init__()
        self.protocol = protocol
        self.pickler = pickler or pickle
        self.comparator = comparator

        # Check for a custom implementation
        if impl:
            self.impl = _to_instance(impl)  # type: ignore

    def __reduce__(self) -> tuple[type['PickleEngine'], tuple[Any, ...]]:
        return PickleEngine, (self.protocol, None, self.comparator)

    @staticmethod
    def rules() -> TypeEngineRules:
        return {
            'protocol': lambda x: x[0] or x[1],
            'pickler': lambda x: x[0] or x[1],
            'comparator': lambda x: x[0] or x[1],
            'impl': lambda x: x[0] or x[1],
        }

    def coarse_type_engine(self, /, **kwargs: Any) -> None:
        return None

    def bind_processor(
        self, dialect: Dialect
    ) -> Callable[[Any], Any] | None:
        impl_processor = self.impl_instance.bind_processor(dialect)
        dumps = self.pickler.dumps
        protocol = self.protocol
        if impl_processor:
            fixed_impl_processor = impl_processor
            def process(value: Any) -> Any:
                if value is not None:
                    value = dumps(value, protocol)
                return fixed_impl_processor(value)
        else:
            def process(value: Any) -> Any:
                if value is not None:
                    value = dumps(value, protocol)
                return value
        return process

    def result_processor(
        self, dialect: Dialect, coltype: object
    ) -> Callable[[Any], Any] | None:
        impl_processor = self.impl_instance.result_processor(dialect, coltype)
        loads = self.pickler.loads
        if impl_processor:
            fixed_impl_processor = impl_processor
            def process(value: Any) -> Any:
                value = fixed_impl_processor(value)
                if value is None:
                    return None
                return loads(value)
        else:
            def process(value: Any) -> Any:
                if value is None:
                    return None
                return loads(value)
        return process

    def compare_values(self, x: Any, y: Any) -> bool:
        if self.comparator:
            return self.comparator(x, y)
        else:
            return x == y  # type: ignore


class StringEngine(BaseTypeEngine[str]):
    """A string engine.

    A string engine which typically uses `VARCHAR`, `NVARCHAR`, `TEXT`, or
    other variants on the DDL side, and on the Python side deals with `str`
    types.
    """
    impl: type[_String] = _String
    cache_ok = True

    def __init__(
        self,
        length: int | None = None,
        collation: str | None = None,
    ):
        """Construct a string engine.

        Args:
            length: A length for the column for use in DDL and ``CAST``
                expressions. If `length` is omitted, `TEXT` and related types
                will be used. Otherwise, `VARCHAR` and related types will be
                used. Whether the value is interpreted as bytes or characters
                is database specific.
            collation: A column-level collation for use in DDL and ``CAST``
                expressions. Renders using the ``COLLATE`` keyword supported by
                SQLite, MySQL, and PostgreSQL. If `collation` is equal to
                ``ascii``, `VARCHAR` and related types will be used. Otherwise,
                `NVARCHAR` and related types will be used.
        """
        if self.impl is None:
            if collation == 'ascii':
                if length is not None:
                    self.impl = _String
                else:
                    self.impl = _Text
            else:
                if length is not None:
                    self.impl = _Unicode
                else:
                    self.impl = _UnicodeText
        super().__init__(length, collation)

    @staticmethod
    def rules() -> TypeEngineRules:
        return {
            'length': lambda x: max(
                (i for i in x if i is not None),
                default=None,
            ),
            'collation': lambda x: x[0] or x[1],
        }

    def coarse_type_engine(self, /, **kwargs: Any) -> BaseTypeEngine[Any]:
        return JsonEngine()


class TimeEngine(BaseTypeEngine[datetime.time]):
    """A time engine.

    The `TimeEngine` returns objects from the Python `datetime.time`.
    """
    impl: type[_Time] = _Time
    cache_ok = True

    def __init__(self) -> None:
        """
        Construct a time engine.
        """
        super().__init__()

    @staticmethod
    def rules() -> TypeEngineRules:
        return {}

    def coarse_type_engine(self, /, **kwargs: Any) -> BaseTypeEngine[Any]:
        return DateTimeEngine()


class UuidEngine(BaseTypeEngine[_TUuid]):
    """A UUID engine.

    For backends that have no ``native`` UUID datatype, the value will make use
    of "CHAR(32)" and store the UUID as a 32-character alphanumeric hex string.

    For backends which are known to support `UUID` directly or a similar
    uuid-storing datatype such as SQL Server's ``UNIQUEIDENTIFIER``, a
    ``native`` mode enabled by default allows these types will be used on those
    backends.

    In its default mode of use, the `UuidEngine` datatype expects Python uuid
    objects, from the Python
    [uuid module](https://docs.python.org/3/library/uuid.html).
    """
    impl: type[_Uuid[Any]] = _Uuid[_TUuid]
    cache_ok = True

    def __init__(
        self,
        as_uuid: bool = True,
        native_uuid: bool = True,
    ):
        """Construct a UUID engine.

        Args:
            as_uuid: If ``True``, values will be interpreted as Python uuid
                objects, converting to/from string via the DBAPI.
            native_uuid: If ``True``, backends that support either the `UUID`
                datatype directly, or a UUID-storing value (such as SQL
                Server's ``UNIQUEIDENTIFIER`` will be used by those backends.
                If ``False``, a ``CHAR(32)`` datatype will be used for all
                backends regardless of native support.
        """
        super().__init__(as_uuid, native_uuid)

    @staticmethod
    def rules() -> TypeEngineRules:
        return {
            'as_uuid': lambda x: all(x),
            'native_uuid': lambda x: all(x),
        }

    def coarse_type_engine(self, /, **kwargs: Any) -> BaseTypeEngine[Any]:
        return StringEngine()

    def coerce_compared_value(
        self, op: _OperatorType | None, value: Any
    ) -> Any:
        return self.impl.coerce_compared_value(op, value)  # type: ignore


DefaultEngine: BaseTypeEngine[Any] = \
    Mutable.as_mutable(JsonEngine())  # type: ignore
"""Default type engine.

It should be used by fields that do not have a specific type engine defined and
for which no type engine can be resolved.
"""


class ARRAY(BaseTypeEngine[Sequence[Any]]):
    """The SQL ARRAY concrete type.

    The `ARRAY` type engine serves as the basis for all ``ARRAY`` operations.
    However, currently only the PostgreSQL backend has support for SQL arrays.

    To allow ORM change events to propagate for elements associated with the
    `ARRAY` class, use ``Mutable.as_mutable(ARRAY)``.
    """
    impl = _ARRAY
    cache_ok = True

    def __init__(
        self,
        item_type: '_TEngine[Any]',
        as_tuple: bool = False,
        dimensions: int | None = None,
        zero_indexes: bool = False,
    ):
        """Construct an ARRAY type.

        Args:
            item_type: The data type of items of this array. Note that
                dimensionality is irrelevant here, so multi-dimensional arrays
                like ``INTEGER[][]``, are constructed as ``ARRAY(Integer)``,
                not as ``ARRAY(ARRAY(Integer))`` or such.
            as_tuple: Specify whether return results should be converted to
                tuples from lists. This parameter is not generally needed as a
                Python list corresponds well to a SQL array.
            dimensions: If not ``None``, the `ARRAY` will assume a fixed number
                of dimensions. This impacts how the array is declared on the
                database, how it goes about interpreting Python and result
                values, as well as how expression behavior in conjunction with
                the ``getitem`` operator works.
            zero_indexes: When ``True``, index values will be converted between
                Python zero-based and SQL one-based indexes, e.g. a value of
                one will be added to all index values before passing to the
                database.
        """
        super().__init__(item_type, as_tuple, dimensions, zero_indexes)

    @staticmethod
    def rules() -> TypeEngineRules:
        return {
            'item_type': lambda x: (x[0] | x[1]),
            'as_tuple': lambda x: any(x),
            'dimensions': lambda x: max(
                (i for i in x if i is not None),
                default=None,
            ),
            'zero_indexes': lambda x: any(x),
        }

    def coarse_type_engine(self, /, **kwargs: Any) -> BaseTypeEngine[Any]:
        return StringEngine()

    def coerce_compared_value(
        self, op: _OperatorType | None, value: Any
    ) -> Any:
        return self.impl.coerce_compared_value(op, value)  # type: ignore


class BIGINT(IntegerEngine):
    """The SQL BIGINT concrete type."""
    impl = _BIGINT


class BINARY(BinaryEngine):
    """The SQL BINARY concrete type."""
    impl = _BINARY


class BLOB(BinaryEngine):
    """The SQL BLOB concrete type."""
    impl = _BLOB


class BOOLEAN(BooleanEngine):
    """The SQL BOOLEAN concrete type."""
    impl = _BOOLEAN


class CHAR(StringEngine):
    """The SQL CHAR concrete type."""
    impl = _CHAR


class CLOB(StringEngine):
    """The SQL CLOB concrete type."""
    impl = _CLOB


class DATE(DateEngine):
    """The SQL DATE concrete type."""
    impl = _DATE


class DATETIME(DateTimeEngine):
    """The SQL DATETIME concrete type."""
    impl = _DATETIME


class DECIMAL(NumericEngine[decimal.Decimal]):
    """The SQL DECIMAL concrete type."""
    impl = _DECIMAL


class DOUBLE(NumericEngine[float]):
    """The SQL DOUBLE concrete type."""
    impl = _DOUBLE


class DOUBLE_PRECISION(NumericEngine[float]):
    """The SQL DOUBLE_PRECISION concrete type."""
    impl = _DOUBLE_PRECISION


class FLOAT(NumericEngine[float]):
    """The SQL FLOAT concrete type."""
    impl = _FLOAT


class INTEGER(IntegerEngine):
    """The SQL INTEGER concrete type."""
    impl = _INTEGER


class JSON(JsonEngine[_T]):
    """The SQL JSON concrete type."""
    impl = _JSON


class NCHAR(StringEngine):
    """The SQL NCHAR concrete type."""
    impl = _NCHAR


class NUMERIC(NumericEngine[float]):
    """The SQL NUMERIC concrete type."""
    impl = _NUMERIC


class NVARCHAR(StringEngine):
    """The SQL NVARCHAR concrete type."""
    impl = _NVARCHAR


class REAL(NumericEngine[float]):
    """The SQL REAL concrete type."""
    impl = _REAL


class SMALLINT(IntegerEngine):
    """The SQL SMALLINT concrete type."""
    impl = _SMALLINT


class TEXT(StringEngine):
    """The SQL TEXT concrete type."""
    impl = _TEXT


class TIME(TimeEngine):
    """The SQL TIME concrete type."""
    impl = _TIME


class TIMESTAMP(DateTimeEngine):
    """The SQL TIMESTAMP concrete type."""
    impl = _TIMESTAMP


class UUID(UuidEngine[_TUuid]):
    """The SQL UUID concrete type."""
    impl = _UUID


class VARBINARY(BinaryEngine):
    """The SQL VARBINARY concrete type."""
    impl = _VARBINARY


class VARCHAR(StringEngine):
    """The SQL VARCHAR concrete type."""
    impl = _VARCHAR


def combine_type_engines(
    *engines: '_TEngine[Any]',
    **kwargs: Any,
) -> BaseTypeEngine[Any]:
    """Combine type engines.

    Args:
        engines: The engines to combine.
        kwargs: Additional keyword arguments to pass to the
            `coarse_type_engine` method for each engine.

    Returns:
        A new type engine that is the combination of the given engines.
    """
    if len(engines) == 0:
        raise ValueError("At least one engine must be provided.")
    if len(engines) == 1:
        if isinstance(engines[0], type):
            return engines[0]()
        return engines[0]

    # Retrieve the first two engines and convert them to instances
    engine_a, engine_b, *engines_remaining = engines
    if isinstance(engine_a, type):
        engine_a = engine_a()
    if isinstance(engine_b, type):
        engine_b = engine_b()
    # Initialize the hierarchy and payloads for each engine
    hierarchy_a = [engine_a]
    hierarchy_b = [engine_b]
    payloads_a = engine_a.payloads
    payloads_b = engine_b.payloads

    # Initialize the common payload to None
    class CommonPayload(TypedDict):
        engine: type[BaseTypeEngine[Any]]
        arguments_a: dict[str, Any]
        arguments_b: dict[str, Any]
    common_payload: CommonPayload | None = None

    # Iterate until a common payload is found
    while (common_payload is None):
        # Find the common payload between the two type engines
        for payload_a in reversed(payloads_a):
            for payload_b in reversed(payloads_b):
                if payload_a['engine'] == payload_b['engine']:
                    common_payload = CommonPayload(
                        engine=payload_a['engine'],
                        arguments_a=payload_a['arguments'],
                        arguments_b=payload_b['arguments'],
                    )
                    break

        if common_payload is None:
            # Update the hierarchy and payloads for the next iteration
            # with their coarser type engine and associated payloads.
            # If no coarser type engine is available, raise an error.
            # If a circular reference is detected, raise an error.
            def _extend_hierarchy_and_payloads(
                hierarchy: list[BaseTypeEngine[Any]],
                payloads: list[TypeEnginePayload],
            ) -> bool:
                coarser = hierarchy[-1].coarse_type_engine(**kwargs)
                if coarser is not None:
                    hierarchy.append(coarser)
                    hierarchy_types = {type(engine) for engine in hierarchy}
                    if len(hierarchy_types) != len(hierarchy):
                        raise ValueError(
                            f"Circular reference detected for type engine "
                            f"{hierarchy[-1].__class__.__name__!r}."
                        )
                    payloads.extend(coarser.payloads)
                    return True
                return False

            # Execute for both type engines
            extend_a = _extend_hierarchy_and_payloads(hierarchy_a, payloads_a)
            extend_b = _extend_hierarchy_and_payloads(hierarchy_b, payloads_b)

            # Check if both type engines have been extended
            if not extend_a and not extend_b:
                raise ValueError(
                    f"No common type engine found between "
                    f"{hierarchy_a[0].__class__.__name__!r} and "
                    f"{hierarchy_b[0].__class__.__name__!r}."
                )

    # Combine the common engine with the remaining engines
    common_engine = common_payload['engine']
    common_arguments = {}
    for key, rule in common_engine.rules().items():
        common_arguments[key] = rule((
            common_payload['arguments_a'].get(key),
            common_payload['arguments_b'].get(key),
        ))
    engine = common_engine(**common_arguments)
    return combine_type_engines(engine, *engines_remaining, **kwargs)
