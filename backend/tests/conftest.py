"""pytest conftest: fix TestClient hang on Windows (anyio + starlette 0.38.6).

The root cause: starlette TestClient uses anyio.to_thread.run_sync internally
to run the ASGI app. On Windows with asyncio's ProactorEventLoop (default in
Python 3.10+), thread pool tasks can deadlock if the event loop isn't a
SelectorEventLoop.

Fix: set WindowsSelectorEventLoopPolicy before TestClient runs.
"""
import asyncio
import os
import sys

import pytest


if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


from uuid import uuid4

from fastapi.testclient import TestClient

from backend.src.main import create_app
from backend.src.social.fixtures import load_fixture_services


@pytest.fixture(scope="session")
def fixture_services():
    return load_fixture_services()


@pytest.fixture
def client(monkeypatch, fixture_services):
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("LOCKULTURE_SOCIAL_FIXTURES", "1")
    app = create_app(social=fixture_services)
    # Use context manager to trigger lifespan events
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def call(client, method, path, actor="A", *, key=None, **kwargs):
    headers = {"Authorization": f"Bearer lockulture-dev-{actor}"}
    if method != "GET":
        headers["Idempotency-Key"] = str(key or uuid4())
    return client.request(method, "/api/v1" + path, headers=headers, **kwargs)
