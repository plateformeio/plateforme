# plateforme.core.deprecated
# --------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides a deprecated type alias for the Plateforme framework. It
is either an alias to the `typing_extensions.deprecated` backport or the
built-in `warnings.deprecated` class (available in Python 3.13+).
"""

import sys
from typing import TypeAlias

from typing_extensions import deprecated

if sys.version_info >= (3, 13):
    import warnings
    Deprecated: TypeAlias = warnings.deprecated | deprecated
else:
    Deprecated: TypeAlias = deprecated

__all__ = (
    'Deprecated',
)
