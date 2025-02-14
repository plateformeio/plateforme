# plateforme.schema
# -----------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing the schema components of the
Plateforme framework. It leverages Pydantic to offer robust data models and
fields validation, serialization, and deserialization capabilities.
"""

from .core.config import ConfigDict, with_config
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
    Schema,
    Strict,
    Tag,
    TypeAdapter,
    TypeAdapterList,
)

__all__ = (
    # Aliases
    'AliasChoices',
    'AliasGenerator',
    'AliasPath',
    # Core
    'core_schema',
    'GetCoreSchemaHandler',
    'GetJsonSchemaHandler',
    'SerializationInfo',
    'ValidationError',
    'ValidationInfo',
    'ValidationMode',
    # Decorators
    'field_serializer',
    'field_validator',
    'model_serializer',
    'model_validator',
    'validate_call',
    # Fields
    'Field',
    'PrivateAttr',
    'computed_field',
    # JSON
    'GenerateJsonSchema',
    'JsonEncoder',
    'JsonSchemaDict',
    'JsonSchemaExtra',
    'JsonSchemaExtraCallable',
    'JsonSchemaMode',
    'JsonSchemaSource',
    'JsonSchemaValue',
    # Models
    'BaseModel',
    'DiscriminatedModel',
    'ModelConfig',
    'RootModel',
    'collect_fields',
    'collect_models',
    'create_discriminated_model',
    'create_model',
    'create_root_model',
    # Types
    'Discriminator',
    'Schema',
    'Strict',
    'Tag',
    'TypeAdapter',
    'TypeAdapterList',
    # Utilities
    'ConfigDict',
    'with_config',
)
