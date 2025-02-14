# plateforme.errors
# -----------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module is a proxy for the Plateforme framework core errors module.
"""

from .core.errors import *  # noqa: F403

__all__ = [name for name in dir() if not name.startswith('_')]


def __dir__() -> list[str]:
    return list(__all__)
