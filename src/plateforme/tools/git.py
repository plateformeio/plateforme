# plateforme.tools.git
# --------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities to interact with git repositories from Python
within the Plateforme framework.

Functions in this module allow for checking the presence of a git repository,
verifying the availability of the git executable, and retrieving the current
git revision of a specified directory.
"""

import os
import subprocess

__all__ = (
    'git_revision',
    'have_git',
    'is_git_repo',
)


def git_revision(dir: str) -> str:
    """Get the SHA-1 of the HEAD of a git repository."""
    return subprocess.check_output(
        ['git', 'rev-parse', '--short', 'HEAD'],
        cwd=dir,
    ).decode('utf-8').strip()


def have_git() -> bool:
    """Can we run the git executable?"""
    try:
        subprocess.check_output(['git', '--help'])
        return True
    except subprocess.CalledProcessError:
        return False
    except OSError:
        return False


def is_git_repo(dir: str) -> bool:
    """Is the given directory version-controlled with git?"""
    return os.path.exists(os.path.join(dir, '.git'))
