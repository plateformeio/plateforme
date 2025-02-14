# plateforme.core.types.networks
# ------------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing network types within the Plateforme
framework leveraging Pydantic schemas for validation and serialization, and
compatibility with SQLAlchemy's data type system.
"""

import dataclasses
import ipaddress
import re
import typing
from typing import Annotated, Any, Literal, Self, Union

from ..database.types import StringEngine
from ..patterns import EMAIL_MAX_LENGTH, RegexPattern, parse_email
from ..representations import Representation
from ..schema import core as core_schema
from ..schema.core import (
    CoreSchema,
    GetCoreSchemaHandler,
    GetJsonSchemaHandler,
    ValidationInfo,
)
from ..schema.json import JsonSchemaDict
from ..schema.types import (
    PydanticIPvAnyAddress,
    PydanticIPvAnyInterface,
    PydanticIPvAnyNetwork,
    PydanticMultiHostUrl,
    PydanticUrl,
    UrlConstraints,
)
from .base import BaseType, BaseTypeFactory

__all__ = (
    'DEFAULT_DRIVERS',
    # Email
    'Email',
    'NameEmail',
    # Engine
    'EngineUrl',
    'EngineMap',
    # IP
    'IPvAddressFactory',
    'IPvAddressFactoryAlias',
    'IPvAnyAddress',
    'IPv4Address',
    'IPv6Address',
    'IPvInterfaceFactory',
    'IPvInterfaceFactoryAlias',
    'IPvAnyInterface',
    'IPv4Interface',
    'IPv6Interface',
    'IPvNetworkFactory',
    'IPvNetworkFactoryAlias',
    'IPvAnyNetwork',
    'IPv4Network',
    'IPv6Network',
    # URL
    'UrlFactory',
    'UrlConstraints',
    'AnyUrl',
    'AnyHttpUrl',
    'AnyMultiHostUrl',
    'FileUrl',
    'HttpUrl',
    'AmqpDsn',
    'CockroachDsn',
    'KafkaDsn',
    'MariaDBDsn',
    'MongoDsn',
    'MySQLDsn',
    'NatsDsn',
    'OracleDsn',
    'PostgresDsn',
    'RedisDsn',
    'SQLiteDsn',
    'SQLServerDsn',
)


DEFAULT_DRIVERS = {
    'oracle': 'oracledb',
    'postgresql': 'asyncpg',
    'mariadb': 'asyncmy',
    'mssql': 'aioodbc',
    'mysql': 'asyncmy',
    'sqlite': 'aiosqlite',
}
"""The default database drivers for the supported database engines."""


# MARK: Email

if typing.TYPE_CHECKING:
    Email = Annotated[str, ...]
else:
    class Email(BaseType):
        """A plain email address type.

        It validates an email address as specified by
        [RFC 5322](https://datatracker.ietf.org/doc/html/rfc5322#section-3.4).

        Examples:
            >>> from plateforme import BaseModel
            ... from plateforme.types import Email
            >>> class User(BaseModel):
            ...     email: Email
            >>> user = User(email='jane.bloggs@example.com')

            >>> print(user.email)
            jane.bloggs@example.com
        """

        @classmethod
        def __get_pydantic_core_schema__(
            cls,
            __source: type[Any],
            __handler: GetCoreSchemaHandler,
        ) -> CoreSchema:
            return core_schema.no_info_after_validator_function(
                cls.validate,
                core_schema.str_schema()
            )

        @classmethod
        def __get_pydantic_json_schema__(
            cls,
            core_schema: CoreSchema,
            handler: GetJsonSchemaHandler,
        ) -> JsonSchemaDict:
            schema = handler(core_schema)
            schema.update(type='string', format='email')
            return schema

        @classmethod
        def __get_sqlalchemy_data_type__(cls, **kwargs: Any) -> StringEngine:
            length = kwargs.get('max_length', EMAIL_MAX_LENGTH)
            return StringEngine(length=min(length, EMAIL_MAX_LENGTH))

        @classmethod
        def validate(
            cls,
            __value: str,
            _: ValidationInfo | None = None,
        ) -> Self:
            return parse_email(__value)[1]


class NameEmail(BaseType, Representation):
    """A formatted name and email address type.

    It validates a name and email address combination as specified by
    [RFC 5322](https://datatracker.ietf.org/doc/html/rfc5322#section-3.4). The
    type has two properties: `name` and `email`. If the `name` is not provided,
    it's inferred from the email address.

    Examples:
        >>> from plateforme import BaseModel
        ... from plateforme.types import NameEmail
        >>> class User(BaseModel):
        ...     email: NameEmail
        >>> user = User(email='Jane Bloggs <jane.bloggs@example.com>')

        >>> print(user.email)
        Jane Bloggs <jane.bloggs@example.com>

        >>> print(user.email.name)
        Jane Bloggs
    """
    __slots__ = ('name', 'email')

    def __init__(self, name: str, email: str):
        """Inialize a formatted name and email address."""
        self.name = name
        self.email = email

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, NameEmail) \
            and (self.name, self.email) == (other.name, other.email)

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        __source: type[Any],
        __handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        json_schema = core_schema.str_schema()
        python_schema = core_schema.union_schema(
            [
                core_schema.is_instance_schema(cls),
                json_schema,
            ],
            custom_error_type='name_email_type',
            custom_error_message='Input is not a valid name email',
        )

        return core_schema.no_info_after_validator_function(
            cls.validate,
            core_schema.json_or_python_schema(json_schema, python_schema),
            serialization=core_schema.to_string_ser_schema(),
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        core_schema: CoreSchema,
        handler: GetJsonSchemaHandler,
    ) -> JsonSchemaDict:
        schema = handler(core_schema)
        schema.update(type='string', format='name-email')
        return schema

    @classmethod
    def __get_sqlalchemy_data_type__(cls, **kwargs: Any) -> StringEngine:
        length = kwargs.get('max_length', EMAIL_MAX_LENGTH)
        return StringEngine(length=min(length, EMAIL_MAX_LENGTH))

    @classmethod
    def validate(
        cls,
        __value: Self | str,
        _: ValidationInfo | None = None,
    ) -> Self:
        if isinstance(__value, cls):
            return __value
        else:
            name, email = parse_email(__value)  # type: ignore[arg-type]
            if name is None:
                name = email.split('@')[0]
            return cls(name, email)

    def __str__(self, _: bool = False, /) -> str:
        return f'{self.name} <{self.email}>'


# MARK: Engine

@dataclasses.dataclass(frozen=True, kw_only=True, slots=True)
class EngineUrl:
    """A database engine URL type enforcing async driver selection."""

    scheme: str
    """The scheme part of the URL."""

    username: str | None = None
    """The username part of the URL, or omit for no username."""

    password: str | None = None
    """The password part of the URL, or omit for no password."""

    host: str | None = None
    """The host part of the URL."""

    port: int | None = None
    """The port part of the URL, or omit for no port."""

    database: str | None = None
    """The database part of the URL, or omit for no database path."""

    @typing.overload
    def __init__(
        self,
        conn: str,
        /,
        *,
        scheme: None = None,
        username: None = None,
        password: None = None,
        host: None = None,
        port: None = None,
        database: None = None,
    ) -> None:
        ...

    @typing.overload
    def __init__(
        self,
        conn: None = None,
        /,
        *,
        scheme: str,
        username: str | None = None,
        password: str | None = None,
        host: str | None = None,
        port: int | None = None,
        database: str | None = None,
    ) -> None:
        ...

    def __init__(
        self,
        conn: str | None = None,
        /,
        *,
        scheme: str | None = None,
        username: str | None = None,
        password: str | None = None,
        host: str | None = None,
        port: int | None = None,
        database: str | None = None,
    ) -> None:
        """Initialize a database engine URL."""
        # Validate URL format
        if conn is not None:
            if scheme is not None:
                raise ValueError(
                    f"Cannot specify both the URL connection and URL "
                    f"components. Got: conn={conn}, scheme={scheme}."
                )
            # Handle SQLite in-memory and path URLs
            if conn == ':memory:':
                conn = 'sqlite+aiosqlite:///:memory:'
            elif conn.endswith('://'):
                conn += '/:memory:'
            elif ':' not in conn:
                conn = f'sqlite+aiosqlite:///{conn}'
            # Validate URL connection format
            match = re.match(RegexPattern.ENGINE, conn)
            if match is None:
                raise ValueError(
                    f"Invalid database engine URL: {conn!r}. The provided "
                    f"URL connection format must follow the pattern "
                    f"`scheme://[username[:password]@]host[:port]/database`."
                )
            scheme, dialect, driver, \
                username, \
                password, \
                host, \
                port_str, \
                database = match.groups()
            if port_str is not None:
                port = int(port_str)
        else:
            if scheme is None:
                raise ValueError(
                    "Missing database engine URL scheme. Please provide a "
                    "valid URL scheme or URL connection."
                )
            # Validate URL scheme format
            match = re.match(RegexPattern.ENGINE_SCHEME, scheme)
            if not match:
                raise ValueError(
                    f"Invalid database engine URL scheme: {scheme}. The "
                    f"provided URL scheme format must follow the pattern "
                    f"`dialect+driver`."
                )
            _, dialect, driver = match.groups()

        # Validate URL scheme dialect and driver
        if driver is None:
            if dialect not in DEFAULT_DRIVERS:
                raise ValueError(
                    f"No default driver for database engine: {dialect}. "
                    f"Please specify a valid driver in the URL scheme."
                )
            driver = DEFAULT_DRIVERS[dialect]
            scheme = f'{dialect}+{driver}'

        # Validate URL host and database
        if dialect == 'sqlite':
            if host is not None:
                raise ValueError(
                    f"Invalid host for SQLite database engine: {host}. The "
                    f"host must be omitted or set to `None`."
                )
            if database is None:
                raise ValueError(
                    f"Missing database for SQLite database engine. The "
                    f"database must be set to `:memory:` or a valid file path."
                )
        elif host is None:
            raise ValueError(
                f"Missing host for database engine: {dialect}. The host must "
                f"be set to a valid hostname or IP address."
            )

        object.__setattr__(self, 'scheme', scheme)
        object.__setattr__(self, 'username', username)
        object.__setattr__(self, 'password', password)
        object.__setattr__(self, 'host', host)
        object.__setattr__(self, 'port', port)
        object.__setattr__(self, 'database', database)

        # Validate final URL
        if conn is None and not re.match(RegexPattern.ENGINE, str(self)):
            raise ValueError(
                f"Invalid database engine URL: {self}. Please check the URL "
                f"components and try again."
            )

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        __source: type[Any],
        __handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        # Helper function for validating the URL
        def validate(obj: Any) -> Any:
            if isinstance(obj, cls):
                return obj
            if isinstance(obj, dict):
                return cls(**obj)
            return cls(str(obj))

        return core_schema.no_info_plain_validator_function(validate)

    def __repr__(self) -> str:
        return f"EngineUrl('{self}')"

    def __str__(self) -> str:
        url = f'{self.scheme}://'
        if self.username is not None:
            url += self.username
            if self.password is not None:
                url += f':{self.password}'
            url += '@'
        if self.host is not None:
            url += self.host
        if self.port is not None:
            url += f':{self.port}'
        if self.database is not None:
            url += f'/{self.database}'
        return url


class EngineMap(dict[str, EngineUrl]):
    """A database engine URL map type."""

    def __init__(
        self,
        default: str | EngineUrl,
        **kwargs: str | EngineUrl,
    ):
        """Initialize a database engine URL map."""
        engines = {'default': default, **kwargs}
        for key, value in engines.items():
            if isinstance(value, str):
                self[key] = EngineUrl(value)
            else:
                self[key] = value

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        __source: type[Any],
        __handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        # Helper function for validating the URL map
        def validate(obj: Any) -> Any:
            if isinstance(obj, cls):
                return obj
            if isinstance(obj, dict):
                return cls(**obj)
            return cls(str(obj))

        return core_schema.no_info_plain_validator_function(validate)


# MARK: IP

IPvAddressFactoryAlias = Union[
    ipaddress.IPv4Address | ipaddress.IPv6Address | PydanticIPvAnyAddress
]
"""A type alias for the IP address factory type."""


class IPvAddressFactory(BaseTypeFactory[IPvAddressFactoryAlias]):
    """An IP address type factory.

    It extends the built-in `ipaddress.IPv4Address`, `ipaddress.IPv6Address`,
    and pydantic `IPvAnyAddress` classes with additional validation and schema
    methods.
    """

    @classmethod
    def __get_sqlalchemy_data_type__(cls, **kwargs: Any) -> StringEngine:
        return StringEngine(
            length=kwargs.get('max_length', None),
        )

    def __new__(
        cls,
        *,
        version: Literal[4, 6] | None = None,
    ) -> type[IPvAddressFactoryAlias]:
        """Create a new IP address type with the given annotations.

        Args:
            version: The IP address version to validate against.
                Defaults to ``None``.

        Returns:
            The IP address type with the specified constraints.

        Examples:
            >>> IPvAddressFactory(version=4)
            Annotated[ipaddress.IPv4Address, IPvAddressFactory]
        """
        type_: type[IPvAddressFactoryAlias] | None
        if version == 4:
            type_ = ipaddress.IPv4Address
        elif version == 6:
            type_ = ipaddress.IPv6Address
        else:
            type_ = PydanticIPvAnyAddress

        return super().__new__(
            cls,
            type_=type_,
            force_build=True,
        )


if typing.TYPE_CHECKING:
    IPvAnyAddress = Annotated[PydanticIPvAnyAddress, ...]
    """The IP address proxy."""

    IPv4Address = Annotated[ipaddress.IPv4Address, ...]
    """An IPv4 address proxy."""

    IPv6Address = Annotated[ipaddress.IPv6Address, ...]
    """An IPv6 address proxy."""

else:
    IPvAnyAddress = IPvAddressFactory()
    IPv4Address = IPvAddressFactory(version=4)
    IPv6Address = IPvAddressFactory(version=6)


IPvInterfaceFactoryAlias = Union[
    ipaddress.IPv4Interface | ipaddress.IPv6Interface | PydanticIPvAnyInterface
]
"""A type alias for the IP interface factory type."""


class IPvInterfaceFactory(BaseTypeFactory[IPvInterfaceFactoryAlias]):
    """An IP interface type factory.

    It extends the built-in `ipaddress.IPv4Interface`,
    `ipaddress.IPv6Interface`, and pydantic `IPvAnyInterface` classes with
    additional validation and schema methods.
    """

    @classmethod
    def __get_sqlalchemy_data_type__(cls, **kwargs: Any) -> StringEngine:
        return StringEngine(
            length=kwargs.get('max_length', None),
        )

    def __new__(
        cls,
        *,
        version: Literal[4, 6] | None = None,
    ) -> type[IPvInterfaceFactoryAlias]:
        """Create a new IP interface type with the given annotations.

        Args:
            version: The IP interface version to validate against.
                Defaults to ``None``.

        Returns:
            The IP interface type with the specified constraints.

        Examples:
            >>> IPvInterfaceFactory(version=4)
            Annotated[ipaddress.IPv4Interface, IPvInterfaceFactory]
        """
        type_: type[IPvInterfaceFactoryAlias] | None
        if version == 4:
            type_ = ipaddress.IPv4Interface
        elif version == 6:
            type_ = ipaddress.IPv6Interface
        else:
            type_ = PydanticIPvAnyInterface

        return super().__new__(
            cls,
            type_=type_,
            force_build=True,
        )


if typing.TYPE_CHECKING:
    IPvAnyInterface = Annotated[PydanticIPvAnyInterface, ...]
    """The IP interface proxy."""

    IPv4Interface = Annotated[ipaddress.IPv4Interface, ...]
    """An IPv4 interface proxy."""

    IPv6Interface = Annotated[ipaddress.IPv6Interface, ...]
    """An IPv6 interface proxy."""

else:
    IPvAnyInterface = IPvInterfaceFactory()
    IPv4Interface = IPvInterfaceFactory(version=4)
    IPv6Interface = IPvInterfaceFactory(version=6)


IPvNetworkFactoryAlias = Union[
    ipaddress.IPv4Network | ipaddress.IPv6Network | PydanticIPvAnyNetwork
]
"""A type alias for the IP network factory type."""


class IPvNetworkFactory(BaseTypeFactory[IPvNetworkFactoryAlias]):
    """An IP network type factory.

    It extends the built-in `ipaddress.IPv4Network`, `ipaddress.IPv6Network`,
    and pydantic `IPvAnyNetwork` classes with additional validation and schema
    methods.
    """

    @classmethod
    def __get_sqlalchemy_data_type__(cls, **kwargs: Any) -> StringEngine:
        return StringEngine(
            length=kwargs.get('max_length', None),
        )

    def __new__(
        cls,
        *,
        version: Literal[4, 6] | None = None,
    ) -> type[IPvNetworkFactoryAlias]:
        """Create a new IP network type with the given annotations.

        Args:
            version: The IP network version to validate against.
                Defaults to ``None``.

        Returns:
            The IP network type with the specified constraints.

        Examples:
            >>> IPvNetworkFactory(version=4)
            Annotated[ipaddress.IPv4Network, IPvNetworkFactory]
        """
        type_: type[IPvNetworkFactoryAlias] | None
        if version == 4:
            type_ = ipaddress.IPv4Network
        elif version == 6:
            type_ = ipaddress.IPv6Network
        else:
            type_ = PydanticIPvAnyNetwork

        return super().__new__(
            cls,
            type_=type_,
            force_build=True,
        )


if typing.TYPE_CHECKING:
    IPvAnyNetwork = Annotated[PydanticIPvAnyNetwork, ...]
    """The IP network proxy."""

    IPv4Network = Annotated[ipaddress.IPv4Network, ...]
    """An IPv4 network proxy."""

    IPv6Network = Annotated[ipaddress.IPv6Network, ...]
    """An IPv6 network proxy."""

else:
    IPvAnyNetwork = IPvNetworkFactory()
    IPv4Network = IPvNetworkFactory(version=4)
    IPv6Network = IPvNetworkFactory(version=6)


# MARK: URL

class UrlFactory(BaseTypeFactory[PydanticUrl]):
    """A URL type factory.

    It extends the pydantic `Url` class with additional validation and schema
    methods.
    """

    @classmethod
    def __get_sqlalchemy_data_type__(cls, **kwargs: Any) -> StringEngine:
        return StringEngine(
            length=kwargs.get('max_length', None),
        )

    def __new__(
        cls,
        max_length: int | None = None,
        allowed_schemes: list[str] | None = None,
        host_required: bool | None = None,
        default_host: str | None = None,
        default_port: int | None = None,
        default_path: str | None = None,
    ) -> type[PydanticUrl]:
        """Create a new URL type with constraints validation.

        Args:
            max_length: The maximum length of the URL. Defaults to `None`.
            allowed_schemes: The allowed schemes. Defaults to `None`.
            host_required: Whether the host is required. Defaults to `None`.
            default_host: The default host. Defaults to `None`.
            default_port: The default port. Defaults to `None`.
            default_path: The default path. Defaults to `None`.

        Returns:
            The URL type with the specified constraints.

        Examples:
            >>> UrlFactory(max_length=2083)
            Annotated[Url, UrlFactory, UrlConstraints(max_length=2083)]
        """
        return super().__new__(
            cls,
            UrlConstraints(
                max_length=max_length,
                allowed_schemes=allowed_schemes,
                host_required=host_required,
                default_host=default_host,
                default_port=default_port,
                default_path=default_path,
            ),
            force_build=True,
        )


if typing.TYPE_CHECKING:
    AnyUrl = Annotated[PydanticUrl, ...]
    """The URL proxy."""

    AnyHttpUrl = Annotated[PydanticUrl, ...]
    """A URL that must implement the HTTP scheme."""

    HttpUrl = Annotated[PydanticUrl, ...]
    """A URL that must implement the HTTP scheme with 2083 max length."""

    FileUrl = Annotated[PydanticUrl, ...]
    """A URL that must implement the file scheme."""

    AmqpDsn = Annotated[PydanticUrl, ...]
    """An AMQP DSN URL."""

    CockroachDsn = Annotated[PydanticUrl, ...]
    """A CockroachDB DSN URL."""

    KafkaDsn = Annotated[PydanticUrl, ...]
    """A Kafka DSN URL."""

    MariaDBDsn = Annotated[PydanticUrl, ...]
    """A MariaDB DSN URL."""

    MySQLDsn = Annotated[PydanticUrl, ...]
    """A MySQL DSN URL."""

    OracleDsn = Annotated[PydanticUrl, ...]
    """An Oracle DSN URL."""

    RedisDsn = Annotated[PydanticUrl, ...]
    """A Redis DSN URL."""

    SQLiteDsn = Annotated[PydanticUrl, ...]
    """A SQLite DSN URL."""

    SQLServerDsn = Annotated[PydanticUrl, ...]
    """A SQL Server DSN URL."""

else:
    AnyUrl = UrlFactory()
    AnyHttpUrl = UrlFactory(allowed_schemes=['http', 'https'])
    HttpUrl = UrlFactory(max_length=2083, allowed_schemes=['http', 'https'])
    FileUrl = UrlFactory(allowed_schemes=['file'])

    AmqpDsn = UrlFactory(allowed_schemes=['amqp', 'amqps'])
    CockroachDsn = UrlFactory(
        allowed_schemes=[
            'cockroachdb',
            'cockroachdb+psycopg2',
            'cockroachdb+asyncpg',
        ],
        host_required=True,
    )
    KafkaDsn = UrlFactory(
        allowed_schemes=['kafka'],
        default_host='localhost',
        default_port=9092,
    )
    MariaDBDsn = UrlFactory(
        allowed_schemes=[
            'mariadb',
            'mariadb+aiomysql',
            'mariadb+asyncmy',
            'mariadb+mariadbconnector',
            'mariadb+pymysql',
        ],
        default_port=3306,
    )
    MySQLDsn = UrlFactory(
        allowed_schemes=[
            'mysql',
            'mysql+mysqlconnector',
            'mysql+aiomysql',
            'mysql+asyncmy',
            'mysql+mysqldb',
            'mysql+pymysql',
            'mysql+cymysql',
            'mysql+pyodbc',
        ],
        default_port=3306,
    )
    OracleDsn = UrlFactory(
        allowed_schemes=[
            'oracle',
            'oracle+oracledb',
            'oracle+cx_oracle',
        ],
        host_required=True,
        default_port=1521,
    )
    RedisDsn = UrlFactory(
        allowed_schemes=['redis', 'rediss'],
        default_host='localhost',
        default_port=6379,
        default_path='/0',
    )
    SQLiteDsn = UrlFactory(
        allowed_schemes=[
            'sqlite',
            'sqlite+aiosqlite',
            'sqlite+pysqlcipher',
            'sqlite+pysqlite',
        ],
    )
    SQLServerDsn = UrlFactory(
        allowed_schemes=[
            'mssql',
            'mssql+aioodbc',
            'mssql+pyodbc',
            'mssql+pymssql',
        ],
        host_required=True,
        default_port=1433,
    )


class MultiHostUrlFactory(BaseTypeFactory[PydanticMultiHostUrl]):
    """A multi host URL type factory.

    It extends the pydantic `MultiHostUrl` class with additional validation and
    schema methods.
    """

    @classmethod
    def __get_sqlalchemy_data_type__(cls, **kwargs: Any) -> StringEngine:
        return StringEngine(
            length=kwargs.get('max_length', None),
        )

    def __new__(
        cls,
        max_length: int | None = None,
        allowed_schemes: list[str] | None = None,
        host_required: bool | None = None,
        default_host: str | None = None,
        default_port: int | None = None,
        default_path: str | None = None,
    ) -> type[PydanticMultiHostUrl]:
        """Create a new multi host URL type with constraints validation.

        Args:
            max_length: The maximum length of the URL. Defaults to `None`.
            allowed_schemes: The allowed schemes. Defaults to `None`.
            host_required: Whether the host is required. Defaults to `None`.
            default_host: The default host. Defaults to `None`.
            default_port: The default port. Defaults to `None`.
            default_path: The default path. Defaults to `None`.

        Returns:
            The multi host URL type with the specified constraints.

        Examples:
            >>> MultiHostUrlFactory(max_length=2083)
            Annotated[
                MultiHostUrl,
                MultiHostUrlFactory,
                UrlConstraints(max_length=2083),
            ]
        """
        return super().__new__(
            cls,
            UrlConstraints(
                max_length=max_length,
                allowed_schemes=allowed_schemes,
                host_required=host_required,
                default_host=default_host,
                default_port=default_port,
                default_path=default_path,
            ),
            force_build=True,
        )


if typing.TYPE_CHECKING:
    AnyMultiHostUrl = Annotated[PydanticMultiHostUrl, ...]
    """The multi host URL proxy."""

    MongoDsn = Annotated[PydanticMultiHostUrl, ...]
    """A MongoDB DSN URL."""

    NatsDsn = Annotated[PydanticMultiHostUrl, ...]
    """A NATS DSN URL."""

    PostgresDsn = Annotated[PydanticMultiHostUrl, ...]
    """A PostgreSQL DSN URL."""

else:
    AnyMultiHostUrl = MultiHostUrlFactory()

    MongoDsn = MultiHostUrlFactory(
        allowed_schemes=['mongodb', 'mongodb+srv'],
        default_port=27017,
    )
    NatsDsn = MultiHostUrlFactory(
        allowed_schemes=['nats', 'tls', 'ws'],
        default_host='localhost',
        default_port=4222,
    )
    PostgresDsn = MultiHostUrlFactory(
        allowed_schemes=[
            'postgres',
            'postgresql',
            'postgresql+asyncpg',
            'postgresql+pg8000',
            'postgresql+psycopg',
            'postgresql+psycopg2',
            'postgresql+psycopg2cffi',
            'postgresql+py-postgresql',
            'postgresql+pygresql',
        ],
        host_required=True,
    )
