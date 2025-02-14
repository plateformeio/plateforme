# plateforme.middleware.gzip
# --------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing GZip middleware within the
Plateforme framework's API using FastAPI and Starlette features.
"""

from starlette.middleware.gzip import GZipMiddleware

__all__ = (
    'GZipMiddleware',
)
