# plateforme.cli.utils.config
# ---------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
Configuration utilities for the command line interface.
"""

import os


def supports_utf8() -> bool:
    lang = os.environ.get('LANG', '').lower()
    if 'utf-8' in lang or 'utf8' in lang:
        return True
    return False
