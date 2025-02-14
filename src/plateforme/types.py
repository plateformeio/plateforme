# plateforme.types
# ----------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing types within the Plateforme
framework leveraging Pydantic schemas for validation and serialization, and
compatibility with SQLAlchemy's data type system. It is a proxy module for the
core types package that provides a clean and simple interface for developers to
interact with the framework's types features.
"""

# Base
from .core.types.base import BaseType, BaseTypeFactory
from .core.types.binaries import Binary, BinaryFactory, StrictBinary
from .core.types.datetimes import (
    AwareDateTime,
    Date,
    DateFactory,
    DateTime,
    DateTimeFactory,
    FutureDate,
    FutureDateTime,
    NaiveDateTime,
    PastDate,
    PastDateTime,
    StrictDate,
    StrictDateTime,
    StrictTime,
    StrictTimeDelta,
    Time,
    TimeDelta,
    TimeDeltaFactory,
    TimeFactory,
)
from .core.types.enums import Enum, EnumFactory, StrictEnum
from .core.types.json import Json
from .core.types.networks import (
    AmqpDsn,
    AnyHttpUrl,
    AnyMultiHostUrl,
    AnyUrl,
    CockroachDsn,
    Email,
    EngineMap,
    EngineUrl,
    FileUrl,
    HttpUrl,
    IPv4Address,
    IPv4Interface,
    IPv4Network,
    IPv6Address,
    IPv6Interface,
    IPv6Network,
    IPvAddressFactory,
    IPvAnyAddress,
    IPvAnyInterface,
    IPvAnyNetwork,
    IPvInterfaceFactory,
    IPvNetworkFactory,
    KafkaDsn,
    MariaDBDsn,
    MongoDsn,
    MySQLDsn,
    NameEmail,
    NatsDsn,
    OracleDsn,
    PostgresDsn,
    RedisDsn,
    SQLiteDsn,
    SQLServerDsn,
    UrlFactory,
)
from .core.types.numbers import (
    AllowInfNan,
    Boolean,
    BooleanFactory,
    Decimal,
    DecimalFactory,
    FiniteDecimal,
    FiniteFloat,
    Float,
    FloatFactory,
    Integer,
    IntegerFactory,
    NegativeDecimal,
    NegativeFloat,
    NegativeInteger,
    NonNegativeDecimal,
    NonNegativeFloat,
    NonNegativeInteger,
    NonPositiveDecimal,
    NonPositiveFloat,
    NonPositiveInteger,
    PositiveDecimal,
    PositiveFloat,
    PositiveInteger,
    StrictBoolean,
    StrictDecimal,
    StrictFloat,
    StrictInteger,
)
from .core.types.paths import AnyPath, DirectoryPath, FilePath, NewPath
from .core.types.secrets import SecretBytes, SecretStr
from .core.types.strings import StrictString, String, StringFactory
from .core.types.uuid import UUID, UUID1, UUID3, UUID4, UUID5, UuidFactory

__all__ = (
    # Base
    'BaseType',
    'BaseTypeFactory',
    # Binaries
    'Binary',
    'BinaryFactory',
    'StrictBinary',
    # Dates
    'AwareDateTime',
    'Date',
    'DateFactory',
    'DateTime',
    'DateTimeFactory',
    'FutureDate',
    'FutureDateTime',
    'NaiveDateTime',
    'PastDate',
    'PastDateTime',
    'StrictDate',
    'StrictDateTime',
    'StrictTime',
    'StrictTimeDelta',
    'Time',
    'TimeDelta',
    'TimeDeltaFactory',
    'TimeFactory',
    # Enums
    'Enum',
    'EnumFactory',
    'StrictEnum',
    # Json
    'Json',
    # Networks
    'AmqpDsn',
    'AnyHttpUrl',
    'AnyMultiHostUrl',
    'AnyUrl',
    'CockroachDsn',
    'Email',
    'EngineMap',
    'EngineUrl',
    'FileUrl',
    'HttpUrl',
    'IPv4Address',
    'IPv4Interface',
    'IPv4Network',
    'IPv6Address',
    'IPv6Interface',
    'IPv6Network',
    'IPvAddressFactory',
    'IPvAnyAddress',
    'IPvAnyInterface',
    'IPvAnyNetwork',
    'IPvInterfaceFactory',
    'IPvNetworkFactory',
    'KafkaDsn',
    'MariaDBDsn',
    'MongoDsn',
    'MySQLDsn',
    'NameEmail',
    'NatsDsn',
    'OracleDsn',
    'PostgresDsn',
    'RedisDsn',
    'SQLiteDsn',
    'SQLServerDsn',
    'UrlFactory',
    # Numbers
    'AllowInfNan',
    'Boolean',
    'BooleanFactory',
    'Decimal',
    'DecimalFactory',
    'FiniteDecimal',
    'FiniteFloat',
    'Float',
    'FloatFactory',
    'Integer',
    'IntegerFactory',
    'NegativeDecimal',
    'NegativeFloat',
    'NegativeInteger',
    'NonNegativeDecimal',
    'NonNegativeFloat',
    'NonNegativeInteger',
    'NonPositiveDecimal',
    'NonPositiveFloat',
    'NonPositiveInteger',
    'PositiveDecimal',
    'PositiveFloat',
    'PositiveInteger',
    'StrictBoolean',
    'StrictDecimal',
    'StrictFloat',
    'StrictInteger',
    # Paths
    'AnyPath',
    'DirectoryPath',
    'FilePath',
    'NewPath',
    # Secrets
    'SecretBytes',
    'SecretStr',
    # Strings
    'StrictString',
    'String',
    'StringFactory',
    # UUID
    'UUID',
    'UUID1',
    'UUID3',
    'UUID4',
    'UUID5',
    'UuidFactory'
)
