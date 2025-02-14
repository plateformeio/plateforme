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

from typing import Any, Generic, Self, TypeVar

from ..database.types import BaseTypeEngine, BinaryEngine, StringEngine
from ..schema import core as core_schema
from ..schema.core import (
    CoreSchema,
    GetCoreSchemaHandler,
    GetJsonSchemaHandler,
    SerializationInfo,
)
from ..schema.json import JsonSchemaDict
from .base import BaseType

_T = TypeVar('_T', str, bytes)

__all__ = (
    'SecretType',
    'SecretBytes',
    'SecretStr',
)


def _secret_display(value: str | bytes) -> str:
    return '**********' if value else ''


class SecretType(BaseType, Generic[_T]):
    """A secret type for storing sensitive information."""

    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        """Create a new instance of the secret type."""
        # Check if class is directly instantiated
        if cls is SecretType:
            raise TypeError(
                "Plateforme secret type cannot be directly instantiated. Use "
                "either `SecretStr` or `SecretBytes` instead."
            )
        return super().__new__(cls)

    def __init__(self, secret_value: _T) -> None:
        """Initialize the secret type with the given value."""
        self._value: _T = secret_value

    def get_secret_value(self) -> _T:
        """Get the secret value."""
        return self._value

    def _display(self) -> _T:
        """Display the secret value."""
        raise NotImplementedError

    @classmethod
    def serialize(
        cls, value: Self, info: SerializationInfo | None = None
    ) -> Self | str:
        """Serialize the secret value."""
        if info and info.mode == 'json':
            return _secret_display(value.get_secret_value())
        return value

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source: type[Any],
        __handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        field_type: type[str | bytes]
        inner_schema: CoreSchema
        if issubclass(source, SecretStr):
            field_type = str
            inner_schema = core_schema.str_schema()
        else:
            assert issubclass(source, SecretBytes)
            field_type = bytes
            inner_schema = core_schema.bytes_schema()
        error_kind = 'string_type' if field_type is str else 'bytes_type'

        def get_json_schema(
            __core_schema: CoreSchema,
            handler: GetJsonSchemaHandler,
        ) -> JsonSchemaDict:
            schema = handler(inner_schema)
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

        schema = core_schema.json_or_python_schema(
            python_schema=core_schema.union_schema(
                [
                    core_schema.is_instance_schema(source),
                    json_schema,
                ],
                strict=True,
                custom_error_type=error_kind,
            ),
            json_schema=json_schema,
            serialization=core_schema.plain_serializer_function_ser_schema(
                cls.serialize,
                info_arg=True,
                return_schema=core_schema.str_schema(),
                when_used='json',
            ),
        )
        schema.setdefault('metadata', dict(
            pydantic_js_functions=[get_json_schema],
        ))

        return schema

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

    def __len__(self) -> int:
        return len(self._value)

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self._display()!r})'

    def __str__(self) -> str:
        return str(self._display())


class SecretStr(SecretType[str]):
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

    def _display(self) -> str:
        return _secret_display(self.get_secret_value())

    @classmethod
    def __get_sqlalchemy_data_type__(cls, **kwargs: Any) -> StringEngine:
        return StringEngine(
            length=kwargs.get('max_length', None),
            collation=kwargs.get('data_collation', None),

        )


class SecretBytes(SecretType[bytes]):
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

    def _display(self) -> bytes:
        """Display the secret value."""
        return _secret_display(self.get_secret_value()).encode()

    @classmethod
    def __get_sqlalchemy_data_type__(cls, **kwargs: Any) -> BinaryEngine:
        return BinaryEngine(
            length=kwargs.get('max_length', None),
        )
