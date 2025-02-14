# plateforme.core.database.events
# -------------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing database events within the
Plateforme framework using SQLAlchemy features.
"""

from sqlalchemy.event import (
    CANCEL,
    NO_RETVAL,
    contains,
    listen,
    listens_for,
    remove,
)

__all__ = (
    'CANCEL',
    'NO_RETVAL',
    'contains',
    'listen',
    'listens_for',
    'remove',
)
