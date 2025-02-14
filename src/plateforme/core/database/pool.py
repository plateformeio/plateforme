# plateforme.core.database.pool
# -----------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing database pooling within the
Plateforme framework using SQLAlchemy features.
"""

from sqlalchemy.pool import (
    NullPool,
    QueuePool,
    SingletonThreadPool,
    StaticPool,
)

__all__ = (
    'NullPool',
    'QueuePool',
    'SingletonThreadPool',
    'StaticPool',
)
