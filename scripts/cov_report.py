#!/usr/bin/env python3

# plateforme.scripts.cov_report
# -----------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

from utils import run_command


def main():
    try:
        run_command(['coverage', 'combine'])
    except Exception as error:
        print(error)

    run_command(['coverage', 'report'])

if __name__ == '__main__':
    main()
