"""Tests for authentication module: register, login, refresh, logout."""
import pytest

# Use a dedicated user for login/logout tests to avoid invalidating shared fixtures
AUTH_TEST_EMAIL = "auth_test_user@test.com"
AUTH_TEST_PASSWORD = "AuthTest@123456"
AUTH_TEST_COMPANY = "Auth Test Co"


@pytest.fixture(scope="module")
def auth_test_user(client):
    """Register a dedicated user for auth tests (avoids touching shared super session)."""
    resp = client.post("/api/auth/register", json={
        "email": AUTH_TEST_EMAIL,
        "password": AUTH_TEST_PASSWORD,
        "firstName": "Auth",
        "lastName": "Tester",
        "companyName": AUTH_TEST_COMPANY,
    })
    if resp.status_code in (200, 201):
        return resp.json()
    # Already registered from a previous run
    login_resp = client.post("/api/auth/login", json={
        "email": AUTH_TEST_EMAIL,
        "password": AUTH_TEST_PASSWORD,
    })
    assert login_resp.status_code == 200
    return login_resp.json()


class TestRegister:
    def test_register_admin_with_company(self, client):
        resp = client.post("/api/auth/register", json={
            "email": "reg_admin@test.com",
            "password": "Test@123456",
            "firstName": "Reg",
            "lastName": "Admin",
            "companyName": "Reg Test Company",
        })
        assert resp.status_code in (200, 201)
        data = resp.json()
        assert data.get("accessToken")
        assert data.get("refreshToken")

    def test_register_duplicate_email(self, client):
        payload = {
            "email": "dup@test.com",
            "password": "Test@123456",
            "firstName": "Dup",
            "lastName": "User",
            "companyName": "Dup Co",
        }
        client.post("/api/auth/register", json=payload)
        resp = client.post("/api/auth/register", json=payload)
        assert resp.status_code == 409

    def test_register_missing_fields(self, client):
        resp = client.post("/api/auth/register", json={"email": "bad@test.com"})
        assert resp.status_code in (400, 422)

    def test_register_with_company_code(self, client, admin_company_code, super_headers):
        from tests.conftest import _get_role_id
        crew_id = _get_role_id(client, "crew", super_headers)
        resp = client.post("/api/auth/register", json={
            "email": "codejoin@test.com",
            "password": "Test@123456",
            "firstName": "Code",
            "lastName": "Join",
            "roleId": crew_id,
            "companyCode": admin_company_code,
        })
        assert resp.status_code in (200, 201)

    def test_register_invalid_company_code(self, client):
        resp = client.post("/api/auth/register", json={
            "email": "badcode@test.com",
            "password": "Test@123456",
            "firstName": "Bad",
            "lastName": "Code",
            "companyCode": "INVALID999",
        })
        assert resp.status_code == 400


class TestLogin:
    def test_login_success(self, client, auth_test_user):
        resp = client.post("/api/auth/login", json={
            "email": AUTH_TEST_EMAIL,
            "password": AUTH_TEST_PASSWORD,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("accessToken")
        assert data.get("refreshToken")
        assert data.get("user")

    def test_login_wrong_password(self, client, auth_test_user):
        resp = client.post("/api/auth/login", json={
            "email": AUTH_TEST_EMAIL,
            "password": "WrongPassword123",
        })
        assert resp.status_code in (401, 403)

    def test_login_nonexistent_user(self, client):
        resp = client.post("/api/auth/login", json={
            "email": "nonexistent@test.com",
            "password": "Test@123456",
        })
        assert resp.status_code in (401, 404)


class TestRefreshToken:
    def test_refresh_success(self, client, auth_test_user):
        login_resp = client.post("/api/auth/login", json={
            "email": AUTH_TEST_EMAIL,
            "password": AUTH_TEST_PASSWORD,
        })
        refresh_token = login_resp.json().get("refreshToken")
        assert refresh_token
        resp = client.post("/api/auth/refresh", json={
            "refreshToken": refresh_token,
        })
        assert resp.status_code == 200
        assert resp.json().get("accessToken")

    def test_refresh_invalid_token(self, client):
        resp = client.post("/api/auth/refresh", json={
            "refreshToken": "invalid.token.here",
        })
        assert resp.status_code in (401, 403, 422)


class TestLogout:
    def test_logout_success(self, client, auth_test_user):
        login_resp = client.post("/api/auth/login", json={
            "email": AUTH_TEST_EMAIL,
            "password": AUTH_TEST_PASSWORD,
        })
        token = login_resp.json().get("accessToken")
        refresh = login_resp.json().get("refreshToken")
        resp = client.post(
            "/api/auth/logout",
            json={"refreshToken": refresh},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    def test_logout_no_auth(self, client):
        resp = client.post("/api/auth/logout", json={})
        assert resp.status_code == 401
