# plateforme.errors
# -----------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module is a proxy for the Plateforme framework core errors module.
"""

from .core.errors import (
    AuthenticationError,
    DatabaseError,
    MissingDeferred,
    PlateformeError,
    SecurityError,
)

__all__ = (
    # Framework
    'AuthenticationError',
    'DatabaseError',
    'SecurityError',
    # User
    'PlateformeError',
    # Miscellaneous
    'MissingDeferred',
)
