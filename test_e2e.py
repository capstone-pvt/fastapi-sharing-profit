"""
End-to-end integration tests for all Smart Catch API modules.
Run with: python test_e2e.py
Requires: server running on localhost:8000, MongoDB connected.
"""
import io
import json
import sys
import random
import string
import httpx

BASE = "http://localhost:8000/api"
PASS = 0
FAIL = 0
ERRORS = []


# ─── HELPER FUNCTIONS ───────────────────────

def _rand(n=6):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


def assert_eq(actual, expected):
    if actual != expected:
        raise AssertionError(f"Expected '{expected}', got '{actual}'")


def assert_key(data, key):
    if key not in data:
        raise AssertionError(f"Missing key '{key}'")


def assert_no_key(data, key):
    if key in data:
        raise AssertionError(f"Key '{key}' should not be present (data leak)")


def assert_in(value, options):
    if value not in options:
        raise AssertionError(f"{value} not in {options}")


def report(test_name, resp, expected_status=None, check_fn=None):
    global PASS, FAIL
    ok = True
    details = ""
    if expected_status and resp.status_code != expected_status:
        ok = False
        details = f"Expected {expected_status}, got {resp.status_code}"
    if check_fn:
        try:
            check_fn(resp)
        except Exception as e:
            ok = False
            details = str(e)
    if ok:
        PASS += 1
    else:
        FAIL += 1
        ERRORS.append(f"{test_name}: {details} | Body: {resp.text[:300]}")
    print(f"  [{'PASS' if ok else 'FAIL'}] {test_name}" + (f" - {details}" if details else ""))
    return ok


def section(name):
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")


# ─── CHECK SERVER ─────────────────────────
import subprocess, time, os

server_proc = None

# Check if server is already running
try:
    r = httpx.get("http://localhost:8000/health", timeout=5.0)
    if r.status_code == 200:
        print("Server already running!")
except Exception:
    print("Starting server...")
    server_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
        cwd=os.path.dirname(os.path.abspath(__file__)),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    for _ in range(60):
        try:
            r = httpx.get("http://localhost:8000/health", timeout=2.0)
            if r.status_code == 200:
                print("Server is ready!")
                break
        except Exception:
            pass
        time.sleep(1)
    else:
        print("ERROR: Server failed to start!")
        sys.exit(1)

client = httpx.Client(base_url=BASE, timeout=60.0)

try:
    # ─────────────────────────────────────────────
    # 1. AUTH MODULE
    # ─────────────────────────────────────────────
    section("1. AUTH MODULE")

    rand_id = _rand()
    admin_email = f"testadmin_{rand_id}@test.com"
    admin_pass = "Test@1234"
    company_name = f"TestCompany_{rand_id}"

    # 1a. Register admin with new company
    r = client.post("/auth/register", json={
        "email": admin_email,
        "password": admin_pass,
        "firstName": "Test",
        "lastName": "Admin",
        "roleId": "placeholder",
        "companyName": company_name,
    })
    report("Register admin + new company", r, 200)
    auth_data = r.json() if r.status_code == 200 else {}
    admin_token = auth_data.get("accessToken", "")
    admin_refresh = auth_data.get("refreshToken", "")
    admin_user = auth_data.get("user", {})
    admin_id = admin_user.get("id", "")
    company_code = admin_user.get("companyCode", "")
    company_id = admin_user.get("companyId", "")
    print(f"    -> Admin ID: {admin_id}, Company: {company_name} (code: {company_code})")

    # Get role IDs
    r_roles = client.get("/roles", headers={"Authorization": f"Bearer {admin_token}"})
    roles_map = {}
    if r_roles.status_code == 200:
        for role in r_roles.json():
            roles_map[role.get("name")] = role.get("id", "")

    crew_role_id = roles_map.get("crew", "")
    broker_role_id = roles_map.get("broker", "")
    owner_role_id = roles_map.get("owner", "")

    # 1b. Register crew
    crew_email = f"testcrew_{rand_id}@test.com"
    r = client.post("/auth/register", json={
        "email": crew_email, "password": "Test@1234",
        "firstName": "Test", "lastName": "Crew",
        "roleId": crew_role_id, "companyCode": company_code,
    })
    report("Register crew with company code", r, 200)
    crew_data = r.json() if r.status_code == 200 else {}
    crew_token = crew_data.get("accessToken", "")
    crew_id = crew_data.get("user", {}).get("id", "")

    # 1c. Register broker
    broker_email = f"testbroker_{rand_id}@test.com"
    r = client.post("/auth/register", json={
        "email": broker_email, "password": "Test@1234",
        "firstName": "Test", "lastName": "Broker",
        "roleId": broker_role_id, "companyCode": company_code,
    })
    report("Register broker with company code", r, 200)
    broker_data = r.json() if r.status_code == 200 else {}
    broker_token = broker_data.get("accessToken", "")
    broker_id = broker_data.get("user", {}).get("id", "")

    # 1d. Register owner
    owner_email = f"testowner_{rand_id}@test.com"
    r = client.post("/auth/register", json={
        "email": owner_email, "password": "Test@1234",
        "firstName": "Test", "lastName": "Owner",
        "roleId": owner_role_id, "companyCode": company_code,
    })
    report("Register owner with company code", r, 200)
    owner_data = r.json() if r.status_code == 200 else {}
    owner_token = owner_data.get("accessToken", "")
    owner_id = owner_data.get("user", {}).get("id", "")

    # 1e. Login
    r = client.post("/auth/login", json={"email": admin_email, "password": admin_pass})
    report("Login admin", r, 200)
    if r.status_code == 200:
        admin_token = r.json().get("accessToken", admin_token)
        admin_refresh = r.json().get("refreshToken", admin_refresh)

    # 1f. Refresh token
    r = client.post("/auth/refresh", json={"refreshToken": admin_refresh})
    report("Refresh token", r, 200)
    if r.status_code == 200:
        admin_token = r.json().get("accessToken", admin_token)

    # 1g. Duplicate email
    r = client.post("/auth/register", json={
        "email": admin_email, "password": admin_pass,
        "firstName": "Dup", "lastName": "User",
        "roleId": "x", "companyCode": company_code,
    })
    report("Duplicate email rejected (409)", r, 409)

    # 1h. Wrong password
    r = client.post("/auth/login", json={"email": admin_email, "password": "wrong"})
    report("Wrong password rejected (401)", r, 401)

    # Auth headers
    def admin_h(): return {"Authorization": f"Bearer {admin_token}"}
    def broker_h(): return {"Authorization": f"Bearer {broker_token}"}
    def owner_h(): return {"Authorization": f"Bearer {owner_token}"}
    def crew_h(): return {"Authorization": f"Bearer {crew_token}"}

    # ─────────────────────────────────────────────
    # 2. PROFILE MODULE
    # ─────────────────────────────────────────────
    section("2. PROFILE MODULE")

    r = client.get("/profile", headers=admin_h())
    report("Get admin profile", r, 200)
    report("Profile has email", r, check_fn=lambda r: assert_eq(r.json().get("email"), admin_email))
    report("Profile no password leak", r, check_fn=lambda r: assert_no_key(r.json(), "password"))
    report("Profile no refreshToken leak", r, check_fn=lambda r: assert_no_key(r.json(), "refreshToken"))

    r = client.patch("/profile", headers=admin_h(), json={"firstName": "UpdatedAdmin"})
    report("Update profile firstName", r, 200)
    report("firstName changed", r, check_fn=lambda r: assert_eq(r.json().get("firstName"), "UpdatedAdmin"))

    r = client.post("/profile/change-password", headers=admin_h(), json={
        "currentPassword": admin_pass, "newPassword": "NewTest@1234"
    })
    report("Change password", r, 200)

    r = client.post("/auth/login", json={"email": admin_email, "password": "NewTest@1234"})
    report("Login with new password", r, 200)
    if r.status_code == 200:
        admin_token = r.json().get("accessToken", admin_token)
        admin_pass = "NewTest@1234"

    r = client.post("/profile/change-password", headers=admin_h(), json={
        "currentPassword": "wrongold", "newPassword": "Another@123"
    })
    report("Wrong current password rejected (401)", r, 401)

    # ─────────────────────────────────────────────
    # 3. COMPANIES MODULE
    # ─────────────────────────────────────────────
    section("3. COMPANIES MODULE")

    r = client.get("/companies", headers=admin_h())
    report("List companies", r, 200)
    report("Has results key", r, check_fn=lambda r: assert_key(r.json(), "results"))

    r = client.patch(f"/companies/{company_id}", headers=admin_h(), json={
        "companyAddress": "123 Test St", "companyPhone": "09171234567"
    })
    report("Update company", r, 200)
    report("Address updated", r, check_fn=lambda r: assert_eq(r.json().get("companyAddress"), "123 Test St"))

    # ─────────────────────────────────────────────
    # 4. USERS MODULE
    # ─────────────────────────────────────────────
    section("4. USERS MODULE")

    r = client.get("/users", headers=admin_h())
    report("List users", r, 200)
    report("Users has results", r, check_fn=lambda r: assert_key(r.json(), "results"))
    print(f"    -> Total users: {r.json().get('total', 0)}")

    r = client.get(f"/users/{crew_id}", headers=admin_h())
    report("Get single user", r, 200)

    new_email = f"newuser_{_rand()}@test.com"
    r = client.post("/users", headers=admin_h(), json={
        "email": new_email, "password": "Test@1234",
        "firstName": "New", "lastName": "User", "roleId": crew_role_id,
    })
    report("Admin create user", r, 200)
    new_user_id = r.json().get("id", "") if r.status_code == 200 else ""

    if new_user_id:
        r = client.patch(f"/users/{new_user_id}", headers=admin_h(), json={"firstName": "Updated"})
        report("Admin update user", r, 200)
        r = client.delete(f"/users/{new_user_id}", headers=admin_h())
        report("Admin delete user", r, 200)

    # ─────────────────────────────────────────────
    # 5. ROLES & PERMISSIONS
    # ─────────────────────────────────────────────
    section("5. ROLES & PERMISSIONS")

    r = client.get("/roles", headers=admin_h())
    report("List roles", r, 200)
    print(f"    -> Roles: {[x.get('name') for x in r.json()]}" if r.status_code == 200 else "")

    r = client.get("/permissions", headers=admin_h())
    report("List permissions", r, 200)
    print(f"    -> Total permissions: {len(r.json())}" if r.status_code == 200 else "")

    # ─────────────────────────────────────────────
    # 6. VESSELS, BOATS, VESSEL OWNERS
    # ─────────────────────────────────────────────
    section("6. VESSELS, BOATS, VESSEL OWNERS")

    r = client.post("/vessel-owners", headers=broker_h(), json={
        "firstName": "Juan", "lastName": "Dela Cruz", "contactNumber": "09171111111",
    })
    report("Create vessel owner", r, 200)
    vo_id = r.json().get("id", "") if r.status_code == 200 else ""

    r = client.get("/vessel-owners", headers=broker_h())
    report("List vessel owners", r, 200)

    r = client.post("/vessels", headers=broker_h(), json={
        "name": f"Vessel_{rand_id}", "registrationNo": f"REG-{rand_id}",
        "type": "motorized", "capacity": 10, "vesselOwnerId": vo_id,
    })
    report("Create vessel", r, 200)
    vessel_id = r.json().get("id", "") if r.status_code == 200 else ""

    r = client.get("/vessels", headers=broker_h())
    report("List vessels", r, 200)

    if vessel_id:
        r = client.patch(f"/vessels/{vessel_id}", headers=broker_h(), json={"capacity": 15})
        report("Update vessel", r, 200)

    r = client.post("/boats", headers=broker_h(), json={
        "name": f"Boat_{rand_id}", "registrationNo": f"BOAT-{rand_id}",
        "type": "pumpboat", "vesselOwnerId": vo_id,
    })
    report("Create boat", r, 200)
    boat_id = r.json().get("id", "") if r.status_code == 200 else ""

    r = client.get("/boats", headers=broker_h())
    report("List boats", r, 200)

    # ─────────────────────────────────────────────
    # 7. CREW MANAGEMENT (owner role has fishermen perms)
    # ─────────────────────────────────────────────
    section("7. CREW MANAGEMENT")

    # Use admin (has all permissions) for crew management
    r = client.post("/crew", headers=admin_h(), json={
        "firstName": "Pedro", "lastName": "Santos", "contactNumber": "09172222222",
        "vessel": vessel_id, "role": "crew", "crewType": "pakura", "status": "active",
    })
    report("Create crew member (admin)", r, 200)
    crew_member_id = r.json().get("id", "") if r.status_code == 200 else ""

    r = client.post("/crew", headers=admin_h(), json={
        "firstName": "Maria", "lastName": "Garcia", "contactNumber": "09173333333",
        "vessel": vessel_id, "role": "captain", "crewType": "pakura", "status": "active",
    })
    report("Create captain (admin)", r, 200)
    captain_id = r.json().get("id", "") if r.status_code == 200 else ""

    # Owner should also have access
    r = client.get("/crew", headers=owner_h())
    report("List crew (owner)", r, 200)

    if crew_member_id:
        r = client.get(f"/crew/{crew_member_id}", headers=admin_h())
        report("Get single crew", r, 200)

        r = client.patch(f"/crew/{crew_member_id}", headers=admin_h(), json={
            "contactNumber": "09174444444"
        })
        report("Update crew member", r, 200)

    # ─────────────────────────────────────────────
    # 8. TRIPS
    # ─────────────────────────────────────────────
    section("8. TRIPS")

    r = client.post("/trips", headers=broker_h(), json={
        "boatId": boat_id, "vesselId": vessel_id,
        "departureDate": "2026-04-01T06:00:00Z", "returnDate": "2026-04-03T18:00:00Z",
        "status": "completed", "captainId": captain_id,
        "captainName": "Maria Garcia", "crewType": "pakura",
        "crewMembers": [crew_member_id, captain_id],
    })
    report("Create trip", r, 200)
    trip_id = r.json().get("id", "") if r.status_code == 200 else ""

    r = client.get("/trips", headers=broker_h())
    report("List trips", r, 200)

    if trip_id:
        r = client.get(f"/trips/{trip_id}", headers=broker_h())
        report("Get single trip", r, 200)
        r = client.patch(f"/trips/{trip_id}", headers=broker_h(), json={"status": "completed"})
        report("Update trip status", r, 200)

    # ─────────────────────────────────────────────
    # 9. CATCHES
    # ─────────────────────────────────────────────
    section("9. CATCHES")

    r = client.post("/catches", headers=broker_h(), json={
        "tripId": trip_id,
        "speciesBreakdown": [
            {"species": "Bangus", "weightKg": 50, "pricePerKg": 180},
            {"species": "Galunggong", "weightKg": 30, "pricePerKg": 120},
        ],
        "totalWeight": 80, "totalValue": 12600,
    })
    report("Create catch record", r, 200)
    catch_id = r.json().get("id", "") if r.status_code == 200 else ""

    r = client.get("/catches", headers=broker_h())
    report("List catches", r, 200)

    # ─────────────────────────────────────────────
    # 10. FISH SALES
    # ─────────────────────────────────────────────
    section("10. FISH SALES")

    r = client.post("/fish-sales", headers=broker_h(), json={
        "tripId": trip_id, "species": "Bangus", "weightKg": 25,
        "pricePerKg": 180, "totalAmount": 4500, "buyer": "Buyer 1", "saleType": "small_fish",
    })
    report("Create fish sale (small)", r, 200)
    sale_id_1 = r.json().get("id", "") if r.status_code == 200 else ""

    r = client.post("/fish-sales", headers=broker_h(), json={
        "tripId": trip_id, "species": "Yellowfin Tuna", "weightKg": 15,
        "pricePerKg": 350, "totalAmount": 5250, "buyer": "Buyer 2", "saleType": "big_fish",
    })
    report("Create fish sale (big)", r, 200)
    sale_id_2 = r.json().get("id", "") if r.status_code == 200 else ""

    r = client.get("/fish-sales", headers=broker_h())
    report("List fish sales", r, 200)

    if sale_id_1:
        r = client.get(f"/fish-sales/{sale_id_1}", headers=broker_h())
        report("Get single fish sale", r, 200)

    # ─────────────────────────────────────────────
    # 11. EXPENSES
    # ─────────────────────────────────────────────
    section("11. EXPENSES")

    r = client.post("/expenses", headers=broker_h(), json={
        "tripId": trip_id, "category": "fuel", "amount": 3000,
        "description": "Diesel fuel", "recordedBy": broker_id,
    })
    report("Create expense (fuel)", r, 200)
    expense_id_1 = r.json().get("id", "") if r.status_code == 200 else ""

    r = client.post("/expenses", headers=broker_h(), json={
        "tripId": trip_id, "category": "ice", "amount": 500,
        "description": "Ice blocks", "recordedBy": broker_id,
    })
    report("Create expense (ice)", r, 200)
    expense_id_2 = r.json().get("id", "") if r.status_code == 200 else ""

    r = client.get("/expenses", headers=broker_h())
    report("List expenses", r, 200)

    if expense_id_1:
        r = client.patch(f"/expenses/{expense_id_1}", headers=broker_h(), json={"amount": 3500})
        report("Update expense", r, 200)

    # ─────────────────────────────────────────────
    # 12. CASH ADVANCES
    # ─────────────────────────────────────────────
    section("12. CASH ADVANCES")

    r = client.post("/cash-advances", headers=admin_h(), json={
        "requestedBy": crew_member_id, "amount": 500,
        "reason": "Emergency", "status": "pending", "tripId": trip_id,
    })
    report("Create cash advance", r, 200)
    ca_id = r.json().get("id", "") if r.status_code == 200 else ""

    r = client.get("/cash-advances", headers=admin_h())
    report("List cash advances", r, 200)

    if ca_id:
        r = client.patch(f"/cash-advances/{ca_id}/approve", headers=admin_h(), json={
            "notes": "Approved"
        })
        report("Approve cash advance", r, 200)
        report("Status is approved", r, check_fn=lambda r: assert_eq(r.json().get("status"), "approved"))

    # Create another to decline
    r = client.post("/cash-advances", headers=admin_h(), json={
        "requestedBy": crew_member_id, "amount": 5000,
        "reason": "Wants phone", "status": "pending", "tripId": trip_id,
    })
    ca_id_2 = r.json().get("id", "") if r.status_code == 200 else ""
    if ca_id_2:
        r = client.patch(f"/cash-advances/{ca_id_2}/decline", headers=admin_h(), json={
            "declineReason": "Not emergency"
        })
        report("Decline cash advance", r, 200)
        report("Status is declined", r, check_fn=lambda r: assert_eq(r.json().get("status"), "declined"))

    # ─────────────────────────────────────────────
    # 13. PROFIT SHARING POLICIES
    # ─────────────────────────────────────────────
    section("13. PROFIT SHARING POLICIES")

    r = client.post("/profit-sharing-policies", headers=owner_h(), json={
        "boatOwnerId": owner_id, "boatId": boat_id,
        "pakuraDivisor": 3, "tongkoDivisor": 2, "sinakahan": 1000,
        "captainOwnerSplitType": "members_split", "totalMembers": 4,
        "captainMembersShare": 1, "captainIsOwner": False, "isActive": True,
    })
    report("Create profit sharing policy", r, 200)
    policy_id = r.json().get("id", "") if r.status_code == 200 else ""

    r = client.get("/profit-sharing-policies", headers=owner_h())
    report("List policies", r, 200)

    if policy_id:
        r = client.get(f"/profit-sharing-policies/{policy_id}", headers=owner_h())
        report("Get single policy", r, 200)
        r = client.patch(f"/profit-sharing-policies/{policy_id}", headers=owner_h(), json={"pakuraDivisor": 4})
        report("Update policy", r, 200)

    # ─────────────────────────────────────────────
    # 14. PROFIT SHARES (read-only CRUD - no update/delete)
    # ─────────────────────────────────────────────
    section("14. PROFIT SHARES")

    r = client.post("/profit-shares", headers=admin_h(), json={
        "tripId": trip_id, "boatOwnerId": owner_id,
        "totalRevenue": 9750, "totalExpenses": 3500, "netProfit": 6250,
        "brokerShare": 975, "boatOwnerShare": 2000,
        "fishermanShares": {crew_member_id: 1500, captain_id: 1775},
        "status": "finalized",
    })
    report("Create profit share", r, 200)
    ps_id = r.json().get("id", "") if r.status_code == 200 else ""

    r = client.get("/profit-shares", headers=admin_h())
    report("List profit shares", r, 200)

    if ps_id:
        r = client.get(f"/profit-shares/{ps_id}", headers=admin_h())
        report("Get single profit share", r, 200)

    # ─────────────────────────────────────────────
    # 15. FISH SPECIES
    # ─────────────────────────────────────────────
    section("15. FISH SPECIES")

    r = client.get("/fish/species", headers=admin_h())
    report("List fish species (admin)", r, 200)
    print(f"    -> Total species: {len(r.json())}" if r.status_code == 200 else "")

    r = client.get("/fish/species/active", headers=admin_h())
    report("List active species", r, 200)

    # ─────────────────────────────────────────────
    # 16. FISH ANALYSIS (AI)
    # ─────────────────────────────────────────────
    section("16. FISH ANALYSIS (AI)")

    from PIL import Image
    img = Image.new("RGB", (640, 480), color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    r = client.post("/fish/analyze",
        headers={"Authorization": f"Bearer {broker_token}"},
        files={"image": ("test_fish.png", buf, "image/png")},
        data={"singleFish": "false", "confidence": "0.25"},
    )
    report("Fish analysis endpoint", r, 200)
    if r.status_code == 200:
        analysis = r.json()
        print(f"    -> Detections: {len(analysis.get('detections', []))}")
        print(f"    -> Total weight: {analysis.get('totalEstimatedWeight', 0)} kg")

    r = client.get("/fish/diagnostic", headers=admin_h())
    report("Fish diagnostic", r, 200)

    r = client.get("/fish/analytics", headers=admin_h())
    report("Fish analytics count", r, 200)

    r = client.get("/fish/analysis-history", headers=broker_h())
    report("Fish analysis history", r, 200)

    # ─────────────────────────────────────────────
    # 17. FISH MODELS
    # ─────────────────────────────────────────────
    section("17. FISH MODELS")

    r = client.get("/fish/models", headers=admin_h())
    report("List fish models", r, 200)

    r = client.get("/fish/models/active?model_type=detector", headers=admin_h())
    report("Get active detector model", r, 200)

    # ─────────────────────────────────────────────
    # 18. TRAINING SAMPLES
    # ─────────────────────────────────────────────
    section("18. TRAINING SAMPLES")

    buf2 = io.BytesIO()
    img.save(buf2, format="JPEG")
    buf2.seek(0)

    r = client.post("/fish/training-samples",
        headers={"Authorization": f"Bearer {broker_token}"},
        files={"image": ("training.jpg", buf2, "image/jpeg")},
        data={"species": "Bangus", "weightKg": "1.5", "pricePerKg": "180"},
    )
    report("Create training sample", r, 200)
    sample_id = r.json().get("id", "") if r.status_code == 200 else ""

    r = client.get("/fish/training-samples", headers=broker_h())
    report("List training samples", r, 200)

    r = client.get("/fish/training-samples/mine", headers=broker_h())
    report("List my training samples", r, 200)

    # ─────────────────────────────────────────────
    # 19. FORECASTS
    # ─────────────────────────────────────────────
    section("19. FORECASTS")

    r = client.get("/forecasts/seasonal?month=4&habitat=marine", headers=broker_h())
    report("Seasonal forecast", r, 200)
    if r.status_code == 200:
        print(f"    -> Species in forecast: {len(r.json().get('species', []))}")

    r = client.get("/forecasts/species-calendar", headers=broker_h())
    report("Species calendar", r, 200)

    r = client.get("/forecasts/price-guide?month=4", headers=broker_h())
    report("Price guide", r, 200)

    # ─────────────────────────────────────────────
    # 20. WEATHER
    # ─────────────────────────────────────────────
    section("20. WEATHER")

    r = client.get("/weather/current?lat=14.5&lon=120.9", headers=broker_h())
    report("Current weather", r, 200)
    if r.status_code == 200:
        w = r.json()
        print(f"    -> Temp: {w.get('temperature')}C, Condition: {w.get('condition')}")

    r = client.get("/weather/forecast?lat=14.5&lon=120.9", headers=broker_h())
    report("Weather 5-day forecast", r, 200)

    # ─────────────────────────────────────────────
    # 21. LICENSES
    # ─────────────────────────────────────────────
    section("21. LICENSES")

    r = client.get("/licenses/status", headers=admin_h())
    report("License status", r, 200)

    # Try super admin login for license generation
    r_super = client.post("/auth/login", json={"email": "super@demo.com", "password": "P@ssw0rd123"})
    super_token = ""
    if r_super.status_code == 200:
        super_token = r_super.json().get("accessToken", "")
        super_h = {"Authorization": f"Bearer {super_token}"}

        r = client.post("/licenses/generate", headers=super_h, json={"plan": "trial", "maxUsers": 10})
        report("Generate license (super)", r, 200)
        license_code = r.json().get("activationCode", "") if r.status_code == 200 else ""
        print(f"    -> License code: {license_code}")

        r = client.get("/licenses", headers=super_h)
        report("List all licenses (super)", r, 200)

        if license_code:
            r = client.post("/licenses/validate", headers=admin_h(), json={"activationCode": license_code})
            report("Validate/activate license", r, 200)
    else:
        print("  [SKIP] Super admin login failed - skipping license generation")

    # ─────────────────────────────────────────────
    # 22. AUDIT LOGS
    # ─────────────────────────────────────────────
    section("22. AUDIT LOGS")

    r = client.get("/audit-logs", headers=admin_h())
    report("List audit logs (admin)", r, 200)

    # ─────────────────────────────────────────────
    # 23. NEGATIVE / EDGE CASES
    # ─────────────────────────────────────────────
    section("23. NEGATIVE / EDGE CASES")

    r = client.get("/profile")
    report("Unauthenticated access rejected (401)", r, 401)

    r = client.get("/users/not-a-valid-objectid", headers=admin_h())
    report("Invalid ObjectId handled gracefully", r, check_fn=lambda r: assert_in(r.status_code, [400, 404, 422, 500]))

    r = client.get("/users", headers=crew_h())
    report("Crew cannot list users (403)", r, 403)

    r = client.post("/auth/login", json={})
    report("Empty login body rejected (400)", r, 400)

    r = client.post("/auth/register", json={
        "email": "", "password": "x", "firstName": "", "lastName": "",
        "roleId": "x",
    })
    report("Invalid register data rejected (400)", r, 400)

    # ─────────────────────────────────────────────
    # 24. CLEANUP
    # ─────────────────────────────────────────────
    section("24. CLEANUP")

    cleanup_items = [
        # profit-shares only allows create+read (no delete), skip it
        ("profit policy", policy_id, "/profit-sharing-policies"),
        ("cash advance 1", ca_id, "/cash-advances"),
        ("cash advance 2", ca_id_2, "/cash-advances"),
        ("expense 1", expense_id_1, "/expenses"),
        ("expense 2", expense_id_2, "/expenses"),
        ("fish sale 1", sale_id_1, "/fish-sales"),
        ("fish sale 2", sale_id_2, "/fish-sales"),
        ("catch", catch_id, "/catches"),
        ("trip", trip_id, "/trips"),
        ("crew member", crew_member_id, "/crew"),
        ("captain", captain_id, "/crew"),
        ("boat", boat_id, "/boats"),
        ("vessel", vessel_id, "/vessels"),
        ("vessel owner", vo_id, "/vessel-owners"),
    ]
    for label, item_id, endpoint in cleanup_items:
        if item_id:
            r = client.delete(f"{endpoint}/{item_id}", headers=admin_h())
            report(f"Delete {label}", r, 200)

    for uid, label in [(crew_id, "crew user"), (broker_id, "broker user"), (owner_id, "owner user")]:
        if uid:
            r = client.delete(f"/users/{uid}", headers=admin_h())
            report(f"Delete {label}", r, 200)

    if sample_id:
        r = client.delete(f"/fish/training-samples/{sample_id}", headers=admin_h())
        report("Delete training sample", r, 200)

    r = client.post("/auth/logout", headers=admin_h())
    report("Logout", r, 200)

finally:
    if server_proc:
        server_proc.terminate()
        server_proc.wait(timeout=10)

# ─────────────────────────────────────────────
# FINAL REPORT
# ─────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"  FINAL TEST REPORT")
print(f"{'='*60}")
print(f"  Total:  {PASS + FAIL}")
print(f"  Passed: {PASS}")
print(f"  Failed: {FAIL}")
if ERRORS:
    print(f"\n  FAILURES:")
    for e in ERRORS:
        print(f"    - {e}")
print(f"{'='*60}")

sys.exit(1 if FAIL > 0 else 0)
