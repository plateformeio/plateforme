"""
The application setup script used to build the database schema.
"""

from server.main import app  # type: ignore

app.metadata.create_all()
