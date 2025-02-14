# plateforme.tests.fixtures
# -------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

from .database import engine, session

__all__ = (
    'engine',
    'session',
)
