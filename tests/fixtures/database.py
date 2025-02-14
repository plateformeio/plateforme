# plateforme.tests.fixtures.database
# ----------------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

import pytest

from plateforme.database import create_engine, session_factory

# List of database configurations for testing
database_configs = (
    'sqlite:///:memory:',
    # Add other database URLs...
)


@pytest.fixture(params=database_configs, scope='session')
def engine(request):
    return create_engine(request.param)


@pytest.fixture(scope='function')
def session(engine):
    Session = session_factory(bind=engine)
    session = Session()
    yield session
    session.close()
