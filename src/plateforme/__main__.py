#!/usr/bin/env python3

# plateforme
# ----------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
The modern ASGI framework for data-driven applications.

The Plateforme framework provides a suite of tools and components to support
the rapid development of data-driven applications. It includes a collection of
modules that offer a wide range of functionalities, from environment setup to
data modeling, resource management, and API deployment.

Examples:
    >>> from plateforme import Plateforme, BaseResource, Field
    ...
    >>> app = Plateforme()
    ...
    >>> class MyResource(BaseResource):
    ...     foo: int
    ...     bar: str = Field(default='hello-world')
"""

from .cli import app

if __name__ == '__main__':
    app()
