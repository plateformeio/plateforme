# plateforme.api
# --------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing the API components of the
Plateforme framework. It leverages FastAPI and Starlette to offer robust API
design, asynchronous handling, and additional features like background tasks,
data structures management, and custom request and response handling.
"""

from .core.api.background import BackgroundTasks
from .core.api.base import APIManager
from .core.api.datastructures import (
    URL,
    Address,
    FormData,
    Headers,
    QueryParams,
    State,
    UploadFile,
)
from .core.api.dependencies import AsyncSessionDep, SessionDep
from .core.api.exceptions import HTTPException, WebSocketException
from .core.api.parameters import (
    Body,
    Cookie,
    Depends,
    File,
    Form,
    Header,
    Path,
    Payload,
    Query,
    Security,
    Selection,
)
from .core.api.requests import HTTPConnection, Request
from .core.api.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    ORJSONResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
    StreamingResponse,
    UJSONResponse,
)
from .core.api.routing import (
    APIRouteConfig,
    APIRouteDecorator,
    APIRouter,
    route,
)
from .core.api.status import status
from .core.api.websockets import WebSocket, WebSocketDisconnect
from .core.expressions import Condition, Filter, Ordering, Sort
from .core.selectors import BaseSelector, Key, KeyList

__all__ = (
    # Background
    'BackgroundTasks',
    # Base
    'APIManager',
    # Datastructures
    'URL',
    'Address',
    'FormData',
    'Headers',
    'QueryParams',
    'State',
    'UploadFile',
    # Dependencies
    'AsyncSessionDep',
    'SessionDep',
    # Exceptions
    'HTTPException',
    'WebSocketException',
    # Expressions
    'Condition',
    'Filter',
    'Ordering',
    'Sort',
    # Parameters
    'Body',
    'Cookie',
    'Depends',
    'File',
    'Form',
    'Header',
    'Path',
    'Payload',
    'Query',
    'Security',
    'Selection',
    # Requests
    'HTTPConnection',
    'Request',
    # Responses
    'FileResponse',
    'HTMLResponse',
    'JSONResponse',
    'ORJSONResponse',
    'PlainTextResponse',
    'RedirectResponse',
    'Response',
    'StreamingResponse',
    'UJSONResponse',
    # Routing
    'APIRouteConfig',
    'APIRouteDecorator',
    'APIRouter',
    'route',
    # Selectors
    'BaseSelector',
    'Key',
    'KeyList',
    # Status
    'status',
    # Websockets
    'WebSocket',
    'WebSocketDisconnect',
)
