# plateforme.scripts.utils.bash
# -----------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

import subprocess
import sys


def run_command(command):
    """Run a command using subprocess and print its output."""
    result = subprocess.run(command, capture_output=True, text=True)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    elif result.stdout:
        print(result.stdout)
    return result.returncode
