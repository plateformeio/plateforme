# plateforme.settings
# -------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing settings within the Plateforme
framework. It facilitates the customization of application behavior,
integration settings, and service operations through structured configuration
objects that enhance maintainability and scalability of the application.
"""

from .core.settings import (
    APIRouterSettings,
    APISettings,
    LoggingSettings,
    NamespaceSettings,
    PackageSettings,
    Settings,
)

__all__ = (
    'APIRouterSettings',
    'APISettings',
    'LoggingSettings',
    'NamespaceSettings',
    'PackageSettings',
    'Settings',
)
