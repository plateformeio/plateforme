<p style="text-align: center">
  <a href="https://docs.plateforme.io"><img src="https://raw.githubusercontent.com/plateformeio/plateforme/refs/heads/main/docs/banner.png" alt="Plateforme"></a>
</p>

# Plateforme Core - OSS (alpha release)

[![ci](https://img.shields.io/github/actions/workflow/status/plateformeio/plateforme/ci.yml?branch=main&logo=github&label=ci)](https://github.com/plateformeio/plateforme/actions?query=event%3Apush+branch%3Amain+workflow%3Aci)
[![pypi](https://img.shields.io/pypi/v/plateforme.svg)](https://pypi.python.org/pypi/plateforme)
[![downloads](https://static.pepy.tech/badge/plateforme/month)](https://pepy.tech/project/plateforme)
[![versions](https://img.shields.io/pypi/pyversions/plateforme.svg)](https://github.com/plateformeio/plateforme)
[![license](https://img.shields.io/github/license/plateformeio/plateforme.svg)](https://github.com/plateformeio/plateforme/blob/main/LICENSE)

Plateforme enables you to build and deploy modern data-driven applications and services in seconds with the power of [SQLAlchemy](https://github.com/sqlalchemy/sqlalchemy), [Pydantic](https://github.com/plateforme/plateforme), and [FastAPI](https://github.com/tiangolo/fastapi).

## Help

See the [documentation](https://docs.plateforme.io) for more details.

## Installation

Install using `pip install -U plateforme` or `conda install plateforme -c conda-forge`.

For more details and advanced installation options, see the [installation guide](https://docs.plateforme.io/latest/start/install) from the official documentation site.

## A basic example

### Create a simple application

```python
from typing import Self

from plateforme import Plateforme
from plateforme.api import route
from plateforme.resources import ConfigDict, CRUDResource, Field

app = Plateforme(debug=True, database_engines='plateforme.db')

class Rocket(CRUDResource):
    code: str = Field(unique=True)
    name: str
    parts: list['RocketPart'] = Field(default_factory=list)
    launched: bool = False

    @route.post()
    async def launch(self) -> Self:
        self.launched = True
        return self

class RocketPart(CRUDResource):
    __config__ = ConfigDict(indexes=[{'rocket', 'code'}])
    rocket: Rocket
    code: str
    quantity: int
```

### Validate and use data

```python
some_data = {
    'code': 'FAL-9',
    'name': 'Falcon 9',
    'parts': [
        {'code': 'dragon', 'quantity': 1},
        {'code': 'raptor', 'quantity': 9},
        {'code': 'tank', 'quantity': 1},
    ],
}

rocket = Rocket.resource_validate(some_data)
print(repr(rocket))
#> Rocket(code='FAL-9')

print(repr(rocket.parts[0].code))
#> 'dragon'
```

### Persist data

```python
# Create the database schema
app.metadata.create_all()

# Persist the data
with app.session() as session:
    session.add(rocket)
    session.commit()

# Query the data
with app.session() as session:
    rocket = session.query(Rocket).filter_by(code='FAL-9').one()

print(repr(rocket))
#> Rocket(id=1, code='FAL-9')
```

### Run the application

```bash
uvicorn main:app
```

### Play with the API

#### Use the built-in CRUD and query engine

With the built-in CRUD and query engine, you can easily create, read, update, and delete resources. The following query finds all parts in rocket `#1` whose part codes contain the sequence `ra`.

```http
GET http://localhost:8000/rockets/1/parts?.code=like~*ra* HTTP/1.1
```

```json
[
  {
    "id": 1,
    "type": "rocket_part",
    "code": "dragon",
    "quantity": 1
  },
  {
    "id": 2,
    "type": "rocket_part",
    "code": "raptor",
    "quantity": 9
  }
]
```

#### Use custom routes

You can also define custom routes to perform more complex operations. The following request launches rocket `#1` and persists in the database the `launched` flag to `true`.

```http
POST http://localhost:8000/rockets/1/launch HTTP/1.1
```

```json
{
  "id": 1,
  "type": "rocket",
  "code": "FAL-9",
  "name": "Falcon 9",
  "parts": [
    ...
  ],
  "launched": true
}
```

### Use the built-in CLI

Plateforme comes with a built-in CLI to help you automate common tasks. For instance, the following commands initialize a new project, build it, and start the server.

```bash
# Initialize the project
plateforme init

# Build the project
plateforme build

# Start the server
plateforme start --reload
```

For detailed documentation and more examples, see the [official documentation](https://docs.plateforme.io/latest/start).

## Contributing

For guidance on setting up a development environment and how to make a contribution to Plateforme, read the [contributing guidelines](https://docs.plateforme.io/latest/about/community/contributing) from the official documentation site.

## Reporting a security vulnerability

See our [security policy](https://github.com/plateformeio/plateforme/security/policy).
