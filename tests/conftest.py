import asyncio
import os
import uuid

import pytest
from motor.motor_asyncio import AsyncIOMotorClient


def _run_async(coro):
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


def _can_connect(uri: str) -> bool:
    async def _ping():
        client = AsyncIOMotorClient(uri)
        try:
            await client.admin.command("ping")
        finally:
            client.close()

    try:
        _run_async(_ping())
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def test_db_name() -> str:
    return f"profit_sharing_test_{uuid.uuid4().hex}"


@pytest.fixture(scope="session")
def client(test_db_name: str):
    mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    if not _can_connect(mongo_uri):
        pytest.skip("MongoDB is not available for tests")

    os.environ["MONGODB_URI"] = mongo_uri
    os.environ["DATABASE_NAME"] = test_db_name

    from app.main import app
    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client

    async def _drop_db():
        client = AsyncIOMotorClient(mongo_uri)
        try:
            await client.drop_database(test_db_name)
        finally:
            client.close()

    _run_async(_drop_db())
