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
    ContactInfo,
    LicenseInfo,
    LoggingCustomFormatterSettings,
    LoggingCustomHandlerSettings,
    LoggingDefaultFormatterSettings,
    LoggingFileHandlerSettings,
    LoggingJsonFormatterSettings,
    LoggingSettings,
    LoggingSimpleFormatterSettings,
    LoggingStreamHandlerSettings,
    NamespaceSettings,
    PackageSettings,
    PackageSettingsExtra,
    Settings,
)

__all__ = (
    # Information
    'ContactInfo',
    'LicenseInfo',
    # Settings
    'APIRouterSettings',
    'APISettings',
    'LoggingCustomFormatterSettings',
    'LoggingCustomHandlerSettings',
    'LoggingDefaultFormatterSettings',
    'LoggingFileHandlerSettings',
    'LoggingJsonFormatterSettings',
    'LoggingSettings',
    'LoggingSimpleFormatterSettings',
    'LoggingStreamHandlerSettings',
    'NamespaceSettings',
    'PackageSettings',
    'PackageSettingsExtra',
    'Settings',
)
