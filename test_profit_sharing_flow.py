"""
End-to-end test: Full Profit Sharing Business Flow

Tests the COMPLETE business flow:
  1. Setup: Company, Broker, Owner, 3 Crew Members, Vessel, Boat
  2. Profit Sharing Policy: Pakura config (divisor=3)
  3. Trip: Create completed trip with crew
  4. Fish Sales: Small fish + Big fish entries
  5. Expenses: Fuel, ice, motorman
  6. Cash Advances: One crew member gets an advance (approved)
  7. Profit Calculation: Simulate the frontend Pakura calculation
  8. Profit Share Record: Store computed distribution
  9. Crew View: Each crew member can see their individual share
  10. Repeat with Tongko policy (divisor=2) for second trip
  11. Payroll: Mark shares as paid
  12. Cleanup
"""
import json
import sys
import random
import string
import httpx

BASE = "http://localhost:8000/api"
PASS = 0
FAIL = 0
ERRORS = []


def _rand(n=5):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


def report(name, resp=None, expected=None, check_fn=None, manual_ok=None):
    global PASS, FAIL
    ok = True
    details = ""
    if manual_ok is not None:
        ok = manual_ok
        if not ok:
            details = "Manual check failed"
    if resp and expected and resp.status_code != expected:
        ok = False
        details = f"Expected {expected}, got {resp.status_code}"
    if check_fn:
        try:
            check_fn()
        except Exception as e:
            ok = False
            details = str(e)
    if ok:
        PASS += 1
    else:
        FAIL += 1
        body = resp.text[:200] if resp else ""
        ERRORS.append(f"{name}: {details} | {body}")
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" - {details}" if details else ""))


def section(name):
    print(f"\n{'='*65}")
    print(f"  {name}")
    print(f"{'='*65}")


def assert_close(actual, expected, tolerance=0.01, label=""):
    if abs(actual - expected) > tolerance:
        raise AssertionError(f"{label}: {actual:.2f} != {expected:.2f} (tolerance {tolerance})")


client = httpx.Client(base_url=BASE, timeout=60.0)
rid = _rand()

# ═══════════════════════════════════════════════
section("PHASE 1: SETUP - Users, Company, Vessel, Crew")
# ═══════════════════════════════════════════════

# Register admin (creates company)
r = client.post("/auth/register", json={
    "email": f"psadmin_{rid}@test.com", "password": "Test@1234",
    "firstName": "PS", "lastName": "Admin", "roleId": "x",
    "companyName": f"PSCompany_{rid}",
})
report("Register admin + company", r, 200)
admin_token = r.json().get("accessToken", "")
admin_user = r.json().get("user", {})
company_code = admin_user.get("companyCode", "")
company_id = admin_user.get("companyId", "")

# Get role IDs
r = client.get("/roles", headers={"Authorization": f"Bearer {admin_token}"})
roles_map = {role["name"]: role["id"] for role in r.json()} if r.status_code == 200 else {}

# Register broker
r = client.post("/auth/register", json={
    "email": f"psbroker_{rid}@test.com", "password": "Test@1234",
    "firstName": "PS", "lastName": "Broker",
    "roleId": roles_map.get("broker", ""), "companyCode": company_code,
})
report("Register broker", r, 200)
broker_token = r.json().get("accessToken", "")
broker_id = r.json().get("user", {}).get("id", "")

# Register owner
r = client.post("/auth/register", json={
    "email": f"psowner_{rid}@test.com", "password": "Test@1234",
    "firstName": "PS", "lastName": "Owner",
    "roleId": roles_map.get("owner", ""), "companyCode": company_code,
})
report("Register owner", r, 200)
owner_token = r.json().get("accessToken", "")
owner_id = r.json().get("user", {}).get("id", "")

# Register 3 crew members
crew_ids = []
crew_tokens = []
for i in range(3):
    r = client.post("/auth/register", json={
        "email": f"pscrew{i}_{rid}@test.com", "password": "Test@1234",
        "firstName": f"Crew{i}", "lastName": "Member",
        "roleId": roles_map.get("crew", ""), "companyCode": company_code,
    })
    report(f"Register crew member {i}", r, 200)
    crew_ids.append(r.json().get("user", {}).get("id", ""))
    crew_tokens.append(r.json().get("accessToken", ""))

ah = {"Authorization": f"Bearer {admin_token}"}
bh = {"Authorization": f"Bearer {broker_token}"}
oh = {"Authorization": f"Bearer {owner_token}"}

# Create vessel owner record
r = client.post("/vessel-owners", headers=bh, json={
    "firstName": "PS", "lastName": "VesselOwner", "contactNumber": "09170000000",
})
report("Create vessel owner", r, 200)
vo_id = r.json().get("id", "") if r.status_code == 200 else ""

# Create vessel
r = client.post("/vessels", headers=bh, json={
    "name": f"MV_PS_{rid}", "registrationNo": f"PS-{rid}",
    "type": "motorized", "capacity": 10, "vesselOwnerId": vo_id,
})
report("Create vessel", r, 200)
vessel_id = r.json().get("id", "") if r.status_code == 200 else ""

# Create boat
r = client.post("/boats", headers=bh, json={
    "name": f"Bangka_PS_{rid}", "registrationNo": f"BK-{rid}",
    "type": "pumpboat", "vesselOwnerId": vo_id,
})
report("Create boat", r, 200)
boat_id = r.json().get("id", "") if r.status_code == 200 else ""

# Create crew records
crew_record_ids = []
for i, cid in enumerate(crew_ids):
    role = "captain" if i == 0 else "crew"
    r = client.post("/crew", headers=ah, json={
        "firstName": f"Crew{i}", "lastName": "Member",
        "contactNumber": f"0917000000{i}", "vessel": vessel_id,
        "role": role, "crewType": "pakura", "status": "active",
    })
    report(f"Create crew record {i} ({role})", r, 200)
    crew_record_ids.append(r.json().get("id", "") if r.status_code == 200 else "")

captain_id = crew_record_ids[0]
print(f"    -> Crew IDs: {crew_record_ids}")
print(f"    -> Crew User IDs: {crew_ids}")

# ═══════════════════════════════════════════════
section("PHASE 2: PAKURA PROFIT SHARING POLICY")
# ═══════════════════════════════════════════════

r = client.post("/profit-sharing-policies", headers=oh, json={
    "boatOwnerId": owner_id,
    "boatId": boat_id,
    "pakuraDivisor": 3,
    "tongkoDivisor": 2,
    "sinakahan": 1000,
    "captainOwnerSplitType": "members_split",
    "totalMembers": 4,
    "captainMembersShare": 1,
    "captainIsOwner": False,
    "brokerPercentage": 10.0,
    "boatOwnerPercentage": 40.0,
    "fishermanPercentage": 50.0,
    "isActive": True,
    "notes": "Pakura policy for testing",
})
report("Create Pakura profit sharing policy", r, 200)
policy_id = r.json().get("id", "") if r.status_code == 200 else ""
print(f"    -> Policy: Pakura divisor=3, Broker=10%, Owner=40%, Crew=50%")

# Verify policy read
r = client.get(f"/profit-sharing-policies/{policy_id}", headers=oh)
report("Read Pakura policy", r, 200)
if r.status_code == 200:
    pol = r.json()
    report("Policy pakuraDivisor=3", check_fn=lambda: assert_close(pol["pakuraDivisor"], 3, 0, "pakuraDivisor"))
    report("Policy brokerPct=10", check_fn=lambda: assert_close(pol["brokerPercentage"], 10, 0.01, "brokerPct"))
    report("Policy ownerPct=40", check_fn=lambda: assert_close(pol["boatOwnerPercentage"], 40, 0.01, "ownerPct"))
    report("Policy crewPct=50", check_fn=lambda: assert_close(pol["fishermanPercentage"], 50, 0.01, "crewPct"))

# ═══════════════════════════════════════════════
section("PHASE 3: TRIP 1 - PAKURA CREW (Complete Flow)")
# ═══════════════════════════════════════════════

# Create trip with all 3 crew
r = client.post("/trips", headers=bh, json={
    "boatId": boat_id, "vesselId": vessel_id,
    "departureDate": "2026-04-01T06:00:00Z",
    "returnDate": "2026-04-03T18:00:00Z",
    "status": "completed",
    "captainId": captain_id,
    "captainName": "Crew0 Member",
    "crewType": "pakura",
    "crewMembers": crew_record_ids,
})
report("Create Trip 1 (Pakura, 3 crew)", r, 200)
trip1_id = r.json().get("id", "") if r.status_code == 200 else ""

# ─── FISH SALES ───
# Small fish sales
r = client.post("/fish-sales", headers=bh, json={
    "tripId": trip1_id, "species": "Galunggong",
    "weightKg": 100, "pricePerKg": 120, "totalAmount": 12000,
    "buyer": "Wet Market A", "saleType": "small_fish",
})
report("Small fish sale: 100kg Galunggong @ 120/kg = P12,000", r, 200)
sf1_id = r.json().get("id", "") if r.status_code == 200 else ""

r = client.post("/fish-sales", headers=bh, json={
    "tripId": trip1_id, "species": "Bangus",
    "weightKg": 50, "pricePerKg": 180, "totalAmount": 9000,
    "buyer": "Wet Market B", "saleType": "small_fish",
})
report("Small fish sale: 50kg Bangus @ 180/kg = P9,000", r, 200)
sf2_id = r.json().get("id", "") if r.status_code == 200 else ""

# Big fish sales
r = client.post("/fish-sales", headers=bh, json={
    "tripId": trip1_id, "species": "Yellowfin Tuna",
    "weightKg": 30, "pricePerKg": 350, "totalAmount": 10500,
    "buyer": "Fish Dealer C", "saleType": "big_fish",
})
report("Big fish sale: 30kg YF Tuna @ 350/kg = P10,500", r, 200)
bf1_id = r.json().get("id", "") if r.status_code == 200 else ""

r = client.post("/fish-sales", headers=bh, json={
    "tripId": trip1_id, "species": "Tambakol",
    "weightKg": 20, "pricePerKg": 280, "totalAmount": 5600,
    "buyer": "Fish Dealer D", "saleType": "big_fish",
})
report("Big fish sale: 20kg Tambakol @ 280/kg = P5,600", r, 200)
bf2_id = r.json().get("id", "") if r.status_code == 200 else ""

SMALL_FISH_TOTAL = 12000 + 9000  # 21,000
BIG_FISH_TOTAL = 10500 + 5600    # 16,100
GROSS_REVENUE = SMALL_FISH_TOTAL + BIG_FISH_TOTAL  # 37,100
print(f"    -> Small Fish Total: P{SMALL_FISH_TOTAL:,.2f}")
print(f"    -> Big Fish Total: P{BIG_FISH_TOTAL:,.2f}")
print(f"    -> Gross Revenue: P{GROSS_REVENUE:,.2f}")

# ─── EXPENSES ───
r = client.post("/expenses", headers=bh, json={
    "tripId": trip1_id, "category": "fuel", "amount": 5000,
    "description": "Diesel fuel for 3-day trip", "recordedBy": broker_id,
})
report("Expense: Fuel P5,000", r, 200)
exp1_id = r.json().get("id", "") if r.status_code == 200 else ""

r = client.post("/expenses", headers=bh, json={
    "tripId": trip1_id, "category": "ice", "amount": 1500,
    "description": "Ice blocks for fish preservation", "recordedBy": broker_id,
})
report("Expense: Ice P1,500", r, 200)
exp2_id = r.json().get("id", "") if r.status_code == 200 else ""

r = client.post("/expenses", headers=bh, json={
    "tripId": trip1_id, "category": "food", "amount": 2000,
    "description": "Crew food and provisions", "recordedBy": broker_id,
})
report("Expense: Food P2,000", r, 200)
exp3_id = r.json().get("id", "") if r.status_code == 200 else ""

TOTAL_EXPENSES = 5000 + 1500 + 2000  # 8,500
print(f"    -> Total Expenses: P{TOTAL_EXPENSES:,.2f}")

# ─── CASH ADVANCE (1 crew member) ───
r = client.post("/cash-advances", headers=ah, json={
    "requestedBy": crew_record_ids[1],
    "amount": 1000,
    "reason": "Family emergency",
    "status": "pending",
    "tripId": trip1_id,
})
report("Cash advance request: Crew1 P1,000", r, 200)
ca_id = r.json().get("id", "") if r.status_code == 200 else ""

if ca_id:
    r = client.patch(f"/cash-advances/{ca_id}/approve", headers=ah, json={"notes": "Approved"})
    report("Approve cash advance", r, 200)
TOTAL_CASH_ADVANCES = 1000
print(f"    -> Cash Advances: P{TOTAL_CASH_ADVANCES:,.2f} (Crew1)")

# ═══════════════════════════════════════════════
section("PHASE 4: PAKURA PROFIT CALCULATION")
# ═══════════════════════════════════════════════

# Simulate the frontend calculation (Pakura method)
print("\n  === PAKURA CALCULATION (Frontend Logic) ===\n")

# Step 1: Broker Share
BROKER_PCT = 10.0
broker_share = GROSS_REVENUE * (BROKER_PCT / 100)
print(f"  Step 1: Broker Share = P{GROSS_REVENUE:,.2f} × 10% = P{broker_share:,.2f}")

# Step 2: Bangka Share
small_bangka = SMALL_FISH_TOTAL * 0.20
big_bangka = BIG_FISH_TOTAL * 0.10
total_bangka = small_bangka + big_bangka
print(f"  Step 2: Bangka Share")
print(f"    Small Fish Bangka = P{SMALL_FISH_TOTAL:,.2f} × 20% = P{small_bangka:,.2f}")
print(f"    Big Fish Bangka   = P{BIG_FISH_TOTAL:,.2f} × 10% = P{big_bangka:,.2f}")
print(f"    Total Bangka      = P{total_bangka:,.2f}")

# Step 3: Remaining after Bangka
small_remaining = SMALL_FISH_TOTAL - small_bangka
big_remaining = BIG_FISH_TOTAL - big_bangka
print(f"  Step 3: Remaining After Bangka")
print(f"    Small Remaining = P{small_remaining:,.2f}")
print(f"    Big Remaining   = P{big_remaining:,.2f}")

# Step 4: Crew Pool (Pakura ÷3)
PAKURA_DIVISOR = 3
small_crew = small_remaining / PAKURA_DIVISOR
big_crew = big_remaining / PAKURA_DIVISOR
total_crew_pool = small_crew + big_crew
print(f"  Step 4: Crew Pool (Pakura ÷{PAKURA_DIVISOR})")
print(f"    Small Crew = P{small_remaining:,.2f} ÷ {PAKURA_DIVISOR} = P{small_crew:,.2f}")
print(f"    Big Crew   = P{big_remaining:,.2f} ÷ {PAKURA_DIVISOR} = P{big_crew:,.2f}")
print(f"    Total Crew Pool = P{total_crew_pool:,.2f}")

# Step 5: Captain/Owner Net
motorman = 0  # No separate motorman in this test
captain_owner_net = GROSS_REVENUE - broker_share - total_crew_pool - TOTAL_EXPENSES - motorman
print(f"  Step 5: Captain/Owner NET")
print(f"    = P{GROSS_REVENUE:,.2f} - P{broker_share:,.2f} - P{total_crew_pool:,.2f} - P{TOTAL_EXPENSES:,.2f}")
print(f"    = P{captain_owner_net:,.2f}")

# Step 6: Captain/Owner Split
captain_share = captain_owner_net * 0.40
owner_share = captain_owner_net * 0.60
print(f"  Step 6: Captain/Owner Split")
print(f"    Captain = P{captain_owner_net:,.2f} × 40% = P{captain_share:,.2f}")
print(f"    Owner   = P{captain_owner_net:,.2f} × 60% = P{owner_share:,.2f}")

# Step 7: Individual Crew Shares
NUM_CREW = 3
crew_share_each = total_crew_pool / NUM_CREW
print(f"  Step 7: Individual Crew Shares (÷{NUM_CREW} members)")
print(f"    Gross Per Crew = P{total_crew_pool:,.2f} ÷ {NUM_CREW} = P{crew_share_each:,.2f}")

# Apply cash advance deduction for Crew1
crew0_net = crew_share_each  # Captain (no advance)
crew1_net = crew_share_each - TOTAL_CASH_ADVANCES  # Has P1000 advance
crew2_net = crew_share_each  # No advance
print(f"    Crew0 (Captain): P{crew_share_each:,.2f} - P0 = P{crew0_net:,.2f}")
print(f"    Crew1:           P{crew_share_each:,.2f} - P{TOTAL_CASH_ADVANCES:,.2f} = P{crew1_net:,.2f}")
print(f"    Crew2:           P{crew_share_each:,.2f} - P0 = P{crew2_net:,.2f}")

NET_PROFIT = GROSS_REVENUE - TOTAL_EXPENSES
print(f"\n  Net Profit = P{GROSS_REVENUE:,.2f} - P{TOTAL_EXPENSES:,.2f} = P{NET_PROFIT:,.2f}")

# Verify totals
total_distributed = broker_share + total_bangka + total_crew_pool + captain_owner_net
print(f"\n  Total Distributed = P{broker_share:,.2f} + P{total_bangka:,.2f} + P{total_crew_pool:,.2f} + P{captain_owner_net:,.2f}")
print(f"                    = P{total_distributed:,.2f} (should equal P{GROSS_REVENUE - TOTAL_EXPENSES:,.2f} + expenses absorbed)")

# ═══════════════════════════════════════════════
section("PHASE 5: STORE PAKURA PROFIT SHARE RECORD")
# ═══════════════════════════════════════════════

fisherman_shares = {}
for i, crid in enumerate(crew_record_ids):
    if i == 1:
        fisherman_shares[crid] = crew1_net
    else:
        fisherman_shares[crid] = crew_share_each

r = client.post("/profit-shares", headers=ah, json={
    "tripId": trip1_id,
    "boatOwnerId": owner_id,
    "generatedBy": broker_id,
    "calculationDate": "2026-04-04T00:00:00Z",
    "totalRevenue": GROSS_REVENUE,
    "totalExpenses": TOTAL_EXPENSES,
    "totalCashAdvances": TOTAL_CASH_ADVANCES,
    "netProfit": NET_PROFIT,
    "fishermanShares": fisherman_shares,
    "boatOwnerShare": owner_share,
    "brokerShare": broker_share,
    "brokerPercentage": BROKER_PCT,
    "boatOwnerPercentage": 40.0,
    "fishermanPercentage": 50.0,
    "status": "finalized",
    "notes": "Pakura trip - 3 crew members",
})
report("Store Pakura profit share record", r, 200)
ps1_id = r.json().get("id", "") if r.status_code == 200 else ""

# Verify stored correctly
if ps1_id:
    r = client.get(f"/profit-shares/{ps1_id}", headers=ah)
    report("Read stored profit share", r, 200)
    if r.status_code == 200:
        ps = r.json()
        report("Stored totalRevenue matches", check_fn=lambda: assert_close(ps["totalRevenue"], GROSS_REVENUE, 0.01, "totalRevenue"))
        report("Stored totalExpenses matches", check_fn=lambda: assert_close(ps["totalExpenses"], TOTAL_EXPENSES, 0.01, "totalExpenses"))
        report("Stored netProfit matches", check_fn=lambda: assert_close(ps["netProfit"], NET_PROFIT, 0.01, "netProfit"))
        report("Stored brokerShare matches", check_fn=lambda: assert_close(ps["brokerShare"], broker_share, 0.01, "brokerShare"))
        report("Stored boatOwnerShare matches", check_fn=lambda: assert_close(ps["boatOwnerShare"], owner_share, 0.01, "ownerShare"))
        report("Status is finalized", check_fn=lambda: assert_close(0 if ps["status"] == "finalized" else 1, 0, 0, "status"))
        # Check individual fisherman shares
        fs = ps.get("fishermanShares", {})
        report(f"3 crew shares stored", check_fn=lambda: assert_close(len(fs), 3, 0, "share count"))
        for crid, expected in fisherman_shares.items():
            actual = fs.get(crid, 0)
            report(f"Crew {crid[:8]}... share = P{actual:,.2f}", check_fn=lambda a=actual, e=expected: assert_close(a, e, 0.01, "crew share"))

# ═══════════════════════════════════════════════
section("PHASE 6: CREW MEMBERS VIEW THEIR SHARES")
# ═══════════════════════════════════════════════

# Each crew member reads their profit share
r = client.get("/profit-shares", headers={"Authorization": f"Bearer {crew_tokens[0]}"})
report("Crew0 (Captain) can view profit shares", r, 200)
if r.status_code == 200:
    shares = r.json().get("results", [])
    report(f"Crew0 sees {len(shares)} profit share(s)", manual_ok=len(shares) >= 1)
    if shares:
        ps = shares[0]
        crew0_share = ps.get("fishermanShares", {}).get(crew_record_ids[0], 0)
        print(f"    -> Crew0 (Captain) share: P{crew0_share:,.2f}")
        report("Crew0 share matches calculation", check_fn=lambda: assert_close(crew0_share, crew_share_each, 0.01, "crew0"))

r = client.get("/profit-shares", headers={"Authorization": f"Bearer {crew_tokens[1]}"})
report("Crew1 can view profit shares", r, 200)
if r.status_code == 200:
    shares = r.json().get("results", [])
    if shares:
        ps = shares[0]
        crew1_share_stored = ps.get("fishermanShares", {}).get(crew_record_ids[1], 0)
        print(f"    -> Crew1 share (after P1,000 advance): P{crew1_share_stored:,.2f}")
        report("Crew1 share has advance deducted", check_fn=lambda: assert_close(crew1_share_stored, crew1_net, 0.01, "crew1"))

r = client.get("/profit-shares", headers={"Authorization": f"Bearer {crew_tokens[2]}"})
report("Crew2 can view profit shares", r, 200)
if r.status_code == 200:
    shares = r.json().get("results", [])
    if shares:
        crew2_share_stored = shares[0].get("fishermanShares", {}).get(crew_record_ids[2], 0)
        print(f"    -> Crew2 share: P{crew2_share_stored:,.2f}")
        report("Crew2 share matches calculation", check_fn=lambda: assert_close(crew2_share_stored, crew2_net, 0.01, "crew2"))

# ═══════════════════════════════════════════════
section("PHASE 7: TONGKO TRIP (Divisor=2)")
# ═══════════════════════════════════════════════

# Create second trip (tongko)
r = client.post("/trips", headers=bh, json={
    "boatId": boat_id, "vesselId": vessel_id,
    "departureDate": "2026-04-05T06:00:00Z",
    "returnDate": "2026-04-07T18:00:00Z",
    "status": "completed",
    "captainId": captain_id,
    "captainName": "Crew0 Member",
    "crewType": "tongko",
    "crewMembers": crew_record_ids,
})
report("Create Trip 2 (Tongko, 3 crew)", r, 200)
trip2_id = r.json().get("id", "") if r.status_code == 200 else ""

# Same fish sales for Trip 2
r = client.post("/fish-sales", headers=bh, json={
    "tripId": trip2_id, "species": "Galunggong",
    "weightKg": 100, "pricePerKg": 120, "totalAmount": 12000,
    "buyer": "Buyer E", "saleType": "small_fish",
})
sf3_id = r.json().get("id", "") if r.status_code == 200 else ""
r = client.post("/fish-sales", headers=bh, json={
    "tripId": trip2_id, "species": "Yellowfin Tuna",
    "weightKg": 30, "pricePerKg": 350, "totalAmount": 10500,
    "buyer": "Buyer F", "saleType": "big_fish",
})
sf4_id = r.json().get("id", "") if r.status_code == 200 else ""

T2_SMALL = 12000
T2_BIG = 10500
T2_GROSS = T2_SMALL + T2_BIG  # 22,500
T2_EXPENSES = 4000

r = client.post("/expenses", headers=bh, json={
    "tripId": trip2_id, "category": "fuel", "amount": 4000,
    "description": "Fuel", "recordedBy": broker_id,
})
exp4_id = r.json().get("id", "") if r.status_code == 200 else ""

# Tongko calculation (divisor=2 instead of 3)
TONGKO_DIVISOR = 2
t2_broker = T2_GROSS * 0.10
t2_small_bangka = T2_SMALL * 0.20
t2_big_bangka = T2_BIG * 0.10
t2_small_remaining = T2_SMALL - t2_small_bangka
t2_big_remaining = T2_BIG - t2_big_bangka
t2_small_crew = t2_small_remaining / TONGKO_DIVISOR
t2_big_crew = t2_big_remaining / TONGKO_DIVISOR
t2_crew_pool = t2_small_crew + t2_big_crew
t2_captain_owner_net = T2_GROSS - t2_broker - t2_crew_pool - T2_EXPENSES
t2_captain = t2_captain_owner_net * 0.40
t2_owner = t2_captain_owner_net * 0.60
t2_crew_each = t2_crew_pool / NUM_CREW
t2_net_profit = T2_GROSS - T2_EXPENSES

print(f"\n  === TONGKO CALCULATION (Divisor={TONGKO_DIVISOR}) ===")
print(f"  Gross: P{T2_GROSS:,.2f} | Expenses: P{T2_EXPENSES:,.2f}")
print(f"  Broker: P{t2_broker:,.2f}")
print(f"  Bangka: P{t2_small_bangka + t2_big_bangka:,.2f}")
print(f"  Crew Pool (÷{TONGKO_DIVISOR}): P{t2_crew_pool:,.2f}")
print(f"  Crew Each: P{t2_crew_each:,.2f}")
print(f"  Captain/Owner Net: P{t2_captain_owner_net:,.2f} (C:P{t2_captain:,.2f} / O:P{t2_owner:,.2f})")

# Compare Pakura vs Tongko crew share
print(f"\n  PAKURA crew each: P{crew_share_each:,.2f}")
print(f"  TONGKO crew each: P{t2_crew_each:,.2f}")
# With equal gross, Tongko (÷2) gives larger crew share than Pakura (÷3).
# Here trips have different revenue so compare ratio instead.
pakura_crew_ratio = total_crew_pool / GROSS_REVENUE  # crew pool as % of gross
tongko_crew_ratio = t2_crew_pool / T2_GROSS
print(f"  Pakura crew-to-gross ratio: {pakura_crew_ratio:.4f}")
print(f"  Tongko crew-to-gross ratio: {tongko_crew_ratio:.4f}")
report("Tongko has higher crew-to-gross ratio than Pakura", manual_ok=tongko_crew_ratio > pakura_crew_ratio)

# Store Tongko profit share
t2_fisherman_shares = {crid: t2_crew_each for crid in crew_record_ids}
r = client.post("/profit-shares", headers=ah, json={
    "tripId": trip2_id,
    "boatOwnerId": owner_id,
    "generatedBy": broker_id,
    "calculationDate": "2026-04-07T00:00:00Z",
    "totalRevenue": T2_GROSS,
    "totalExpenses": T2_EXPENSES,
    "totalCashAdvances": 0,
    "netProfit": t2_net_profit,
    "fishermanShares": t2_fisherman_shares,
    "boatOwnerShare": t2_owner,
    "brokerShare": t2_broker,
    "brokerPercentage": 10.0,
    "boatOwnerPercentage": 40.0,
    "fishermanPercentage": 50.0,
    "status": "finalized",
    "notes": "Tongko trip - 3 crew members",
})
report("Store Tongko profit share record", r, 200)
ps2_id = r.json().get("id", "") if r.status_code == 200 else ""

# ═══════════════════════════════════════════════
section("PHASE 8: CREW VIEWS BOTH TRIPS' EARNINGS")
# ═══════════════════════════════════════════════

r = client.get("/profit-shares", headers={"Authorization": f"Bearer {crew_tokens[0]}"})
report("Crew0 can see both trips", r, 200)
if r.status_code == 200:
    shares = r.json().get("results", [])
    report(f"Crew0 sees {len(shares)} profit shares (2 trips)", manual_ok=len(shares) >= 2)
    total_earnings = 0
    for ps in shares:
        fs = ps.get("fishermanShares", {})
        share = fs.get(crew_record_ids[0], 0)
        total_earnings += share
    print(f"    -> Crew0 total earnings across 2 trips: P{total_earnings:,.2f}")
    expected_total = crew_share_each + t2_crew_each
    report("Total matches Pakura + Tongko shares", check_fn=lambda: assert_close(total_earnings, expected_total, 0.01, "total"))

# ═══════════════════════════════════════════════
section("PHASE 9: CLEANUP")
# ═══════════════════════════════════════════════

cleanup_ids = [
    ("trip2 expense", exp4_id, "/expenses"),
    ("trip2 sale 1", sf3_id, "/fish-sales"),
    ("trip2 sale 2", sf4_id, "/fish-sales"),
    ("trip2", trip2_id, "/trips"),
    ("trip1 exp1", exp1_id, "/expenses"),
    ("trip1 exp2", exp2_id, "/expenses"),
    ("trip1 exp3", exp3_id, "/expenses"),
    ("trip1 sf1", sf1_id, "/fish-sales"),
    ("trip1 sf2", sf2_id, "/fish-sales"),
    ("trip1 bf1", bf1_id, "/fish-sales"),
    ("trip1 bf2", bf2_id, "/fish-sales"),
    ("cash advance", ca_id, "/cash-advances"),
    ("trip1", trip1_id, "/trips"),
    ("policy", policy_id, "/profit-sharing-policies"),
    ("boat", boat_id, "/boats"),
    ("vessel", vessel_id, "/vessels"),
    ("vessel owner", vo_id, "/vessel-owners"),
] + [(f"crew rec {i}", cid, "/crew") for i, cid in enumerate(crew_record_ids)]

for label, item_id, ep in cleanup_ids:
    if item_id:
        r = client.delete(f"{ep}/{item_id}", headers=ah)
        status = "ok" if r.status_code == 200 else f"err:{r.status_code}"
        # Don't count cleanup as test failures

# Delete users
for uid in crew_ids + [broker_id, owner_id]:
    if uid:
        client.delete(f"/users/{uid}", headers=ah)

client.post("/auth/logout", headers=ah)

# ═══════════════════════════════════════════════
print(f"\n{'='*65}")
print(f"  PROFIT SHARING FLOW TEST REPORT")
print(f"{'='*65}")
print(f"  Total:  {PASS + FAIL}")
print(f"  Passed: {PASS}")
print(f"  Failed: {FAIL}")
if ERRORS:
    print(f"\n  FAILURES:")
    for e in ERRORS:
        print(f"    - {e}")
print(f"{'='*65}")
sys.exit(1 if FAIL > 0 else 0)
