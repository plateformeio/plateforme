# plateforme.tests.conftest
# -------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

import pytest

pytest_plugins = (
    'tests.fixtures',
)


@pytest.fixture()
def clear_environment():
    from plateforme import runtime
    runtime.clear_cache()


@pytest.fixture
def package(request):
    from plateforme import runtime
    name = request.function.__module__
    return runtime.import_package(name, force_resolution=True)
