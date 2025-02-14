# plateforme
# ----------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
The modern ASGI framework for data-driven applications.

The Plateforme framework provides a suite of tools and components to support
the rapid development of data-driven applications. It includes a collection of
modules that offer a wide range of functionalities, from environment setup to
data modeling, resource management, and API deployment.

Examples:
    >>> from plateforme import Plateforme, BaseResource, Field, route
    ...
    >>> app = Plateforme()
    ...
    >>> class MyResource(BaseResource):
    ...     name: str = Field(unique=True)
    ...
    ...     @route.post()
    ...     def hello(self, name: str) -> str:
    ...         return f'Hello {self.name}!'
"""

import typing

from . import framework
from .core import runtime

__version__ = framework.VERSION


# MARK: Type Checking

if typing.TYPE_CHECKING:
    from .core.api.background import BackgroundTasks
    from .core.api.datastructures import UploadFile
    from .core.api.dependencies import AsyncSessionDep, SessionDep
    from .core.api.exceptions import HTTPException, WebSocketException
    from .core.api.parameters import (
        Body,
        Cookie,
        Depends,
        File,
        Form,
        Header,
        Path,
        Payload,
        Query,
        Security,
        Selection,
    )
    from .core.api.requests import Request
    from .core.api.responses import Response
    from .core.api.routing import route
    from .core.api.status import status
    from .core.api.websockets import WebSocket, WebSocketDisconnect
    from .core.config import ConfigDict, with_config
    from .core.database.base import inspect as inspect
    from .core.database.expressions import (
        alias,
        all_,
        and_,
        any_,
        asc,
        between,
        bindparam,
        case,
        cast,
        collate,
        column,
        cte,
        delete,
        desc,
        distinct,
        except_,
        except_all,
        exists,
        extract,
        false,
        func,
        funcfilter,
        insert,
        intersect,
        intersect_all,
        join,
        label,
        lambda_stmt,
        lateral,
        literal,
        literal_column,
        modifier,
        not_,
        null,
        nulls_first,
        nulls_last,
        nullsfirst,
        nullslast,
        or_,
        outerjoin,
        outparam,
        over,
        select,
        table,
        tablesample,
        text,
        true,
        tuple_,
        type_coerce,
        union,
        union_all,
        update,
        values,
        within_group,
    )
    from .core.database.routing import DatabaseRouter as DatabaseRouter
    from .core.database.sessions import (
        async_session_factory,
        async_session_manager,
        session_factory,
        session_manager,
    )
    from .core.environment import Environment
    from .core.expressions import Condition, Filter, Ordering, Sort
    from .core.main import Plateforme
    from .core.mixins import Archivable, Auditable, Encrypted
    from .core.resources import (
        BaseResource,
        CRUDResource,
        ResourceConfig,
        ResourceIndex,
    )
    from .core.schema import core as core_schema
    from .core.schema.aliases import AliasChoices, AliasGenerator, AliasPath
    from .core.schema.core import (
        GetCoreSchemaHandler,
        GetJsonSchemaHandler,
        SerializationInfo,
        ValidationError,
        ValidationInfo,
        ValidationMode,
    )
    from .core.schema.decorators import (
        AfterValidator,
        BeforeValidator,
        InstanceOf,
        PlainSerializer,
        PlainValidator,
        RecursiveGuard,
        SerializeAsAny,
        SkipValidation,
        WrapSerializer,
        WrapValidator,
        field_serializer,
        field_validator,
        model_serializer,
        model_validator,
        validate_call,
    )
    from .core.schema.fields import Field, PrivateAttr, computed_field
    from .core.schema.json import (
        GenerateJsonSchema,
        JsonEncoder,
        JsonSchemaDict,
        JsonSchemaExtra,
        JsonSchemaExtraCallable,
        JsonSchemaMode,
        JsonSchemaSource,
        JsonSchemaValue,
    )
    from .core.schema.models import (
        BaseModel,
        DiscriminatedModel,
        ModelConfig,
        RootModel,
        collect_fields,
        collect_models,
        create_discriminated_model,
        create_model,
        create_root_model,
    )
    from .core.schema.types import (
        Discriminator,
        OneOrMany,
        Schema,
        Strict,
        Tag,
        TypeAdapter,
        TypeAdapterList,
    )
    from .core.selectors import BaseSelector, Key, KeyList
    from .core.services import (
        BaseService,
        BaseServiceWithSpec,
        CRUDService,
        ServiceConfig,
    )
    from .core.settings import (
        APIRouterSettings,
        APISettings,
        LoggingSettings,
        NamespaceSettings,
        PackageSettings,
        Settings,
    )
    from .core.specs import BaseSpec, CRUDSpec
    from .core.types.binaries import Binary, StrictBinary
    from .core.types.datetimes import (
        AwareDateTime,
        Date,
        DateTime,
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
    )
    from .core.types.enums import Enum, StrictEnum
    from .core.types.json import Json
    from .core.types.networks import (
        AmqpDsn,
        AnyHttpUrl,
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
        IPvAnyAddress,
        IPvAnyInterface,
        IPvAnyNetwork,
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
    )
    from .core.types.numbers import (
        AllowInfNan,
        Boolean,
        Decimal,
        FiniteDecimal,
        FiniteFloat,
        Float,
        Integer,
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
    from .core.types.strings import StrictString, String
    from .core.types.uuid import UUID, UUID1, UUID3, UUID4, UUID5


# MARK: Exports

__all__ = (
    'framework',
    'runtime',
    # API (background)
    'BackgroundTasks',
    # API (datastructures)
    'UploadFile',
    # API (dependencies)
    'AsyncSessionDep',
    'SessionDep',
    # API (exceptions)
    'HTTPException',
    'WebSocketException',
    # API (parameters)
    'Body',
    'Cookie',
    'Depends',
    'File',
    'Form',
    'Header',
    'Path',
    'Payload',
    'Query',
    'Security',
    'Selection',
    # API (requests)
    'Request',
    # API (responses)
    'Response',
    # API (routing)
    'route',
    # API (status)
    'status',
    # API (websockets)
    'WebSocket',
    'WebSocketDisconnect',
    # Database (base)
    'inspect',
    # Database (expressions)
    'alias',
    'all_',
    'and_',
    'any_',
    'asc',
    'between',
    'bindparam',
    'case',
    'cast',
    'collate',
    'column',
    'cte',
    'delete',
    'desc',
    'distinct',
    'except_',
    'except_all',
    'exists',
    'extract',
    'false',
    'func',
    'funcfilter',
    'insert',
    'intersect',
    'intersect_all',
    'join',
    'label',
    'lambda_stmt',
    'lateral',
    'literal',
    'literal_column',
    'modifier',
    'not_',
    'null',
    'nulls_first',
    'nulls_last',
    'nullsfirst',
    'nullslast',
    'or_',
    'outerjoin',
    'outparam',
    'over',
    'select',
    'table',
    'tablesample',
    'text',
    'true',
    'tuple_',
    'type_coerce',
    'union',
    'union_all',
    'update',
    'values',
    'within_group',
    # Database (routing)
    'DatabaseRouter',
    # Database (sessions)
    'async_session_factory',
    'async_session_manager',
    'session_factory',
    'session_manager',
    # Core (config)
    'ConfigDict',
    'with_config',
    # Core (environment)
    'Environment',
    # Core (expressions)
    'Condition',
    'Filter',
    'Ordering',
    'Sort',
    # Core (main)
    'Plateforme',
    # Core (mixins)
    'Archivable',
    'Auditable',
    'Encrypted',
    # Core (resources)
    'BaseResource',
    'CRUDResource',
    'ResourceConfig',
    'ResourceIndex',
    # Core (selectors)
    'BaseSelector',
    'Key',
    'KeyList',
    # Core (services)
    'BaseService',
    'BaseServiceWithSpec',
    'CRUDService',
    'ServiceConfig',
    # Core (specifications)
    'BaseSpec',
    'CRUDSpec',
    # Schema (Aliases)
    'AliasChoices',
    'AliasGenerator',
    'AliasPath',
    # Schema (core)
    'core_schema',
    'GetCoreSchemaHandler',
    'GetJsonSchemaHandler',
    'SerializationInfo',
    'ValidationError',
    'ValidationMode',
    'ValidationInfo',
    # Schema (decorators)
    'AfterValidator',
    'BeforeValidator',
    'InstanceOf',
    'PlainSerializer',
    'PlainValidator',
    'RecursiveGuard',
    'SerializeAsAny',
    'SkipValidation',
    'WrapSerializer',
    'WrapValidator',
    'field_serializer',
    'field_validator',
    'model_serializer',
    'model_validator',
    'validate_call',
    # Schema (fields)
    'Field',
    'PrivateAttr',
    'computed_field',
    # Schema (json)
    'GenerateJsonSchema',
    'JsonEncoder',
    'JsonSchemaDict',
    'JsonSchemaExtra',
    'JsonSchemaExtraCallable',
    'JsonSchemaMode',
    'JsonSchemaSource',
    'JsonSchemaValue',
    # Schema (models)
    'BaseModel',
    'DiscriminatedModel',
    'ModelConfig',
    'RootModel',
    'collect_fields',
    'collect_models',
    'create_discriminated_model',
    'create_model',
    'create_root_model',
    # Schema (types)
    'Discriminator',
    'OneOrMany',
    'Schema',
    'Strict',
    'Tag',
    'TypeAdapter',
    'TypeAdapterList',
    # Settings
    'APIRouterSettings',
    'APISettings',
    'LoggingSettings',
    'NamespaceSettings',
    'PackageSettings',
    'Settings',
    # Types (binaries)
    'Binary',
    'StrictBinary',
    # Types (dates)
    'AwareDateTime',
    'Date',
    'DateTime',
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
    # Types (enums)
    'Enum',
    'StrictEnum',
    # Types (json)
    'Json',
    # Types (networks)
    'AmqpDsn',
    'AnyUrl',
    'AnyHttpUrl',
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
    'IPvAnyAddress',
    'IPvAnyInterface',
    'IPvAnyNetwork',
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
    # Types (numbers)
    'AllowInfNan',
    'Boolean',
    'Decimal',
    'FiniteDecimal',
    'FiniteFloat',
    'Float',
    'Integer',
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
    # Types (paths)
    'AnyPath',
    'DirectoryPath',
    'FilePath',
    'NewPath',
    # Types (secrets)
    'SecretBytes',
    'SecretStr',
    # Types (strings)
    'StrictString',
    'String',
    # Types (uuid)
    'UUID',
    'UUID1',
    'UUID3',
    'UUID4',
    'UUID5',
)


# MARK: Dynamic Imports

__all_dynamic__: dict[str, tuple[str | None, str]] = {
    # API (background)
    'BackgroundTasks': (None, '.core.api.background'),
    # API (datastructures)
    'UploadFile': (None, '.core.api.datastructures'),
    # Core (dependencies)
    'AsyncSessionDep': (None, '.core.api.dependencies'),
    'SessionDep': (None, '.core.api.dependencies'),
    # API (exceptions)
    'HTTPException': (None, '.core.api.exceptions'),
    'WebSocketException': (None, '.core.api.exceptions'),
    # API (parameters)
    'Body': (None, '.core.api.parameters'),
    'Cookie': (None, '.core.api.parameters'),
    'Depends': (None, '.core.api.parameters'),
    'File': (None, '.core.api.parameters'),
    'Form': (None, '.core.api.parameters'),
    'Header': (None, '.core.api.parameters'),
    'Path': (None, '.core.api.parameters'),
    'Payload': (None, '.core.api.parameters'),
    'Query': (None, '.core.api.parameters'),
    'Security': (None, '.core.api.parameters'),
    'Selection': (None, '.core.api.parameters'),
    # API (requests)
    'Request': (None, '.core.api.requests'),
    # API (responses)
    'Response': (None, '.core.api.responses'),
    # API (routing)
    'route': (None, '.core.api.routing'),
    # API (status)
    'status': (None, '.core.api.status'),
    # API (websockets)
    'WebSocket': (None, '.core.api.websockets'),
    'WebSocketDisconnect': (None, '.core.api.websockets'),
    # Database (base)
    'inspect': (None, '.core.database.base'),
    # Database (expressions)
    'alias': (None, '.core.database.expressions'),
    'all_': (None, '.core.database.expressions'),
    'and_': (None, '.core.database.expressions'),
    'any_': (None, '.core.database.expressions'),
    'asc': (None, '.core.database.expressions'),
    'between': (None, '.core.database.expressions'),
    'bindparam': (None, '.core.database.expressions'),
    'case': (None, '.core.database.expressions'),
    'cast': (None, '.core.database.expressions'),
    'collate': (None, '.core.database.expressions'),
    'column': (None, '.core.database.expressions'),
    'cte': (None, '.core.database.expressions'),
    'delete': (None, '.core.database.expressions'),
    'desc': (None, '.core.database.expressions'),
    'distinct': (None, '.core.database.expressions'),
    'except_': (None, '.core.database.expressions'),
    'except_all': (None, '.core.database.expressions'),
    'exists': (None, '.core.database.expressions'),
    'extract': (None, '.core.database.expressions'),
    'false': (None, '.core.database.expressions'),
    'func': (None, '.core.database.expressions'),
    'funcfilter': (None, '.core.database.expressions'),
    'insert': (None, '.core.database.expressions'),
    'intersect': (None, '.core.database.expressions'),
    'intersect_all': (None, '.core.database.expressions'),
    'join': (None, '.core.database.expressions'),
    'label': (None, '.core.database.expressions'),
    'lambda_stmt': (None, '.core.database.expressions'),
    'lateral': (None, '.core.database.expressions'),
    'literal': (None, '.core.database.expressions'),
    'literal_column': (None, '.core.database.expressions'),
    'modifier': (None, '.core.database.expressions'),
    'not_': (None, '.core.database.expressions'),
    'null': (None, '.core.database.expressions'),
    'nulls_first': (None, '.core.database.expressions'),
    'nulls_last': (None, '.core.database.expressions'),
    'nullsfirst': (None, '.core.database.expressions'),
    'nullslast': (None, '.core.database.expressions'),
    'or_': (None, '.core.database.expressions'),
    'outerjoin': (None, '.core.database.expressions'),
    'outparam': (None, '.core.database.expressions'),
    'over': (None, '.core.database.expressions'),
    'select': (None, '.core.database.expressions'),
    'table': (None, '.core.database.expressions'),
    'tablesample': (None, '.core.database.expressions'),
    'text': (None, '.core.database.expressions'),
    'true': (None, '.core.database.expressions'),
    'tuple_': (None, '.core.database.expressions'),
    'type_coerce': (None, '.core.database.expressions'),
    'union': (None, '.core.database.expressions'),
    'union_all': (None, '.core.database.expressions'),
    'update': (None, '.core.database.expressions'),
    'values': (None, '.core.database.expressions'),
    'within_group': (None, '.core.database.expressions'),
    # Database (routing)
    'DatabaseRouter': (None, '.core.database.routing'),
    # Database (sessions)
    'async_session_factory': (None, '.core.database.sessions'),
    'async_session_manager': (None, '.core.database.sessions'),
    'session_factory': (None, '.core.database.sessions'),
    'session_manager': (None, '.core.database.sessions'),
    # Core (config)
    'ConfigDict': (None, '.core.config'),
    'with_config': (None, '.core.config'),
    # Core (environment)
    'Environment': (None, '.core.environment'),
    # Core (expressions)
    'Condition': (None, '.core.expressions'),
    'Filter': (None, '.core.expressions'),
    'Ordering': (None, '.core.expressions'),
    'Sort': (None, '.core.expressions'),
    # Core (main)
    'Plateforme': (None, '.core.main'),
    # Core (mixins)
    'Archivable': (None, '.core.mixins'),
    'Auditable': (None, '.core.mixins'),
    'Encrypted': (None, '.core.mixins'),
    # Core (resources)
    'BaseResource': (None, '.core.resources'),
    'CRUDResource': (None, '.core.resources'),
    'ResourceConfig': (None, '.core.resources'),
    'ResourceIndex': (None, '.core.resources'),
    # Core (selectors)
    'BaseSelector': (None, '.core.selectors'),
    'Key': (None, '.core.selectors'),
    'KeyList': (None, '.core.selectors'),
    # Core (services)
    'BaseService': (None, '.core.services'),
    'BaseServiceWithSpec': (None, '.core.services'),
    'CRUDService': (None, '.core.services'),
    'ServiceConfig': (None, '.core.services'),
    # Core (specifications)
    'BaseSpec': (None, '.core.specs'),
    'CRUDSpec': (None, '.core.specs'),
    # Schema (aliases)
    'AliasChoices': (None, '.core.schema.aliases'),
    'AliasGenerator': (None, '.core.schema.aliases'),
    'AliasPath': (None, '.core.schema.aliases'),
    # Schema (core)
    'core_schema': ('pydantic_core', '__module__'),
    'GetCoreSchemaHandler': (None, '.core.schema.core'),
    'GetJsonSchemaHandler': (None, '.core.schema.core'),
    'SerializationInfo': (None, '.core.schema.core'),
    'ValidationError': (None, '.core.schema.core'),
    'ValidationMode': (None, '.core.schema.core'),
    'ValidationInfo': (None, '.core.schema.core'),
    # Schema (decorators)
    'AfterValidator': (None, '.core.schema.decorators'),
    'BeforeValidator': (None, '.core.schema.decorators'),
    'InstanceOf': (None, '.core.schema.decorators'),
    'PlainSerializer': (None, '.core.schema.decorators'),
    'PlainValidator': (None, '.core.schema.decorators'),
    'RecursiveGuard': (None, '.core.schema.decorators'),
    'SerializeAsAny': (None, '.core.schema.decorators'),
    'SkipValidation': (None, '.core.schema.moddecoratorsels'),
    'WrapSerializer': (None, '.core.schema.decorators'),
    'WrapValidator': (None, '.core.schema.decorators'),
    'field_serializer': (None, '.core.schema.decorators'),
    'field_validator': (None, '.core.schema.decorators'),
    'model_serializer': (None, '.core.schema.decorators'),
    'model_validator': (None, '.core.schema.decorators'),
    'validate_call': (None, '.core.schema.decorators'),
    # Schema (fields)
    'Field': (None, '.core.schema.fields'),
    'PrivateAttr': (None, '.core.schema.fields'),
    'computed_field': (None, '.core.schema.fields'),
    # Schema (json)
    'GenerateJsonSchema': (None, '.core.schema.json'),
    'JsonEncoder': (None, '.core.schema.json'),
    'JsonSchemaDict': (None, '.core.schema.json'),
    'JsonSchemaExtra': (None, '.core.schema.json'),
    'JsonSchemaExtraCallable': (None, '.core.schema.json'),
    'JsonSchemaMode': (None, '.core.schema.json'),
    'JsonSchemaSource': (None, '.core.schema.json'),
    'JsonSchemaValue': (None, '.core.schema.json'),
    # Schema (models)
    'BaseModel': (None, '.core.schema.models'),
    'DiscriminatedModel': (None, '.core.schema.models'),
    'ModelConfig': (None, '.core.schema.models'),
    'RootModel': (None, '.core.schema.models'),
    'collect_fields': (None, '.core.schema.models'),
    'collect_models': (None, '.core.schema.models'),
    'create_discriminated_model': (None, '.core.schema.models'),
    'create_model': (None, '.core.schema.models'),
    'create_root_model': (None, '.core.schema.models'),
    # Schema (types)
    'Discriminator': (None, '.core.schema.types'),
    'OneOrMany': (None, '.core.schema.types'),
    'Schema': (None, '.core.schema.types'),
    'Strict': (None, '.core.schema.types'),
    'Tag': (None, '.core.schema.types'),
    'TypeAdapter': (None, '.core.schema.types'),
    'TypeAdapterList': (None, '.core.schema.types'),
    # Settings
    'APIRouterSettings': (None, '.core.settings'),
    'APISettings': (None, '.core.settings'),
    'LoggingSettings': (None, '.core.settings'),
    'NamespaceSettings': (None, '.core.settings'),
    'PackageSettings': (None, '.core.settings'),
    'Settings': (None, '.core.settings'),
    # Types (binaries)
    'Binary': (None, '.core.types.binaries'),
    'StrictBinary': (None, '.core.types.binaries'),
    # Types (dates)
    'AwareDateTime': (None, '.core.types.datetimes'),
    'Date': (None, '.core.types.datetimes'),
    'DateTime': (None, '.core.types.datetimes'),
    'FutureDate': (None, '.core.types.datetimes'),
    'FutureDateTime': (None, '.core.types.datetimes'),
    'NaiveDateTime': (None, '.core.types.datetimes'),
    'PastDate': (None, '.core.types.datetimes'),
    'PastDateTime': (None, '.core.types.datetimes'),
    'StrictDate': (None, '.core.types.datetimes'),
    'StrictDateTime': (None, '.core.types.datetimes'),
    'StrictTime': (None, '.core.types.datetimes'),
    'StrictTimeDelta': (None, '.core.types.datetimes'),
    'Time': (None, '.core.types.datetimes'),
    'TimeDelta': (None, '.core.types.datetimes'),
    # Types (enums)
    'Enum': (None, '.core.types.enums'),
    'StrictEnum': (None, '.core.types.enums'),
    # Types (json)
    'Json': (None, '.core.types.json'),
    # Types (networks)
    'AmqpDsn': (None, '.core.types.networks'),
    'AnyUrl': (None, '.core.types.networks'),
    'AnyHttpUrl': (None, '.core.types.networks'),
    'CockroachDsn': (None, '.core.types.networks'),
    'Email': (None, '.core.types.networks'),
    'EngineMap': (None, '.core.types.networks'),
    'EngineUrl': (None, '.core.types.networks'),
    'FileUrl': (None, '.core.types.networks'),
    'HttpUrl': (None, '.core.types.networks'),
    'IPv4Address': (None, '.core.types.networks'),
    'IPv4Interface': (None, '.core.types.networks'),
    'IPv4Network': (None, '.core.types.networks'),
    'IPv6Address': (None, '.core.types.networks'),
    'IPv6Interface': (None, '.core.types.networks'),
    'IPv6Network': (None, '.core.types.networks'),
    'IPvAnyAddress': (None, '.core.types.networks'),
    'IPvAnyInterface': (None, '.core.types.networks'),
    'IPvAnyNetwork': (None, '.core.types.networks'),
    'KafkaDsn': (None, '.core.types.networks'),
    'MariaDBDsn': (None, '.core.types.networks'),
    'MongoDsn': (None, '.core.types.networks'),
    'MySQLDsn': (None, '.core.types.networks'),
    'NameEmail': (None, '.core.types.networks'),
    'NatsDsn': (None, '.core.types.networks'),
    'OracleDsn': (None, '.core.types.networks'),
    'PostgresDsn': (None, '.core.types.networks'),
    'RedisDsn': (None, '.core.types.networks'),
    'SQLiteDsn': (None, '.core.types.networks'),
    'SQLServerDsn': (None, '.core.types.networks'),
    # Types (numbers)
    'AllowInfNan': (None, '.core.types.numbers'),
    'Boolean': (None, '.core.types.numbers'),
    'Decimal': (None, '.core.types.numbers'),
    'FiniteDecimal': (None, '.core.types.numbers'),
    'FiniteFloat': (None, '.core.types.numbers'),
    'Float': (None, '.core.types.numbers'),
    'Integer': (None, '.core.types.numbers'),
    'NegativeDecimal': (None, '.core.types.numbers'),
    'NegativeFloat': (None, '.core.types.numbers'),
    'NegativeInteger': (None, '.core.types.numbers'),
    'NonNegativeDecimal': (None, '.core.types.numbers'),
    'NonNegativeFloat': (None, '.core.types.numbers'),
    'NonNegativeInteger': (None, '.core.types.numbers'),
    'NonPositiveDecimal': (None, '.core.types.numbers'),
    'NonPositiveFloat': (None, '.core.types.numbers'),
    'NonPositiveInteger': (None, '.core.types.numbers'),
    'PositiveDecimal': (None, '.core.types.numbers'),
    'PositiveFloat': (None, '.core.types.numbers'),
    'PositiveInteger': (None, '.core.types.numbers'),
    'StrictBoolean': (None, '.core.types.numbers'),
    'StrictDecimal': (None, '.core.types.numbers'),
    'StrictFloat': (None, '.core.types.numbers'),
    'StrictInteger': (None, '.core.types.numbers'),
    # Types (paths)
    'AnyPath': (None, '.core.types.paths'),
    'DirectoryPath': (None, '.core.types.paths'),
    'FilePath': (None, '.core.types.paths'),
    'NewPath': (None, '.core.types.paths'),
    # Types (secrets)
    'SecretBytes': (None, '.core.types.secrets'),
    'SecretStr': (None, '.core.types.secrets'),
    # Types (strings)
    'StrictString': (None, '.core.types.strings'),
    'String': (None, '.core.types.strings'),
    # Types (uuid)
    'UUID': (None, '.core.types.uuid'),
    'UUID1': (None, '.core.types.uuid'),
    'UUID3': (None, '.core.types.uuid'),
    'UUID4': (None, '.core.types.uuid'),
    'UUID5': (None, '.core.types.uuid'),
}


def __dir__() -> list[str]:
    return list(__all__)


def __getattr__(name: str) -> object:
    if name not in __all_dynamic__:
        raise AttributeError(f"Module {__name__!r} has no attribute {name!r}.")

    from importlib import import_module

    package, module_name = __all_dynamic__[name]
    if package is None:
        package = str(getattr(__spec__, 'parent'))

    try:
        if module_name == '__module__':
            return import_module(f'.{name}', package=package)
        module = import_module(module_name, package=package)
        return getattr(module, name)
    except Exception as exception:
        raise ImportError(
            f"An error occured while trying to import {name!r} from "
            f"{package!r}."
        ) from exception
