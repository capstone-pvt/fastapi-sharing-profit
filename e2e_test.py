"""End-to-end API test for all modules."""
import requests
import json

BASE = "http://localhost:8000"
results = []


def test(name, method, url, **kwargs):
    kwargs.setdefault("timeout", 15)
    try:
        r = getattr(requests, method)(f"{BASE}{url}", **kwargs)
        ok = r.status_code < 400
        results.append((name, r.status_code, ok))
        return r
    except Exception as e:
        results.append((name, str(e)[:60], False))
        return None


# ─── 1. Health ───
test("Health", "get", "/health")
test("Root", "get", "/")

# ─── 2. Auth Register (use unique email to avoid conflicts) ───
import time as _time
_ts = str(int(_time.time()))[-6:]
_email = f"e2e_{_ts}@test.com"

reg = test("Auth Register", "post", "/api/auth/register", json={
    "email": _email, "password": "Test1234!",
    "firstName": "E2E", "lastName": "Tester", "companyName": f"E2E Co {_ts}",
})
token = refresh = user_id = company_id = None
if reg and reg.status_code < 400:
    d = reg.json()
    token = d.get("accessToken")
    refresh = d.get("refreshToken")
    user_id = d.get("user", {}).get("id")
    company_id = d.get("user", {}).get("companyId")

# ─── 3. Auth Login ───
login = test("Auth Login", "post", "/api/auth/login",
             json={"email": _email, "password": "Test1234!"})
if login and login.status_code < 400:
    d = login.json()
    token = d["accessToken"]
    refresh = d["refreshToken"]
    user_id = user_id or d.get("user", {}).get("id")
    company_id = company_id or d.get("user", {}).get("companyId")

H = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"} if token else {}

# Auth Refresh
test("Auth Refresh", "post", "/api/auth/refresh", json={"refreshToken": refresh or ""})

# ─── 4. Profile ───
test("Profile GET", "get", "/api/profile", headers=H)
test("Profile PATCH", "patch", "/api/profile", headers=H,
     json={"firstName": "E2EUpdated"})
# Change password and change back to avoid breaking subsequent tests
test("Profile Change Password", "post", "/api/profile/change-password",
     headers=H, json={"currentPassword": "Test1234!", "newPassword": "Test1234!!"})
test("Profile Change Password Back", "post", "/api/profile/change-password",
     headers=H, json={"currentPassword": "Test1234!!", "newPassword": "Test1234!"})

# ─── 5. Roles & Permissions ───
test("Roles GET", "get", "/api/roles", headers=H)
test("Permissions GET", "get", "/api/permissions", headers=H)

# ─── 6. Users CRUD ───
u = test("Users CREATE", "post", "/api/users", headers=H,
         json={"email": f"crew_{_ts}@test.com", "password": "Test1234!",
               "firstName": "Crew", "lastName": "E2E"})
crew_id = u.json().get("id") if u and u.status_code < 400 else None
test("Users LIST", "get", "/api/users", headers=H)
if crew_id:
    test("Users GET", "get", f"/api/users/{crew_id}", headers=H)
    test("Users PATCH", "patch", f"/api/users/{crew_id}", headers=H,
         json={"firstName": "CrewUpdated"})

# ─── 7. Companies ───
test("Companies LIST", "get", "/api/companies", headers=H)
if company_id:
    test("Companies PATCH", "patch", f"/api/companies/{company_id}",
         headers=H, json={"companyAddress": "123 E2E St"})

# ─── 8. CRUD Collections ───
collections = {
    "vessels": {"name": "E2E Vessel", "registrationNumber": "E2E-001",
                "type": "Trawler", "capacity": 10},
    "boats": {"name": "E2E Boat", "type": "Outrigger", "capacity": 5},
    "vessel-owners": {"firstName": "E2E", "lastName": "Owner",
                      "contactNumber": "+639170000000"},
    "crew": {"firstName": "E2E", "lastName": "CrewMember", "role": "crew",
             "status": "active", "crewType": "pakura"},
}
created_ids = {}
for col, data in collections.items():
    r = test(f"{col} CREATE", "post", f"/api/{col}", headers=H, json=data)
    if r and r.status_code < 400:
        created_ids[col] = r.json().get("id")
    test(f"{col} LIST", "get", f"/api/{col}", headers=H)

# Trip
trip_data = {
    "boatId": created_ids.get("boats", ""),
    "vesselId": created_ids.get("vessels", ""),
    "departureDate": "2026-04-01", "returnDate": "2026-04-03",
    "status": "completed", "destination": "E2E Sea",
    "captainId": crew_id or "", "captainName": "CrewUpdated E2E",
    "crewType": "pakura",
    "crewMembers": [created_ids["crew"]] if created_ids.get("crew") else [],
}
tr = test("trips CREATE", "post", "/api/trips", headers=H, json=trip_data)
trip_id = tr.json().get("id") if tr and tr.status_code < 400 else None
test("trips LIST", "get", "/api/trips", headers=H)
if trip_id:
    test("trips PATCH", "patch", f"/api/trips/{trip_id}", headers=H,
         json={"status": "completed"})

# Expenses
exp = test("expenses CREATE", "post", "/api/expenses", headers=H,
           json={"tripId": trip_id or "", "category": "Fuel",
                 "amount": 5000, "description": "E2E Fuel"})
exp_id = exp.json().get("id") if exp and exp.status_code < 400 else None
test("expenses LIST", "get", "/api/expenses", headers=H)

# Fish Sales
fs = test("fish-sales CREATE", "post", "/api/fish-sales", headers=H,
          json={"tripId": trip_id or "", "species": "Tuna", "weightKg": 50,
                "pricePerKg": 250, "totalAmount": 12500, "buyer": "E2E Buyer"})
fs_id = fs.json().get("id") if fs and fs.status_code < 400 else None
test("fish-sales LIST", "get", "/api/fish-sales", headers=H)

# Catches
ct = test("catches CREATE", "post", "/api/catches", headers=H,
          json={"tripId": trip_id or "", "species": "Bangus",
                "weightKg": 30, "quantity": 15})
ct_id = ct.json().get("id") if ct and ct.status_code < 400 else None
test("catches LIST", "get", "/api/catches", headers=H)

# Cash Advances
ca = test("cash-advances CREATE", "post", "/api/cash-advances", headers=H,
          json={"requestedBy": crew_id or "", "amount": 2000,
                "reason": "E2E test", "status": "pending"})
ca_id = ca.json().get("id") if ca and ca.status_code < 400 else None
test("cash-advances LIST", "get", "/api/cash-advances", headers=H)
if ca_id:
    test("cash-advances APPROVE", "patch",
         f"/api/cash-advances/{ca_id}/approve", headers=H, json={"notes": "ok"})

# Profit Sharing Policies
psp = test("profit-sharing-policies CREATE", "post",
           "/api/profit-sharing-policies", headers=H,
           json={"name": "E2E Policy", "ownerShare": 60, "crewShare": 40,
                 "isDefault": True, "pakuraDivisor": 3, "tongkoDivisor": 2,
                 "sinakahan": 1000, "captainOwnerSplitType": "members_split",
                 "totalMembers": 4, "captainMembersShare": 1})
psp_id = psp.json().get("id") if psp and psp.status_code < 400 else None
test("profit-sharing-policies LIST", "get",
     "/api/profit-sharing-policies", headers=H)

# Profit Shares
test("profit-shares CREATE", "post", "/api/profit-shares", headers=H,
     json={"tripId": trip_id or "", "totalRevenue": 12500,
           "totalExpenses": 5000, "netProfit": 7500,
           "ownerShare": 4500, "crewShare": 3000})
test("profit-shares LIST", "get", "/api/profit-shares", headers=H)

# Forecasts
fc = test("forecasts CREATE", "post", "/api/forecasts", headers=H,
          json={"species": "Tuna", "month": 4,
                "estimatedCatch": 200, "pricePerKg": 250})
fc_id = fc.json().get("id") if fc and fc.status_code < 400 else None
test("forecasts LIST", "get", "/api/forecasts", headers=H)

# ─── 9. Fish AI Endpoints ───
test("Fish Diagnostic", "get", "/api/fish/diagnostic", headers=H)
test("Fish Analytics", "get", "/api/fish/analytics", headers=H)
test("Fish History", "get", "/api/fish/analysis-history?limit=3", headers=H)
test("Fish Species Active", "get", "/api/fish/species/active", headers=H)
test("Fish Species All", "get", "/api/fish/species", headers=H)
test("Fish Models", "get", "/api/fish/models", headers=H)

# ─── 10. Weather ───
test("Weather Current", "get",
     "/api/weather/current?lat=14.5995&lon=120.9842", headers=H)
test("Weather Forecast", "get",
     "/api/weather/forecast?lat=14.5995&lon=120.9842", headers=H)

# ─── 11. Forecast Endpoints ───
test("Seasonal Forecast", "get",
     "/api/forecasts/seasonal?month=4", headers=H)
test("Species Calendar", "get",
     "/api/forecasts/species-calendar", headers=H)
test("Price Guide", "get",
     "/api/forecasts/price-guide?month=4", headers=H)

# ─── 12. Misc ───
test("License Status", "get", "/api/licenses/status", headers=H)
test("Training Samples LIST", "get",
     "/api/fish/training-samples?limit=3", headers=H)

# ─── CLEANUP ───
cleanup = [
    ("forecasts", fc_id), ("profit-sharing-policies", psp_id),
    ("catches", ct_id), ("fish-sales", fs_id), ("expenses", exp_id),
    ("cash-advances", ca_id), ("trips", trip_id),
    ("crew", created_ids.get("crew")),
    ("vessel-owners", created_ids.get("vessel-owners")),
    ("boats", created_ids.get("boats")),
    ("vessels", created_ids.get("vessels")),
    ("users", crew_id),
]
for col, cid in cleanup:
    if cid:
        test(f"{col} DELETE", "delete", f"/api/{col}/{cid}", headers=H)

# Logout
test("Auth Logout", "post", "/api/auth/logout", headers=H,
     json={"refreshToken": refresh or ""})

# ─── REPORT ───
print()
passed = sum(1 for _, _, ok in results if ok)
failed = sum(1 for _, _, ok in results if not ok)
print(f"=== E2E RESULTS: {passed} PASSED, {failed} FAILED out of {len(results)} ===")
print()
for name, status, ok in results:
    icon = "PASS" if ok else "FAIL"
    print(f"  [{icon}] {name}: {status}")
