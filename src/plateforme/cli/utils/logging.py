# plateforme.cli.utils.logging
# ----------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
Logging utilities for the command line interface.
"""

import logging
import sys

from plateforme.core.logging import COLOR_MAP, Color, supports_ansi_colors


def setup_cli_logger(level: int = logging.INFO) -> logging.Logger:
    """Setup the CLI logging system."""

    class Formatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            if supports_ansi_colors():
                color_start = COLOR_MAP.get(record.levelname, Color.RESET)
                color_end = Color.RESET
                levelname = f'{color_start}{record.levelname}{color_end}:'
                levelname_offset = len(color_start + color_end)
            else:
                levelname = f'{record.levelname}:'
                levelname_offset = 0

            record.levelname = levelname.ljust(levelname_offset + 10)
            return super().format(record)

    logger = logging.getLogger('plateforme_cli')

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(Formatter('%(levelname)s%(message)s'))

        logger.addHandler(handler)
        logger.setLevel(level)
        logger.propagate = False

    return logger


logger = setup_cli_logger()
"""The CLI logger of the Plateforme framework."""
