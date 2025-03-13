# plateforme.core.schema.errors
# -----------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing errors related to Pydantic schema
generation and validation.
"""

from pydantic.errors import (
    PydanticImportError,
    PydanticInvalidForJsonSchema,
    PydanticSchemaGenerationError,
    PydanticUndefinedAnnotation,
    PydanticUserError,
)

__all__ = (
    'PydanticUserError',
    'PydanticUndefinedAnnotation',
    'PydanticImportError',
    'PydanticSchemaGenerationError',
    'PydanticInvalidForJsonSchema',
)
