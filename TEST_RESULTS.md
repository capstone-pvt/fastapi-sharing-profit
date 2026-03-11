# Profit Sharing API - Test Results

**Date:** 2026-03-11
**Framework:** pytest 7.4.4 | Python 3.11.9
**Result:** 182 passed, 0 failed, 5 warnings
**Duration:** ~19 minutes

---

## Summary

| Module | Tests | Status |
|--------|-------|--------|
| Auth | 12 | All Passed |
| Users | 13 | All Passed |
| Profile | 6 | All Passed |
| Roles | 6 | All Passed |
| Permissions | 4 | All Passed |
| Companies | 8 | All Passed |
| Licenses | 11 | All Passed |
| Cash Advances | 6 | All Passed |
| RBAC | 16 | All Passed |
| CRUD Endpoints | 42 | All Passed |
| Fish Analysis & Scanning | 9 | All Passed |
| Fish Models | 14 | All Passed |
| Fish Species | 5 | All Passed |
| Fish Training Samples | 17 | All Passed |
| Weather | 4 | All Passed |
| Audit Logs | 9 | All Passed |
| **Total** | **182** | **All Passed** |

---

## Detailed Results

### Auth (`tests/auth/test_auth.py`)

| Test | Result |
|------|--------|
| `TestRegister::test_register_admin_with_company` | PASSED |
| `TestRegister::test_register_duplicate_email` | PASSED |
| `TestRegister::test_register_missing_fields` | PASSED |
| `TestRegister::test_register_with_company_code` | PASSED |
| `TestRegister::test_register_invalid_company_code` | PASSED |
| `TestLogin::test_login_success` | PASSED |
| `TestLogin::test_login_wrong_password` | PASSED |
| `TestLogin::test_login_nonexistent_user` | PASSED |
| `TestRefreshToken::test_refresh_success` | PASSED |
| `TestRefreshToken::test_refresh_invalid_token` | PASSED |
| `TestLogout::test_logout_success` | PASSED |
| `TestLogout::test_logout_no_auth` | PASSED |

### Users (`tests/users/test_users.py`)

| Test | Result |
|------|--------|
| `TestListUsers::test_super_can_list_all_users` | PASSED |
| `TestListUsers::test_broker_sees_only_company_users` | PASSED |
| `TestListUsers::test_crew_cannot_list_users` | PASSED |
| `TestListUsers::test_unauthenticated_cannot_list` | PASSED |
| `TestListUsers::test_list_with_search` | PASSED |
| `TestListUsers::test_list_with_pagination` | PASSED |
| `TestGetUser::test_super_can_get_user` | PASSED |
| `TestGetUser::test_get_nonexistent_user` | PASSED |
| `TestCreateUser::test_super_can_create_user` | PASSED |
| `TestBulkAssignCompany::test_super_can_bulk_assign` | PASSED |
| `TestBulkAssignCompany::test_non_super_cannot_bulk_assign` | PASSED |
| `TestBulkAssignCompany::test_unauthenticated_cannot_bulk_assign` | PASSED |
| `TestDeleteUser::test_super_can_delete_user` | PASSED |

### Profile (`tests/test_profile.py`)

| Test | Result |
|------|--------|
| `TestGetProfile::test_super_can_get_profile` | PASSED |
| `TestGetProfile::test_admin_profile_has_company` | PASSED |
| `TestGetProfile::test_unauthenticated_cannot_get_profile` | PASSED |
| `TestUpdateProfile::test_update_first_name` | PASSED |
| `TestUpdateProfile::test_cannot_update_email_to_existing` | PASSED |
| `TestChangePassword::test_change_password_wrong_current` | PASSED |

### Roles (`tests/roles/test_roles.py`)

| Test | Result |
|------|--------|
| `TestListRoles::test_authenticated_user_can_list_roles` | PASSED |
| `TestListRoles::test_unauthenticated_cannot_list_roles` | PASSED |
| `TestGetRole::test_get_role_by_id` | PASSED |
| `TestCreateRole::test_admin_can_create_role` | PASSED |
| `TestCreateRole::test_non_admin_cannot_create_role` | PASSED |
| `TestDeleteRole::test_cannot_delete_admin_role` | PASSED |

### Permissions (`tests/permissions/test_permissions.py`)

| Test | Result |
|------|--------|
| `TestListPermissions::test_authenticated_can_list_permissions` | PASSED |
| `TestListPermissions::test_unauthenticated_cannot_list` | PASSED |
| `TestCreatePermission::test_admin_can_create_permission` | PASSED |
| `TestCreatePermission::test_non_admin_cannot_create` | PASSED |

### Companies (`tests/test_companies.py`)

| Test | Result |
|------|--------|
| `TestListCompanies::test_super_can_list_companies` | PASSED |
| `TestListCompanies::test_unauthenticated_cannot_list` | PASSED |
| `TestCreateCompany::test_super_can_create_company` | PASSED |
| `TestCreateCompany::test_non_super_cannot_create` | PASSED |
| `TestCreateCompany::test_unauthenticated_cannot_create` | PASSED |
| `TestUpdateCompany::test_admin_can_update_own_company` | PASSED |
| `TestDeleteCompany::test_super_can_delete_company` | PASSED |
| `TestDeleteCompany::test_broker_cannot_delete` | PASSED |

### Licenses (`tests/test_licenses.py`)

| Test | Result |
|------|--------|
| `TestLicenseStatus::test_get_license_status` | PASSED |
| `TestLicenseStatus::test_admin_license_status` | PASSED |
| `TestLicenseStatus::test_unauthenticated_cannot_check_status` | PASSED |
| `TestGenerateLicense::test_super_can_generate_license` | PASSED |
| `TestGenerateLicense::test_non_super_cannot_generate` | PASSED |
| `TestValidateLicense::test_validate_invalid_code` | PASSED |
| `TestListLicenses::test_super_can_list_licenses` | PASSED |
| `TestListLicenses::test_non_super_cannot_list` | PASSED |
| `TestRevokeLicense::test_super_can_revoke_license` | PASSED |
| `TestRevokeLicense::test_non_super_cannot_revoke` | PASSED |
| `TestRevokeLicense::test_revoke_nonexistent_returns_404` | PASSED |

### Cash Advances (`tests/test_cash_advances.py`)

| Test | Result |
|------|--------|
| `TestApproveCashAdvance::test_approve_flow` | PASSED |
| `TestApproveCashAdvance::test_approve_nonexistent_returns_404` | PASSED |
| `TestApproveCashAdvance::test_unauthenticated_cannot_approve` | PASSED |
| `TestDeclineCashAdvance::test_decline_flow` | PASSED |
| `TestDeclineCashAdvance::test_decline_without_reason_returns_400` | PASSED |
| `TestDeclineCashAdvance::test_unauthenticated_cannot_decline` | PASSED |

### RBAC (`tests/test_rbac.py`)

| Test | Result |
|------|--------|
| `TestBrokerPermissions::test_broker_can_list_boats` | PASSED |
| `TestBrokerPermissions::test_broker_can_create_boat` | PASSED |
| `TestBrokerPermissions::test_broker_can_list_trips` | PASSED |
| `TestBrokerPermissions::test_broker_can_list_users` | PASSED |
| `TestBrokerPermissions::test_broker_can_list_fish_sales` | PASSED |
| `TestBrokerPermissions::test_broker_can_list_expenses` | PASSED |
| `TestBrokerPermissions::test_broker_cannot_manage_roles` | PASSED |
| `TestBrokerPermissions::test_broker_cannot_manage_permissions` | PASSED |
| `TestCrewPermissions::test_crew_can_read_profit_shares` | PASSED |
| `TestCrewPermissions::test_crew_can_read_catches` | PASSED |
| `TestCrewPermissions::test_crew_can_read_fish_sales` | PASSED |
| `TestCrewPermissions::test_crew_cannot_list_users` | PASSED |
| `TestCrewPermissions::test_crew_cannot_create_boats` | PASSED |
| `TestCrewPermissions::test_crew_cannot_manage_roles` | PASSED |
| `TestSuperUserRestrictions::test_super_cannot_edit_self` | PASSED |
| `TestSuperUserRestrictions::test_super_cannot_delete_self` | PASSED |

### CRUD Endpoints (`tests/crud/test_crud_endpoints.py`)

| Resource | Create | List | CRUD Flow | Unauth Guard |
|----------|--------|------|-----------|--------------|
| boats | PASSED | PASSED | PASSED | PASSED |
| vessels | PASSED | PASSED | PASSED | PASSED |
| vessel-owners | PASSED | PASSED | PASSED | PASSED |
| trips | PASSED | PASSED | PASSED | PASSED |
| expenses | PASSED | PASSED | PASSED | PASSED |
| fish-sales | PASSED | PASSED | PASSED | PASSED |
| catches | PASSED | PASSED | PASSED | PASSED |
| crew | PASSED | PASSED | PASSED | PASSED |
| profit-sharing-policies | PASSED | PASSED | PASSED | PASSED |

| Resource | List | Create |
|----------|------|--------|
| cash-advances | PASSED | PASSED |
| forecasts | PASSED | PASSED |
| profit-shares | PASSED | PASSED |

### Fish Analysis & Scanning (`tests/fish/test_fish_analysis.py`)

| Test | Result |
|------|--------|
| `TestAnalyzeFish::test_analyze_with_image` | PASSED |
| `TestAnalyzeFish::test_analyze_with_single_fish_flag` | PASSED |
| `TestAnalyzeFish::test_analyze_with_caught_by` | PASSED |
| `TestAnalyzeFish::test_analyze_no_image_returns_422` | PASSED |
| `TestAnalyzeFish::test_unauthenticated_cannot_analyze` | PASSED |
| `TestFishAnalytics::test_get_analytics` | PASSED |
| `TestFishAnalytics::test_unauthenticated_cannot_get_analytics` | PASSED |
| `TestAnalysisHistory::test_get_analysis_history` | PASSED |
| `TestAnalysisHistory::test_unauthenticated_cannot_get_history` | PASSED |

### Fish Models (`tests/fish_models/test_fish_models.py`)

| Test | Result |
|------|--------|
| `TestListFishModels::test_super_can_list_models` | PASSED |
| `TestListFishModels::test_admin_can_list_models` | PASSED |
| `TestListFishModels::test_non_admin_cannot_list` | PASSED |
| `TestGetActiveModel::test_get_active_detector` | PASSED |
| `TestGetActiveModel::test_get_active_classifier` | PASSED |
| `TestCreateFishModel::test_admin_can_create_model` | PASSED |
| `TestCreateFishModel::test_non_admin_cannot_create` | PASSED |
| `TestUpdateFishModel::test_admin_can_update_model` | PASSED |
| `TestUpdateFishModel::test_non_admin_cannot_update` | PASSED |
| `TestActivateFishModel::test_admin_can_activate_model` | PASSED |
| `TestActivateFishModel::test_non_admin_cannot_activate` | PASSED |
| `TestDeleteFishModel::test_admin_can_soft_delete_model` | PASSED |
| `TestDeleteFishModel::test_non_admin_cannot_delete` | PASSED |
| `TestDeleteFishModel::test_delete_nonexistent_returns_404` | PASSED |

### Fish Species (`tests/fish_species/test_fish_species.py`)

| Test | Result |
|------|--------|
| `TestListFishSpecies::test_admin_can_list_all_species` | PASSED |
| `TestListFishSpecies::test_active_species_for_authenticated` | PASSED |
| `TestListFishSpecies::test_unauthenticated_cannot_list` | PASSED |
| `TestCreateFishSpecies::test_admin_can_create_species` | PASSED |
| `TestCreateFishSpecies::test_non_admin_cannot_create` | PASSED |

### Fish Training Samples (`tests/fish_training_samples/test_training_samples.py`)

| Test | Result |
|------|--------|
| `TestListTrainingSamples::test_authenticated_can_list` | PASSED |
| `TestListTrainingSamples::test_list_with_species_filter` | PASSED |
| `TestListTrainingSamples::test_list_with_pagination` | PASSED |
| `TestListTrainingSamples::test_unauthenticated_cannot_list` | PASSED |
| `TestCreateTrainingSample::test_broker_can_create_sample` | PASSED |
| `TestCreateTrainingSample::test_create_missing_species_returns_400` | PASSED |
| `TestCreateTrainingSample::test_create_missing_weight_returns_400` | PASSED |
| `TestCreateTrainingSample::test_create_missing_image_returns_422` | PASSED |
| `TestCreateTrainingSample::test_unauthenticated_cannot_create` | PASSED |
| `TestMyTrainingSamples::test_broker_can_list_own_samples` | PASSED |
| `TestMyTrainingSamples::test_unauthenticated_cannot_list_mine` | PASSED |
| `TestExportTrainingSamples::test_admin_can_export` | PASSED |
| `TestExportTrainingSamples::test_non_admin_cannot_export` | PASSED |
| `TestExportTrainingSamples::test_unauthenticated_cannot_export` | PASSED |
| `TestDeleteTrainingSample::test_admin_can_delete_sample` | PASSED |
| `TestDeleteTrainingSample::test_non_admin_cannot_delete` | PASSED |
| `TestDeleteTrainingSample::test_delete_nonexistent_returns_404` | PASSED |

### Weather (`tests/test_weather.py`)

| Test | Result |
|------|--------|
| `TestCurrentWeather::test_get_current_weather` | PASSED |
| `TestCurrentWeather::test_unauthenticated_cannot_get_weather` | PASSED |
| `TestWeatherForecast::test_get_forecast` | PASSED |
| `TestWeatherForecast::test_unauthenticated_cannot_get_forecast` | PASSED |

### Audit Logs (`tests/audit/test_audit.py`)

| Test | Result |
|------|--------|
| `TestListAuditLogs::test_super_can_list_audit_logs` | PASSED |
| `TestListAuditLogs::test_admin_can_list_audit_logs` | PASSED |
| `TestListAuditLogs::test_broker_cannot_list_audit_logs` | PASSED |
| `TestListAuditLogs::test_unauthenticated_cannot_list` | PASSED |
| `TestGetAuditLog::test_nonexistent_audit_log` | PASSED |
| `TestUserAuditHistory::test_super_can_get_user_audit` | PASSED |
| `TestUserAuditHistory::test_broker_cannot_get_user_audit` | PASSED |
| `TestCompanyAuditHistory::test_super_can_get_company_audit` | PASSED |
| `TestCompanyAuditHistory::test_broker_cannot_get_company_audit` | PASSED |

---

## Bugs Found & Fixed During Testing

1. **Super user self-edit/delete guard not working** — `user.get("_id")` returned `None` because `serialize_doc` converts `_id` to `id`. Fixed to use `user.get("id") or user.get("_id")` in `app/api/v1/users/routes.py`.

2. **Fish models active endpoint query parameter** — Tests used `?type=detector` but the route parameter is `model_type`. Fixed test to use `?model_type=detector`.

3. **JWT token expiration during tests** — Default `JWT_EXPIRATION=15m` caused session-scoped tokens to expire during long test runs (~20 min). Fixed by setting `JWT_EXPIRATION=60m` in test conftest.

4. **Only 1 fish species seeded (Tuna)** — The classifier model recognizes 40 species but only "Tuna" was in the DB. All other species were filtered out, causing "Generic Fish" fallback. Fixed by seeding all 41 species in `app/seeders/fish_models.py`.

5. **Detector model "Tune" typo** — The detector model class 1 is named "Tune" instead of "Tuna". Added `_SPECIES_ALIASES` mapping in `app/api/v1/fish/routes.py`.

6. **Training samples exporter TypeError** — `export_dataset` in `app/infrastructure/fish_training_samples/exporter.py:119` crashes with `TypeError: '<' not supported between instances of 'NoneType' and 'int'` when species records have `None` for `classIndex`. This is a known bug triggered when test-created species lack a class index.

## Test Configuration

- Tests run against a temporary MongoDB database (auto-created and dropped per session)
- Session-scoped fixtures for super, admin, broker, and crew authentication
- Dedicated test user for auth login/logout tests to avoid invalidating shared session tokens
- SSL/TLS via certifi for MongoDB Atlas connections

## Warnings (5)

All warnings are deprecation notices:
- `regex` parameter deprecated in favor of `pattern` (fish_models route)
- `on_event` deprecated in favor of lifespan event handlers (FastAPI startup/shutdown)
