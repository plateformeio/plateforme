# plateforme.core.types.secrets
# -----------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing secret types within the Plateforme
framework leveraging Pydantic schemas for validation and serialization, and
compatibility with SQLAlchemy's data type system.
"""

import typing
from typing import Any, ClassVar, Generic, Self, TypeVar

from ..database.types import (
    BaseTypeEngine,
    BinaryEngine,
    JsonEngine,
    StringEngine,
)
from ..schema import core as core_schema
from ..schema.core import (
    CoreSchema,
    GetCoreSchemaHandler,
    GetJsonSchemaHandler,
    SchemaSerializer,
    SerializationInfo,
)
from ..schema.json import JsonSchemaDict
from .base import BaseType

_T = TypeVar('_T')
_TSecret = TypeVar('_TSecret', bound='BaseSecret[Any]')

__all__ = (
    'BaseSecret',
    'Secret',
    'SecretBytes',
    'SecretStr',
)


def _secret_display(value: _T) -> str:
    """Display the secret value."""
    return '**********' if value else ''


def _secret_serialization(
    value: _TSecret, info: SerializationInfo | None = None
) -> _TSecret | str:
    """Serialize the secret value."""
    if info and info.mode == 'json':
        return _secret_display(value.get_secret_value())
    return value


class BaseSecret(BaseType, Generic[_T]):
    """A base secret for storing sensitive information."""
    if typing.TYPE_CHECKING:
        _schema: ClassVar[CoreSchema | None]
        _schema_type: ClassVar[str | None]

    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        """Create a new instance of the base secret."""
        # Check if class is directly instantiated
        if cls is BaseSecret:
            raise TypeError(
                "Plateforme base secret cannot be directly instantiated. Use "
                "either Secret[<type>], SecretStr, SecretBytes, or subclass "
                "from Secret[<type>] instead."
            )
        return super().__new__(cls)

    def __init__(self, secret_value: _T) -> None:
        """Initialize the base secret with the given value."""
        self._value: _T = secret_value

    def get_secret_value(self) -> _T:
        """Get the secret value."""
        return self._value

    def _display(self) -> _T | str:
        """Display the secret value."""
        raise NotImplementedError()

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source: type[Any],
        handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        inner_schema = getattr(cls, '_schema', None)
        if inner_schema is None:
            inner_type = None
            # If origin type is secret then extract the inner type directly
            origin_type = typing.get_origin(source)
            if origin_type is not None:
                inner_type = typing.get_args(source)[0]
            # Otherwise, extract the inner type from the base class
            else:
                bases = getattr(
                    cls, '__orig_bases__', getattr(cls, '__bases__', [])
                )
                for base in bases:
                    if typing.get_origin(base) is Secret:
                        inner_type = typing.get_args(base)[0]
                if bases == [] or inner_type is None:
                    raise TypeError(
                        f"Can't get secret type from {cls.__name__}. Use "
                        f"Secret[<type>], or subclass from Secret[<type>] "
                        f"instead."
                    )
            inner_schema = handler.generate_schema(inner_type)

        def get_json_schema(
            _core_schema: CoreSchema,
            _handler: GetJsonSchemaHandler,
        ) -> JsonSchemaDict:
            schema = _handler(inner_schema)
            schema.update(
                type='string',
                writeOnly=True,
                format='password',
            )
            return schema

        json_schema = core_schema.no_info_after_validator_function(
            source,
            inner_schema,
        )

        def get_secret_schema(strict: bool) -> CoreSchema:
            return core_schema.json_or_python_schema(
                python_schema=core_schema.union_schema(
                    [
                        core_schema.is_instance_schema(source),
                        json_schema,
                    ],
                    strict=strict,
                    custom_error_type=cls._schema_type,
                ),
                json_schema=json_schema,
                serialization=core_schema.plain_serializer_function_ser_schema(
                    _secret_serialization,
                    info_arg=True,
                    when_used='always',
                ),
            )

        return core_schema.lax_or_strict_schema(
            lax_schema=get_secret_schema(strict=False),
            strict_schema=get_secret_schema(strict=True),
            metadata={'pydantic_js_functions': [get_json_schema]},
        )

    @classmethod
    def __get_sqlalchemy_data_type__(
        cls, **kwargs: Any
    ) -> BaseTypeEngine[Any] | None:
        return None

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, self.__class__) \
            and self.get_secret_value() == other.get_secret_value()

    def __hash__(self) -> int:
        return hash(self.get_secret_value())

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self._display()!r})'

    def __str__(self) -> str:
        return str(self._display())

    __pydantic_serializer__ = SchemaSerializer(
        core_schema.any_schema(
            serialization=core_schema.plain_serializer_function_ser_schema(
                _secret_serialization,
                info_arg=True,
                when_used='always',
            )
        )
    )


class Secret(BaseSecret[_T]):
    """A secret generic type.

    It is used for storing sensitive information that you do not want to be
    visible in logging or tracebacks. When the secret value is nonempty, it is
    displayed as ``'**********'`` instead of the underlying value in calls to
    `repr()` and `str()`. If the value is empty, it is displayed as ``''``.

    Examples:
        >>> from plateforme import BaseModel
        ... from plateforme.types import Secret

        >>> class User(BaseModel):
        ...     username: str
        ...     password: Secret[int]
        ... user = User(username='johndoe', password='123')

        >>> print(user)
        username='johndoe' password=Secret('**********')

        >>> print(user.password.get_secret_value())
        '123'

        >>> print((Secret('password'), Secret('')))
        (Secret('**********'), Secret(''))

    Note:
        Custom secret types can be created by subclassing `Secret` and
        providing a type hint for the secret value. A specific validation
        schema and custom error type can be provided by defining a class
        attribute `_schema` with a Pydantic schema and a `_schema_type` with a
        string representing the error type.
    """

    _schema = None
    _schema_type = None

    def _display(self) -> str:
        """Display the secret value."""
        return _secret_display(self.get_secret_value())

    @classmethod
    def __get_sqlalchemy_data_type__(
        cls, **kwargs: Any
    ) -> 'JsonEngine[_T]':
        return JsonEngine[_T](
            none_as_null=kwargs.get('data_none_as_null', True),
            processors={
                'before': lambda v, _: v.get_secret_value() if v else None,
                'after': lambda v, _: cls(v) if v else None,
            },
        )


class SecretStr(BaseSecret[str]):
    """A secret string type.

    It is used for storing sensitive information that you do not want to be
    visible in logging or tracebacks. When the secret value is nonempty, it is
    displayed as ``'**********'`` instead of the underlying value in calls to
    `repr()` and `str()`. If the value is empty, it is displayed as ``''``.

    Examples:
        >>> from plateforme import BaseModel
        ... from plateforme.types import SecretStr

        >>> class User(BaseModel):
        ...     username: str
        ...     password: SecretStr
        ... user = User(username='johndoe', password='kLj4$2')

        >>> print(user)
        username='johndoe' password=SecretStr('**********')

        >>> print(user.password.get_secret_value())
        kLj4$2

        >>> print((SecretStr('password'), SecretStr('')))
        (SecretStr('**********'), SecretStr(''))
    """

    _schema = core_schema.str_schema()
    _schema_type = 'string_type'

    def _display(self) -> str:
        return _secret_display(self.get_secret_value())

    @classmethod
    def __get_sqlalchemy_data_type__(cls, **kwargs: Any) -> StringEngine:
        return StringEngine(
            length=kwargs.get('max_length', None),
            collation=kwargs.get('data_collation', None),
            processors={
                'before': lambda v, _: v.get_secret_value() if v else None,
                'after': lambda v, _: cls(v) if v else None,
            },
        )

    def __len__(self) -> int:
        return len(self._value)


class SecretBytes(BaseSecret[bytes]):
    """A secret bytes type.

    It is used for storing sensitive information that you do not want to be
    visible in logging or tracebacks. When the secret value is nonempty, it is
    displayed as ``b'**********'`` instead of the underlying value in calls to
    `repr()` and `str()`. If the value is empty, it is displayed as ``b''``.

    Examples:
        >>> from plateforme import BaseModel
        ... from plateforme.types import SecretBytes

        >>> class User(BaseModel):
        ...     username: str
        ...     password: SecretBytes
        ... user = User(username='johndoe', password=b'kLj4$2')

        >>> print(user)
        username='johndoe' password=SecretBytes(b'**********')

        >>> print(user.password.get_secret_value())
        b'kLj4$2'

        >>> print((SecretBytes(b'password'), SecretBytes(b'')))
        (SecretBytes(b'**********'), SecretBytes(b''))
    """

    _schema = core_schema.bytes_schema()
    _schema_type = 'bytes_type'

    def _display(self) -> bytes:
        """Display the secret value."""
        return _secret_display(self.get_secret_value()).encode()

    @classmethod
    def __get_sqlalchemy_data_type__(cls, **kwargs: Any) -> BinaryEngine:
        return BinaryEngine(
            length=kwargs.get('max_length', None),
            processors={
                'before': lambda v, _: v.get_secret_value() if v else None,
                'after': lambda v, _: cls(v) if v else None,
            },
        )

    def __len__(self) -> int:
        return len(self._value)
