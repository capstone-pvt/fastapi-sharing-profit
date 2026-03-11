import asyncio
import os
import uuid
from pathlib import Path

import certifi
import pytest
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

# Load .env before anything else
load_dotenv(Path(__file__).resolve().parents[1] / ".env")


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
        client = AsyncIOMotorClient(uri, tlsCAFile=certifi.where())
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
    return f"smart_catch_test_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="session")
def client(test_db_name: str):
    mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    if not _can_connect(mongo_uri):
        pytest.skip("MongoDB is not available for tests")

    os.environ["MONGODB_URI"] = mongo_uri
    os.environ["DATABASE_NAME"] = test_db_name
    os.environ["JWT_EXPIRATION"] = "60m"  # Extend JWT for long test runs

    from app.main import app
    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client

    async def _drop_db():
        c = AsyncIOMotorClient(mongo_uri, tlsCAFile=certifi.where())
        try:
            await c.drop_database(test_db_name)
        finally:
            c.close()

    _run_async(_drop_db())


# ── Auth helpers ──────────────────────────────────────────────

SUPER_EMAIL = "super@example.com"
SUPER_PASSWORD = "Admin@123456"

ADMIN_EMAIL = "testadmin@example.com"
ADMIN_PASSWORD = "Admin@123456"
ADMIN_COMPANY = "Test Company"

BROKER_EMAIL = "testbroker@example.com"
BROKER_PASSWORD = "Broker@123456"

CREW_EMAIL = "testcrew@example.com"
CREW_PASSWORD = "Crew@123456"


def _get_role_id(client, name: str, headers: dict) -> str | None:
    resp = client.get("/api/roles", headers=headers)
    if resp.status_code != 200:
        return None
    for role in resp.json():
        if role.get("name", "").lower() == name.lower():
            return role["id"]
    return None


def register_and_login(client, email, password, first_name, last_name,
                       role_id=None, company_name=None, company_code=None):
    payload = {
        "email": email,
        "password": password,
        "firstName": first_name,
        "lastName": last_name,
    }
    if role_id:
        payload["roleId"] = role_id
    if company_name:
        payload["companyName"] = company_name
    if company_code:
        payload["companyCode"] = company_code
    resp = client.post("/api/auth/register", json=payload)
    if resp.status_code in (200, 201):
        data = resp.json()
        return data.get("accessToken")
    return None


def login(client, email, password):
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    if resp.status_code == 200:
        return resp.json().get("accessToken")
    return None


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def super_headers(client) -> dict:
    """Login as seeded super user."""
    token = login(client, SUPER_EMAIL, SUPER_PASSWORD)
    assert token, "Super user login failed — ensure seeders have run"
    return auth_headers(token)


@pytest.fixture(scope="session")
def admin_headers(client, super_headers) -> dict:
    """Register an admin user who creates a company."""
    token = register_and_login(
        client, ADMIN_EMAIL, ADMIN_PASSWORD,
        "Test", "Admin", company_name=ADMIN_COMPANY,
    )
    if not token:
        token = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    assert token, "Admin registration/login failed"
    return auth_headers(token)


@pytest.fixture(scope="session")
def admin_company_code(client, admin_headers) -> str:
    """Get the company code for the admin's company."""
    resp = client.get("/api/profile", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    code = data.get("companyCode")
    assert code, "Admin profile missing companyCode"
    return code


@pytest.fixture(scope="session")
def broker_headers(client, super_headers, admin_company_code) -> dict:
    """Register a broker in the admin's company."""
    broker_role_id = _get_role_id(client, "broker", super_headers)
    token = register_and_login(
        client, BROKER_EMAIL, BROKER_PASSWORD,
        "Test", "Broker",
        role_id=broker_role_id,
        company_code=admin_company_code,
    )
    if not token:
        token = login(client, BROKER_EMAIL, BROKER_PASSWORD)
    assert token, "Broker registration/login failed"
    return auth_headers(token)


@pytest.fixture(scope="session")
def crew_headers(client, super_headers, admin_company_code) -> dict:
    """Register a crew member in the admin's company."""
    crew_role_id = _get_role_id(client, "crew", super_headers)
    token = register_and_login(
        client, CREW_EMAIL, CREW_PASSWORD,
        "Test", "Crew",
        role_id=crew_role_id,
        company_code=admin_company_code,
    )
    if not token:
        token = login(client, CREW_EMAIL, CREW_PASSWORD)
    assert token, "Crew registration/login failed"
    return auth_headers(token)
