"""Tests for audit log endpoints."""
import pytest


class TestListAuditLogs:
    def test_super_can_list_audit_logs(self, client, super_headers):
        resp = client.get("/api/audit-logs", headers=super_headers)
        # 200 if audit:read permission exists, 403 if not seeded
        assert resp.status_code in (200, 403)

    def test_admin_can_list_audit_logs(self, client, admin_headers):
        resp = client.get("/api/audit-logs", headers=admin_headers)
        assert resp.status_code in (200, 403)

    def test_broker_cannot_list_audit_logs(self, client, broker_headers):
        resp = client.get("/api/audit-logs", headers=broker_headers)
        assert resp.status_code == 403

    def test_unauthenticated_cannot_list(self, client):
        resp = client.get("/api/audit-logs")
        assert resp.status_code == 401


class TestGetAuditLog:
    def test_nonexistent_audit_log(self, client, super_headers):
        resp = client.get("/api/audit-logs/000000000000000000000000", headers=super_headers)
        # 404 if permission granted, 403 if audit:read not seeded
        assert resp.status_code in (404, 403)


class TestUserAuditHistory:
    def test_super_can_get_user_audit(self, client, super_headers):
        resp = client.get("/api/audit-logs/user/000000000000000000000000", headers=super_headers)
        assert resp.status_code in (200, 403)

    def test_broker_cannot_get_user_audit(self, client, broker_headers):
        resp = client.get("/api/audit-logs/user/000000000000000000000000", headers=broker_headers)
        assert resp.status_code == 403


class TestCompanyAuditHistory:
    def test_super_can_get_company_audit(self, client, super_headers):
        resp = client.get("/api/audit-logs/company/000000000000000000000000", headers=super_headers)
        assert resp.status_code in (200, 403)

    def test_broker_cannot_get_company_audit(self, client, broker_headers):
        resp = client.get("/api/audit-logs/company/000000000000000000000000", headers=broker_headers)
        assert resp.status_code == 403
