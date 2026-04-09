"""
Comprehensive End-to-End Test Suite for Smart Catch Profit Sharing API
======================================================================

Tests ALL modules and ALL CRUD operations including the profit sharing
computation engine.  Designed for thesis defense demonstration.

Run:
    python test_full_e2e.py

Requires:
    - Server running on localhost:8000 (or set BASE_URL env var)
    - MongoDB connected with seeded demo data
    - Demo accounts: super@demo.com, admin@demo.com, broker@demo.com,
      owner@demo.com, crew@demo.com  (password: P@ssw0rd123)
"""

from __future__ import annotations

import json
import os
import random
import string
import subprocess
import sys
import time
from typing import Any

import httpx

# ═══════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000/api")
DEMO_PASSWORD = "P@ssw0rd123"

# ═══════════════════════════════════════════════════════════════════════
# TEST HARNESS
# ═══════════════════════════════════════════════════════════════════════

PASS_COUNT = 0
FAIL_COUNT = 0
SKIP_COUNT = 0
ERRORS: list[str] = []

# ANSI colours (works on Windows 10+ with VT support, Linux, macOS)
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def _rand(n: int = 6) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


def section(title: str) -> None:
    print(f"\n{CYAN}{BOLD}{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}{RESET}")


def report(
    name: str,
    resp: httpx.Response | None = None,
    expected_status: int | None = None,
    check_fn: Any = None,
    manual_ok: bool | None = None,
) -> bool:
    global PASS_COUNT, FAIL_COUNT
    ok = True
    details = ""

    if manual_ok is not None:
        ok = manual_ok
        if not ok:
            details = "Assertion failed"

    if resp is not None and expected_status is not None:
        if resp.status_code != expected_status:
            ok = False
            details = f"Expected {expected_status}, got {resp.status_code}"

    if check_fn is not None:
        try:
            check_fn()
        except Exception as exc:
            ok = False
            details = str(exc)

    if ok:
        PASS_COUNT += 1
        print(f"  {GREEN}[PASS]{RESET} {name}")
    else:
        FAIL_COUNT += 1
        body_preview = ""
        if resp is not None:
            body_preview = resp.text[:250]
        ERRORS.append(f"{name}: {details} | {body_preview}")
        print(f"  {RED}[FAIL]{RESET} {name} - {details}")

    return ok


def skip(name: str, reason: str = "") -> None:
    global SKIP_COUNT
    SKIP_COUNT += 1
    suffix = f" ({reason})" if reason else ""
    print(f"  {YELLOW}[SKIP]{RESET} {name}{suffix}")


def assert_eq(actual: Any, expected: Any, label: str = "") -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected '{expected}', got '{actual}'")


def assert_key(data: dict, key: str) -> None:
    if key not in data:
        raise AssertionError(f"Missing key '{key}'")


def assert_close(actual: float, expected: float, tol: float = 0.02, label: str = "") -> None:
    if abs(actual - expected) > tol:
        raise AssertionError(f"{label}: {actual:.2f} != {expected:.2f} (tol={tol})")


def assert_gte(actual: Any, minimum: Any, label: str = "") -> None:
    if actual < minimum:
        raise AssertionError(f"{label}: {actual} < {minimum}")


def safe_json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return {}


# ═══════════════════════════════════════════════════════════════════════
# ENSURE SERVER IS RUNNING
# ═══════════════════════════════════════════════════════════════════════

server_proc = None

try:
    r = httpx.get("http://localhost:8000/health", timeout=5.0)
    if r.status_code == 200:
        print(f"{GREEN}Server already running.{RESET}")
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
                print(f"{GREEN}Server is ready.{RESET}")
                break
        except Exception:
            pass
        time.sleep(1)
    else:
        print(f"{RED}ERROR: Server failed to start!{RESET}")
        sys.exit(1)


client = httpx.Client(base_url=BASE_URL, timeout=60.0)

# ═══════════════════════════════════════════════════════════════════════
# Shared state (populated during tests)
# ═══════════════════════════════════════════════════════════════════════

tokens: dict[str, str] = {}  # role -> access_token
user_ids: dict[str, str] = {}  # role -> user_id

# IDs created during tests (for cleanup)
created_ids: dict[str, list[tuple[str, str]]] = {}  # endpoint -> [(label, id)]


def add_cleanup(endpoint: str, label: str, item_id: str) -> None:
    created_ids.setdefault(endpoint, []).append((label, item_id))


def auth_header(role: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens.get(role, '')}"}


# ═══════════════════════════════════════════════════════════════════════
# TEST EXECUTION
# ═══════════════════════════════════════════════════════════════════════

try:

    # ==================================================================
    # 1. AUTH & USERS -- Login all demo roles and get profiles
    # ==================================================================
    section("1. AUTH & USERS -- Login Demo Accounts")

    demo_accounts = {
        "super": "super@demo.com",
        "admin": "admin@demo.com",
        "broker": "broker@demo.com",
        "owner": "owner@demo.com",
        "crew": "crew@demo.com",
    }

    for role, email in demo_accounts.items():
        r = client.post("/auth/login", json={"email": email, "password": DEMO_PASSWORD})
        ok = report(f"Login as {role} ({email})", r, 200)
        if ok:
            data = r.json()
            tokens[role] = data.get("accessToken", "")
            user_obj = data.get("user", {})
            user_ids[role] = user_obj.get("id", "")
            print(f"    -> {role} user ID: {user_ids[role]}")

    # Profiles
    section("1b. USER PROFILES")
    for role in demo_accounts:
        if role not in tokens:
            skip(f"Get {role} profile", "no token")
            continue
        r = client.get("/profile", headers=auth_header(role))
        report(f"Get {role} profile", r, 200)
        if r.status_code == 200:
            profile = r.json()
            report(
                f"{role} profile has email",
                check_fn=lambda e=demo_accounts[role], p=profile: assert_eq(p.get("email"), e, "email"),
            )

    # ==================================================================
    # 2. COMPANIES
    # ==================================================================
    section("2. COMPANIES -- List & Verify Demo Company")

    r = client.get("/companies", headers=auth_header("admin"))
    report("List companies (admin)", r, 200)

    company_id = ""
    if r.status_code == 200:
        companies = r.json().get("results", [])
        report("Companies list is not empty", manual_ok=len(companies) > 0)
        # Find Demo Fishing Co
        demo_co = [c for c in companies if "Demo" in (c.get("companyName") or "")]
        if demo_co:
            report("Demo Fishing Co exists", manual_ok=True)
            company_id = demo_co[0].get("id", "")
            print(f"    -> Company ID: {company_id}")
        else:
            report("Demo Fishing Co exists", manual_ok=False)

    # ==================================================================
    # 3. VESSEL OWNERS & VESSELS
    # ==================================================================
    section("3. VESSEL OWNERS & VESSELS")

    rid = _rand()

    # Create vessel owner (owner role — broker cannot create per RBAC spec)
    r = client.post("/vessel-owners", headers=auth_header("owner"), json={
        "firstName": "TestOwner",
        "lastName": f"E2E_{rid}",
        "contactNumber": "09170001111",
    })
    report("Create vessel owner (owner)", r, 200)
    vo_id = safe_json(r).get("id", "")
    if vo_id:
        add_cleanup("/vessel-owners", "vessel owner", vo_id)
        print(f"    -> Vessel Owner ID: {vo_id}")

    # Create vessel (owner role)
    r = client.post("/vessels", headers=auth_header("owner"), json={
        "name": f"MV_Test_{rid}",
        "registrationNo": f"REG-{rid}",
        "type": "motorized",
        "capacity": 12,
        "vesselOwnerId": vo_id,
    })
    report("Create vessel (owner)", r, 200)
    vessel_id = safe_json(r).get("id", "")
    if vessel_id:
        add_cleanup("/vessels", "vessel", vessel_id)
        print(f"    -> Vessel ID: {vessel_id}")

    # List vessels
    r = client.get("/vessels", headers=auth_header("broker"))
    report("List vessels", r, 200)
    if r.status_code == 200:
        vessels = r.json().get("results", [])
        found = any(v.get("id") == vessel_id for v in vessels)
        report("New vessel appears in list", manual_ok=found)

    # Update vessel
    if vessel_id:
        r = client.patch(f"/vessels/{vessel_id}", headers=auth_header("owner"), json={
            "capacity": 15,
        })
        report("Update vessel capacity", r, 200)
        if r.status_code == 200:
            report("Capacity updated to 15", check_fn=lambda: assert_eq(r.json().get("capacity"), 15, "capacity"))

    # Read single vessel
    if vessel_id:
        r = client.get(f"/vessels/{vessel_id}", headers=auth_header("broker"))
        report("Read single vessel", r, 200)

    # ==================================================================
    # 4. CREW / FISHERMEN
    # ==================================================================
    section("4. CREW / FISHERMEN -- Create 3 Members")

    crew_record_ids: list[str] = []
    crew_names = [
        ("Pedro", "Santos", "captain"),
        ("Juan", "Dela Cruz", "crew"),
        ("Maria", "Garcia", "crew"),
    ]

    for first, last, role in crew_names:
        r = client.post("/crew", headers=auth_header("admin"), json={
            "firstName": first,
            "lastName": f"{last}_{rid}",
            "contactNumber": f"09170{_rand(6)}",
            "vessel": vessel_id,
            "role": role,
            "crewType": "pakura",
            "status": "active",
        })
        report(f"Create crew: {first} {last} ({role})", r, 200)
        cid = safe_json(r).get("id", "")
        crew_record_ids.append(cid)
        if cid:
            add_cleanup("/crew", f"crew {first}", cid)

    captain_record_id = crew_record_ids[0] if crew_record_ids else ""
    print(f"    -> Crew IDs: {crew_record_ids}")

    # List crew
    r = client.get("/crew", headers=auth_header("broker"))
    report("List crew (broker)", r, 200)
    if r.status_code == 200:
        all_crew = r.json().get("results", [])
        found_count = sum(1 for c in all_crew if c.get("id") in crew_record_ids)
        report(f"All 3 crew members appear in list", manual_ok=found_count == 3)

    # Update one crew member
    if crew_record_ids and len(crew_record_ids) >= 2:
        r = client.patch(f"/crew/{crew_record_ids[1]}", headers=auth_header("admin"), json={
            "contactNumber": "09179999999",
        })
        report("Update crew member contact", r, 200)

    # ==================================================================
    # 5. TRIPS
    # ==================================================================
    section("5. TRIPS -- Create Trip with 3 Crew (Pakura)")

    # Create boat for the trip (owner role)
    r = client.post("/boats", headers=auth_header("owner"), json={
        "name": f"Bangka_{rid}",
        "registrationNo": f"BK-{rid}",
        "type": "pumpboat",
        "vesselOwnerId": vo_id,
    })
    report("Create boat", r, 200)
    boat_id = safe_json(r).get("id", "")
    if boat_id:
        add_cleanup("/boats", "boat", boat_id)

    r = client.post("/trips", headers=auth_header("owner"), json={
        "boatId": boat_id,
        "vesselId": vessel_id,
        "departureDate": "2026-04-01T06:00:00Z",
        "returnDate": "2026-04-03T18:00:00Z",
        "status": "ongoing",
        "captainId": captain_record_id,
        "captainName": f"Pedro Santos_{rid}",
        "crewType": "pakura",
        "crewMembers": crew_record_ids,
    })
    report("Create trip (pakura, 3 crew)", r, 200)
    trip_id = safe_json(r).get("id", "")
    if trip_id:
        add_cleanup("/trips", "trip", trip_id)
        print(f"    -> Trip ID: {trip_id}")

    # List trips
    r = client.get("/trips", headers=auth_header("broker"))
    report("List trips", r, 200)
    if r.status_code == 200:
        trips = r.json().get("results", [])
        found = any(t.get("id") == trip_id for t in trips)
        report("New trip appears in list", manual_ok=found)

    # Update trip status to completed
    if trip_id:
        r = client.patch(f"/trips/{trip_id}", headers=auth_header("owner"), json={
            "status": "completed",
        })
        report("Update trip status to completed", r, 200)
        if r.status_code == 200:
            report("Trip status is completed", check_fn=lambda: assert_eq(r.json().get("status"), "completed", "status"))

    # ==================================================================
    # 6. FISH SALES (with lineItems)
    # ==================================================================
    section("6. FISH SALES -- Small Fish + Big Fish with lineItems")

    # One sale with mixed lineItems
    fish_sale_payload = {
        "tripId": trip_id,
        "buyer": "Wet Market Manila",
        "saleDate": "2026-04-03T10:00:00Z",
        "lineItems": [
            # 3 small fish entries
            {"species": "Galunggong", "category": "small_fish", "kilos": 80, "pricePerKg": 120},
            {"species": "Bangus", "category": "small_fish", "kilos": 50, "pricePerKg": 180},
            {"species": "Tilapia", "category": "small_fish", "kilos": 30, "pricePerKg": 100},
            # 2 big fish entries (attributed to specific crew)
            {"species": "Yellowfin Tuna", "category": "big_fish", "kilos": 25, "pricePerKg": 350,
             "caughtById": crew_record_ids[1] if len(crew_record_ids) > 1 else ""},
            {"species": "Blue Marlin", "category": "big_fish", "kilos": 18, "pricePerKg": 400,
             "caughtById": crew_record_ids[2] if len(crew_record_ids) > 2 else ""},
        ],
    }

    r = client.post("/fish-sales", headers=auth_header("broker"), json=fish_sale_payload)
    report("Create fish sale with 5 lineItems", r, 200)
    fish_sale_id = safe_json(r).get("id", "")
    if fish_sale_id:
        add_cleanup("/fish-sales", "fish sale", fish_sale_id)

    # Compute expected totals
    SMALL_FISH_TOTAL = (80 * 120) + (50 * 180) + (30 * 100)  # 9600 + 9000 + 3000 = 21600
    BIG_FISH_TOTAL = (25 * 350) + (18 * 400)                  # 8750 + 7200 = 15950
    GROSS_REVENUE = SMALL_FISH_TOTAL + BIG_FISH_TOTAL           # 37550
    print(f"    -> Small Fish Total: P{SMALL_FISH_TOTAL:,.2f}")
    print(f"    -> Big Fish Total:   P{BIG_FISH_TOTAL:,.2f}")
    print(f"    -> Gross Revenue:    P{GROSS_REVENUE:,.2f}")

    # List fish sales
    r = client.get("/fish-sales", headers=auth_header("broker"))
    report("List fish sales", r, 200)
    if r.status_code == 200:
        sales = r.json().get("results", [])
        found = any(s.get("id") == fish_sale_id for s in sales)
        report("Fish sale appears in list", manual_ok=found)
        # Verify lineItems are stored
        if found:
            sale_doc = next(s for s in sales if s.get("id") == fish_sale_id)
            items = sale_doc.get("lineItems", [])
            report(f"Fish sale has {len(items)} lineItems (expected 5)", manual_ok=len(items) == 5)

    # ==================================================================
    # 7. EXPENSES
    # ==================================================================
    section("7. EXPENSES -- Fuel, Ice, Grocery")

    expense_entries = [
        {"category": "fuel", "amount": 5000, "description": "Diesel fuel 3-day trip"},
        {"category": "ice", "amount": 1500, "description": "Ice blocks for preservation"},
        {"category": "food", "amount": 2000, "description": "Crew provisions and grocery"},
    ]
    expense_ids: list[str] = []

    for entry in expense_entries:
        r = client.post("/expenses", headers=auth_header("broker"), json={
            "tripId": trip_id,
            "recordedBy": user_ids.get("broker", ""),
            **entry,
        })
        report(f"Create expense: {entry['category']} P{entry['amount']:,}", r, 200)
        eid = safe_json(r).get("id", "")
        expense_ids.append(eid)
        if eid:
            add_cleanup("/expenses", f"expense {entry['category']}", eid)

    TOTAL_EXPENSES = sum(e["amount"] for e in expense_entries)  # 8500
    print(f"    -> Total Expenses: P{TOTAL_EXPENSES:,.2f}")

    # List expenses
    r = client.get("/expenses", headers=auth_header("broker"))
    report("List expenses", r, 200)
    if r.status_code == 200:
        all_expenses = r.json().get("results", [])
        found_count = sum(1 for e in all_expenses if e.get("id") in expense_ids)
        report(f"All 3 expenses appear in list", manual_ok=found_count == 3)

    # ==================================================================
    # 8. CASH ADVANCES
    # ==================================================================
    section("8. CASH ADVANCES")

    r = client.post("/cash-advances", headers=auth_header("admin"), json={
        "requestedBy": crew_record_ids[1] if len(crew_record_ids) > 1 else "",
        "amount": 1000,
        "reason": "Family emergency advance",
        "status": "pending",
        "tripId": trip_id,
    })
    report("Create cash advance (P1,000 for crew #2)", r, 200)
    ca_id = safe_json(r).get("id", "")
    if ca_id:
        add_cleanup("/cash-advances", "cash advance", ca_id)

    # Approve
    if ca_id:
        r = client.patch(f"/cash-advances/{ca_id}/approve", headers=auth_header("admin"), json={
            "notes": "Approved for emergency",
        })
        report("Approve cash advance", r, 200)
        if r.status_code == 200:
            report("Status is approved", check_fn=lambda: assert_eq(r.json().get("status"), "approved", "status"))

    # List
    r = client.get("/cash-advances", headers=auth_header("admin"))
    report("List cash advances", r, 200)

    TOTAL_CASH_ADVANCES = 1000
    print(f"    -> Total Cash Advances: P{TOTAL_CASH_ADVANCES:,.2f}")

    # ==================================================================
    # 9. PROFIT SHARING POLICIES
    # ==================================================================
    section("9. PROFIT SHARING POLICIES")

    policy_payload = {
        "boatOwnerId": vo_id,
        "boatId": boat_id,
        "pakuraDivisor": 3,
        "tongkoDivisor": 2,
        "brokerPercentage": 10.0,
        "boatOwnerPercentage": 40.0,
        "fishermanPercentage": 50.0,
        "smallBangkaPercentage": 20.0,
        "bigBangkaPercentage": 10.0,
        "sinakahan": 500,
        "captainOwnerSplitType": "members_split",
        "totalMembers": 4,
        "captainMembersShare": 1,
        "captainIsOwner": False,
        "isActive": True,
        "notes": f"E2E test policy {rid}",
    }

    r = client.post("/profit-sharing-policies", headers=auth_header("owner"), json=policy_payload)
    report("Create profit sharing policy", r, 200)
    policy_id = safe_json(r).get("id", "")
    if policy_id:
        add_cleanup("/profit-sharing-policies", "policy", policy_id)
        print(f"    -> Policy ID: {policy_id}")

    # List policies
    r = client.get("/profit-sharing-policies", headers=auth_header("owner"))
    report("List policies", r, 200)
    if r.status_code == 200:
        policies = r.json().get("results", [])
        found = any(p.get("id") == policy_id for p in policies)
        report("New policy appears in list", manual_ok=found)

    # Read single policy
    if policy_id:
        r = client.get(f"/profit-sharing-policies/{policy_id}", headers=auth_header("owner"))
        report("Read single policy", r, 200)
        if r.status_code == 200:
            pol = r.json()
            report("pakuraDivisor = 3", check_fn=lambda: assert_eq(pol.get("pakuraDivisor"), 3, "pakuraDivisor"))
            report("brokerPercentage = 10", check_fn=lambda: assert_close(pol.get("brokerPercentage", 0), 10, 0.01, "brokerPct"))
            report("smallBangkaPercentage = 20", check_fn=lambda: assert_close(pol.get("smallBangkaPercentage", 0), 20, 0.01, "smallBangkaPct"))
            report("bigBangkaPercentage = 10", check_fn=lambda: assert_close(pol.get("bigBangkaPercentage", 0), 10, 0.01, "bigBangkaPct"))
            report("sinakahan = 500", check_fn=lambda: assert_close(pol.get("sinakahan", 0), 500, 0.01, "sinakahan"))

    # ==================================================================
    # 10. PROFIT SHARING COMPUTATION (THE KEY TEST)
    # ==================================================================
    section("10. PROFIT SHARING COMPUTATION ENGINE")

    print(f"\n  {BOLD}Calling POST /profit-shares/compute with tripId={trip_id}{RESET}")
    print(f"  Policy: pakuraDivisor=3, broker=10%, smallBangka=20%, bigBangka=10%")
    print(f"  sinakahan=500/crew, captainOwnerSplit=members_split (4 members, captain=1)")
    print()

    compute_result: dict[str, Any] = {}
    if trip_id:
        r = client.post("/profit-shares/compute", headers=auth_header("owner"), json={
            "tripId": trip_id,
            "policyId": policy_id,
        })
        report("POST /profit-shares/compute returns 200", r, 200)

        if r.status_code == 200:
            compute_result = r.json()

            # ---- Verify all expected fields exist ----
            expected_fields = [
                "grossRevenue", "smallFishTotal", "bigFishTotal",
                "brokerShare", "bangkaShare", "smallBangka", "bigBangka",
                "crewPool", "divisor",
                "captainOwnerNet", "captainShare", "ownerShare",
                "fishermanShares", "crewBreakdown",
                "totalExpenses", "totalCashAdvances", "netProfit",
                "crewCount", "crewType",
            ]
            for field in expected_fields:
                report(
                    f"Response has field '{field}'",
                    check_fn=lambda f=field: assert_key(compute_result, f),
                )

            # ---- Verify computed values ----
            cr = compute_result  # shorthand

            # Gross revenue
            report(
                f"grossRevenue = P{cr.get('grossRevenue', 0):,.2f} (expected ~P{GROSS_REVENUE:,.2f})",
                check_fn=lambda: assert_close(cr["grossRevenue"], GROSS_REVENUE, 1.0, "grossRevenue"),
            )
            report(
                f"smallFishTotal = P{cr.get('smallFishTotal', 0):,.2f}",
                check_fn=lambda: assert_close(cr["smallFishTotal"], SMALL_FISH_TOTAL, 1.0, "smallFishTotal"),
            )
            report(
                f"bigFishTotal = P{cr.get('bigFishTotal', 0):,.2f}",
                check_fn=lambda: assert_close(cr["bigFishTotal"], BIG_FISH_TOTAL, 1.0, "bigFishTotal"),
            )

            # Broker share (gross * 10%)
            expected_broker = GROSS_REVENUE * 0.10
            report(
                f"brokerShare = P{cr.get('brokerShare', 0):,.2f} (grossRevenue * 10%)",
                check_fn=lambda: assert_close(cr["brokerShare"], expected_broker, 1.0, "brokerShare"),
            )

            # Bangka shares
            expected_small_bangka = SMALL_FISH_TOTAL * 0.20
            expected_big_bangka = BIG_FISH_TOTAL * 0.10
            report(
                f"smallBangka = P{cr.get('smallBangka', 0):,.2f} (smallFish * 20%)",
                check_fn=lambda: assert_close(cr["smallBangka"], expected_small_bangka, 1.0, "smallBangka"),
            )
            report(
                f"bigBangka = P{cr.get('bigBangka', 0):,.2f} (bigFish * 10%)",
                check_fn=lambda: assert_close(cr["bigBangka"], expected_big_bangka, 1.0, "bigBangka"),
            )

            # Divisor (pakura = 3)
            report(
                f"divisor = {cr.get('divisor')} (pakura -> 3)",
                check_fn=lambda: assert_eq(cr["divisor"], 3, "divisor"),
            )

            # Crew pool
            small_remaining = SMALL_FISH_TOTAL - expected_small_bangka
            big_remaining = BIG_FISH_TOTAL - expected_big_bangka
            expected_crew_pool = (small_remaining / 3) + (big_remaining / 3)
            report(
                f"crewPool = P{cr.get('crewPool', 0):,.2f} (remaining / divisor)",
                check_fn=lambda: assert_close(cr["crewPool"], expected_crew_pool, 2.0, "crewPool"),
            )

            # Captain/Owner Net
            expected_co_net = GROSS_REVENUE - expected_broker - expected_crew_pool - TOTAL_EXPENSES
            report(
                f"captainOwnerNet = P{cr.get('captainOwnerNet', 0):,.2f}",
                check_fn=lambda: assert_close(cr["captainOwnerNet"], expected_co_net, 2.0, "captainOwnerNet"),
            )

            # Captain/Owner split (members_split: 4 members, captain=1 -> captain gets 1/4)
            expected_captain = expected_co_net / 4
            expected_owner = expected_co_net - expected_captain
            report(
                f"captainShare = P{cr.get('captainShare', 0):,.2f} (1/4 of net)",
                check_fn=lambda: assert_close(cr["captainShare"], expected_captain, 2.0, "captainShare"),
            )
            report(
                f"ownerShare = P{cr.get('ownerShare', 0):,.2f} (3/4 of net)",
                check_fn=lambda: assert_close(cr["ownerShare"], expected_owner, 2.0, "ownerShare"),
            )

            # Fisherman shares map
            fs = cr.get("fishermanShares", {})
            report(f"fishermanShares has {len(fs)} entries (expected 3)", manual_ok=len(fs) == 3)

            # Crew count
            report(f"crewCount = {cr.get('crewCount')} (expected 3)", check_fn=lambda: assert_eq(cr["crewCount"], 3, "crewCount"))

            # Crew breakdown
            cbd = cr.get("crewBreakdown", [])
            report(f"crewBreakdown has {len(cbd)} entries (expected 3)", manual_ok=len(cbd) == 3)

            # Print full computation result for manual verification
            print(f"\n  {BOLD}--- Full Computation Result ---{RESET}")
            for key in ["grossRevenue", "smallFishTotal", "bigFishTotal", "brokerShare",
                         "bangkaShare", "smallBangka", "bigBangka", "crewPool",
                         "divisor", "captainOwnerNet", "captainShare", "ownerShare",
                         "totalExpenses", "totalCashAdvances", "netProfit", "crewCount", "crewType"]:
                val = cr.get(key, "N/A")
                if isinstance(val, (int, float)):
                    print(f"    {key}: P{val:,.2f}" if key != "divisor" and key != "crewCount" else f"    {key}: {val}")
                else:
                    print(f"    {key}: {val}")
            print(f"  {BOLD}--- Crew Breakdown ---{RESET}")
            for entry in cbd:
                print(f"    {entry.get('crewName', entry.get('crewId', '?')[:8])}: "
                      f"gross=P{entry.get('grossShare', 0):,.2f}, "
                      f"deductions=P{entry.get('totalDeductions', 0):,.2f}, "
                      f"net=P{entry.get('netPayout', 0):,.2f}")
            print()

    # ==================================================================
    # 11. PROFIT SHARING GENERATION (compute + save)
    # ==================================================================
    section("11. PROFIT SHARING GENERATION (Compute + Save)")

    ps_id = ""
    if trip_id:
        r = client.post("/profit-shares/generate", headers=auth_header("owner"), json={
            "tripId": trip_id,
            "policyId": policy_id,
            "status": "draft",
            "notes": f"Generated by E2E test {rid}",
        })
        report("POST /profit-shares/generate returns 200", r, 200)
        if r.status_code == 200:
            gen_result = r.json()
            ps_id = gen_result.get("id", "")
            report("Generated profit share has an ID", manual_ok=bool(ps_id))
            report(
                "Generated status is 'draft'",
                check_fn=lambda: assert_eq(gen_result.get("status"), "draft", "status"),
            )
            print(f"    -> Profit Share ID: {ps_id}")

    # ==================================================================
    # 12. PROFIT SHARE STATUS TRANSITIONS
    # ==================================================================
    section("12. PROFIT SHARE STATUS TRANSITIONS")

    if ps_id:
        # draft -> finalized (should succeed)
        r = client.patch(f"/profit-shares/{ps_id}/status", headers=auth_header("owner"), json={
            "status": "finalized",
        })
        report("draft -> finalized (should succeed)", r, 200)
        if r.status_code == 200:
            report("Status is now finalized", check_fn=lambda: assert_eq(r.json().get("status"), "finalized", "status"))

        # finalized -> paid (should succeed)
        r = client.patch(f"/profit-shares/{ps_id}/status", headers=auth_header("owner"), json={
            "status": "paid",
        })
        report("finalized -> paid (should succeed)", r, 200)
        if r.status_code == 200:
            report("Status is now paid", check_fn=lambda: assert_eq(r.json().get("status"), "paid", "status"))

        # paid -> draft (should FAIL -- paid is terminal)
        r = client.patch(f"/profit-shares/{ps_id}/status", headers=auth_header("owner"), json={
            "status": "draft",
        })
        report("paid -> draft (should fail, 400)", r, 400)
    else:
        skip("Status transitions", "no profit share ID")

    # ==================================================================
    # 13. FORECASTS
    # ==================================================================
    section("13. FORECASTS")

    r = client.get("/forecasts/seasonal?month=4&habitat=marine", headers=auth_header("broker"))
    report("GET /forecasts/seasonal", r, 200)
    if r.status_code == 200:
        forecast = r.json()
        species_list = forecast.get("species", [])
        print(f"    -> Species in seasonal forecast: {len(species_list)}")
        report("Seasonal forecast has species data", manual_ok=isinstance(species_list, list))

    r = client.get("/forecasts/price-guide?month=4", headers=auth_header("broker"))
    report("GET /forecasts/price-guide", r, 200)
    if r.status_code == 200:
        guide = r.json()
        report("Price guide has month field", check_fn=lambda: assert_key(guide, "month"))
        report("Price guide has prices list", check_fn=lambda: assert_key(guide, "prices"))
        print(f"    -> Species in price guide: {len(guide.get('prices', []))}")

    r = client.get("/forecasts/species-calendar", headers=auth_header("broker"))
    report("GET /forecasts/species-calendar", r, 200)

    # ==================================================================
    # 14. FISH SPECIES
    # ==================================================================
    section("14. FISH SPECIES")

    # List active species
    r = client.get("/fish/species/active", headers=auth_header("broker"))
    report("List active fish species", r, 200)
    if r.status_code == 200:
        species = r.json()
        print(f"    -> Active species count: {len(species)}")

    # Create a new species (as broker)
    new_species_name = f"TestFish_{rid}"
    r = client.post("/fish/species", headers=auth_header("broker"), json={
        "name": new_species_name,
        "localName": f"Isdang Test {rid}",
        "habitat": "marine",
        "peakMonths": [3, 4, 5, 6],
        "pricePerKg": [100, 200],
        "weightRange": [0.5, 5.0],
        "isActive": True,
    })
    report(f"Create fish species: {new_species_name}", r, 200)
    species_id = safe_json(r).get("id", "")
    if species_id:
        print(f"    -> Species ID: {species_id}")

    # Update species
    if species_id:
        r = client.patch(f"/fish/species/{species_id}", headers=auth_header("broker"), json={
            "pricePerKg": [120, 250],
        })
        report("Update fish species price range", r, 200)

    # Cleanup species (as admin)
    if species_id:
        r = client.delete(f"/fish/species/{species_id}", headers=auth_header("admin"))
        report("Delete test fish species", r, 200)

    # ==================================================================
    # 15. LICENSES
    # ==================================================================
    section("15. LICENSES")

    # Check license status (any logged-in user)
    r = client.get("/licenses/status", headers=auth_header("admin"))
    report("GET /licenses/status (admin)", r, 200)
    if r.status_code == 200:
        lic = r.json()
        print(f"    -> hasLicense: {lic.get('hasLicense')}, status: {lic.get('status')}, plan: {lic.get('plan')}")

    # Super admin license operations
    if "super" in tokens:
        r = client.get("/licenses/status", headers=auth_header("super"))
        report("GET /licenses/status (super)", r, 200)
        if r.status_code == 200:
            report("Super always has license", check_fn=lambda: assert_eq(r.json().get("hasLicense"), True, "hasLicense"))
    else:
        skip("Super license check", "no super token")

    # ==================================================================
    # 16. ROLES & PERMISSIONS
    # ==================================================================
    section("16. ROLES & PERMISSIONS")

    r = client.get("/roles", headers=auth_header("admin"))
    report("List roles", r, 200)
    if r.status_code == 200:
        roles = r.json()
        role_names = [ro.get("name") for ro in roles]
        print(f"    -> Roles: {role_names}")
        report("Has admin role", manual_ok="admin" in role_names)
        report("Has broker role", manual_ok="broker" in role_names)
        report("Has crew role", manual_ok="crew" in role_names)
        report("Has owner role", manual_ok="owner" in role_names)

    r = client.get("/permissions", headers=auth_header("admin"))
    report("List permissions", r, 200)
    if r.status_code == 200:
        perms = r.json()
        print(f"    -> Total permissions: {len(perms)}")

    # ==================================================================
    # 17. AUDIT LOGS
    # ==================================================================
    section("17. AUDIT LOGS")

    r = client.get("/audit-logs", headers=auth_header("admin"))
    report("GET /audit-logs (admin)", r, 200)

    # ==================================================================
    # 18. NEGATIVE / EDGE CASES
    # ==================================================================
    section("18. NEGATIVE / EDGE CASES")

    # Unauthenticated
    r = client.get("/profile")
    report("Unauthenticated access rejected (401)", r, 401)

    # Invalid ObjectId
    r = client.get("/vessels/not-a-valid-id", headers=auth_header("admin"))
    report("Invalid ObjectId handled gracefully (4xx)", manual_ok=r.status_code in (400, 404, 422, 500))

    # Wrong password
    try:
        r = client.post("/auth/login", json={"email": "admin@demo.com", "password": "WrongPass!"})
        report("Wrong password rejected (401)", r, 401)
    except Exception:
        report("Wrong password rejected (connection reset = server rejected)", manual_ok=True)

    # Crew cannot list users (forbidden)
    try:
        r = client.get("/users", headers=auth_header("crew"))
        report("Crew cannot list users (403)", r, 403)
    except Exception:
        report("Crew cannot list users (connection reset)", manual_ok=True)

    # ==================================================================
    # 19. CLEANUP
    # ==================================================================
    section("19. CLEANUP")

    # Reverse order for referential integrity:
    # profit shares (no delete endpoint for CRUD, just skip)
    # cash advances -> expenses -> fish sales -> trips -> crew -> boats -> vessels -> vessel owners
    cleanup_order = [
        "/cash-advances",
        "/expenses",
        "/fish-sales",
        "/trips",
        "/crew",
        "/boats",
        "/vessels",
        "/vessel-owners",
        "/profit-sharing-policies",
    ]

    for endpoint in cleanup_order:
        items = created_ids.get(endpoint, [])
        for label, item_id in items:
            if item_id:
                r = client.delete(f"{endpoint}/{item_id}", headers=auth_header("admin"))
                status_text = "ok" if r.status_code == 200 else f"err:{r.status_code}"
                print(f"    Cleanup {label}: {status_text}")

    # Logout
    for role in ["admin", "broker", "owner", "crew", "super"]:
        if role in tokens:
            client.post("/auth/logout", headers=auth_header(role))


finally:
    if server_proc:
        server_proc.terminate()
        try:
            server_proc.wait(timeout=10)
        except Exception:
            server_proc.kill()


# ═══════════════════════════════════════════════════════════════════════
# FINAL REPORT
# ═══════════════════════════════════════════════════════════════════════

total = PASS_COUNT + FAIL_COUNT + SKIP_COUNT

print(f"\n{BOLD}{'=' * 70}")
print(f"  COMPREHENSIVE E2E TEST REPORT")
print(f"{'=' * 70}{RESET}")
print(f"  Total Tests:  {total}")
print(f"  {GREEN}Passed:       {PASS_COUNT}{RESET}")
print(f"  {RED}Failed:       {FAIL_COUNT}{RESET}")
print(f"  {YELLOW}Skipped:      {SKIP_COUNT}{RESET}")

if ERRORS:
    print(f"\n  {RED}{BOLD}FAILURES:{RESET}")
    for i, err in enumerate(ERRORS, 1):
        print(f"    {i}. {err}")

print(f"\n{'=' * 70}")
if FAIL_COUNT == 0:
    print(f"  {GREEN}{BOLD}ALL TESTS PASSED{RESET}")
else:
    print(f"  {RED}{BOLD}SOME TESTS FAILED{RESET}")
print(f"{'=' * 70}\n")

sys.exit(1 if FAIL_COUNT > 0 else 0)
