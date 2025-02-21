# plateforme.logging
# ------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides logging utilities for the Plateforme framework.
"""

from .core.logging import (
    COLOR_MAP,
    LOG_RECORD_MAP,
    Color,
    DefaultFormatter,
    FileHandler,
    JsonFormatter,
    NoErrorFilter,
    StreamHandler,
)

__all__ = (
    # Filters
    'NoErrorFilter',
    # Formatters
    'DefaultFormatter',
    'JsonFormatter',
    # Handlers
    'FileHandler',
    'StreamHandler',
    # Utilities
    'COLOR_MAP',
    'LOG_RECORD_MAP',
    'Color',
)
