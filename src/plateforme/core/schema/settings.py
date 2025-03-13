# plateforme.core.schema.settings
# -------------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing settings within the Plateforme
framework using Pydantic features.
"""

from pydantic_settings import (
    BaseSettings as _BaseSettings,
    SettingsConfigDict,
)

__all__ = (
    'BaseSettings',
    'SettingsConfigDict',
)


class BaseSettings(_BaseSettings):
    """The base settings class for Plateforme applications."""

    model_config = SettingsConfigDict(
        title='Plateforme settings',
        strict=True,
        env_prefix='PLATEFORME_',
    )
