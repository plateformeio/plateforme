#!/usr/bin/env python3

# plateforme.scripts.install
# --------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

from utils import run_command


def main():
    run_command(['hatch', 'run', 'true'])

if __name__ == '__main__':
    main()
