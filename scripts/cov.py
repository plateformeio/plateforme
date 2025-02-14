#!/usr/bin/env python3

# plateforme.scripts.cov
# ----------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

import cov_report
import cov_test


def main():
    cov_test.main()
    cov_report.main()

if __name__ == '__main__':
    main()
