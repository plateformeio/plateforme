# plateforme.resources
# --------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides comprehensive utilities for resource management within the
Plateforme framework. It supports the configuration and management of
resources and services, integrating features such as archiving, auditing,
encryption, and validation to facilitate robust and scalable data-driven
application development.
"""

from .core.config import ConfigDict, with_config
from .core.mixins import Archivable, Auditable, Encrypted
from .core.resources import (
    BaseResource,
    CRUDResource,
    ResourceConfig,
    ResourceIndex,
)
from .core.schema.fields import Field, PrivateAttr, computed_field
from .core.services import (
    BaseService,
    BaseServiceWithSpec,
    CRUDService,
    ServiceConfig,
)
from .core.specs import BaseSpec, CRUDSpec

__all__ = (
    # Fields
    'Field',
    'PrivateAttr',
    'computed_field',
    # Mixins
    'Archivable',
    'Auditable',
    'Encrypted',
    # Resources
    'BaseResource',
    'CRUDResource',
    'ResourceConfig',
    'ResourceIndex',
    # Services
    'BaseService',
    'BaseServiceWithSpec',
    'CRUDService',
    'ServiceConfig',
    # Specifications
    'BaseSpec',
    'CRUDSpec',
    # Utilities
    'ConfigDict',
    'with_config',
)
