"""
Comprehensive demo data seeder for the Profit Sharing system.
Seeds realistic data for all collections: users, vessels, crew, trips,
catches, expenses, fish sales, cash advances, profit shares, and policies.

Usage:
    python -m app.seeders.seed_demo_data
"""
import asyncio
from datetime import datetime, timezone, timedelta
from bson import ObjectId

from app.db import connect_db, disconnect_db, get_db
from app.core.security import hash_password
from app.seeders.roles_permissions import (
    seed_broker_role_with_permissions,
    seed_boat_owner_role_with_permissions,
    seed_fisherman_role_with_permissions,
    seed_admin_role_with_all_permissions,
)


async def seed_demo_data():
    await connect_db()
    db = get_db()
    now = datetime.now(timezone.utc)

    print("Seeding roles and permissions...")
    await seed_broker_role_with_permissions()
    await seed_boat_owner_role_with_permissions()
    await seed_fisherman_role_with_permissions()
    await seed_admin_role_with_all_permissions()

    # ─── Lookup role IDs ───
    roles = {}
    async for r in db["roles"].find():
        roles[r["name"]] = r["_id"]

    # ─── Company ───
    print("Seeding company...")
    company = await db["companies"].find_one({"companyName": "Demo Fishing Co"})
    if not company:
        result = await db["companies"].insert_one({
            "companyName": "Demo Fishing Co",
            "companyCode": "DFC001",
            "companyAddress": "Brgy. San Isidro, Lapu-Lapu City, Cebu",
            "companyPhone": "+63 917 123 4567",
            "companyTaxId": "123-456-789-000",
            "createdAt": now,
            "updatedAt": now,
        })
        company_id = result.inserted_id
    else:
        company_id = company["_id"]

    # ─── Users ───
    print("Seeding users...")
    users_data = [
        {"email": "admin@demo.com", "firstName": "Admin", "lastName": "User",
         "role": "admin"},
        {"email": "broker@demo.com", "firstName": "Maria", "lastName": "Cruz",
         "role": "broker"},
        {"email": "owner@demo.com", "firstName": "Juan", "lastName": "Santos",
         "role": "owner"},
        {"email": "captain@demo.com", "firstName": "Jose", "lastName": "Reyes",
         "role": "crew"},
        {"email": "pedro@demo.com", "firstName": "Pedro", "lastName": "Martinez",
         "role": "crew"},
        {"email": "miguel@demo.com", "firstName": "Miguel", "lastName": "Lopez",
         "role": "crew"},
        {"email": "ramon@demo.com", "firstName": "Ramon", "lastName": "Garcia",
         "role": "crew"},
        {"email": "carlos@demo.com", "firstName": "Carlos", "lastName": "Aquino",
         "role": "crew"},
    ]
    user_ids = {}
    for u in users_data:
        existing = await db["users"].find_one({"email": u["email"]})
        if existing:
            user_ids[u["email"]] = existing["_id"]
            continue
        result = await db["users"].insert_one({
            "email": u["email"],
            "password": hash_password("Demo1234!"),
            "firstName": u["firstName"],
            "lastName": u["lastName"],
            "role": roles.get(u["role"]),
            "companyId": company_id,
            "companyApproved": True,
            "isActive": True,
            "createdAt": now,
            "updatedAt": now,
        })
        user_ids[u["email"]] = result.inserted_id
    print(f"  {len(user_ids)} users ready")

    # ─── Vessel Owners ───
    print("Seeding vessel owners...")
    vo = await db["vessel-owners"].find_one({"firstName": "Juan", "lastName": "Santos"})
    if not vo:
        r = await db["vessel-owners"].insert_one({
            "firstName": "Juan", "lastName": "Santos",
            "contactNumber": "+63 917 234 5678",
            "companyId": company_id,
            "createdAt": now, "updatedAt": now,
        })
        vo_id = r.inserted_id
    else:
        vo_id = vo["_id"]

    # ─── Vessels ───
    print("Seeding vessels...")
    vessels_data = [
        {"name": "FB Maria Josefa", "registrationNumber": "FB-2024-001",
         "type": "Fishing Trawler", "capacity": 8, "status": "active"},
        {"name": "FB San Miguel", "registrationNumber": "FB-2024-002",
         "type": "Purse Seiner", "capacity": 12, "status": "active"},
    ]
    vessel_ids = {}
    for v in vessels_data:
        existing = await db["vessels"].find_one({"name": v["name"]})
        if existing:
            vessel_ids[v["name"]] = existing["_id"]
            continue
        r = await db["vessels"].insert_one({
            **v,
            "vesselOwnerId": str(vo_id),
            "companyId": company_id,
            "createdAt": now, "updatedAt": now,
        })
        vessel_ids[v["name"]] = r.inserted_id
    print(f"  {len(vessel_ids)} vessels ready")

    # ─── Boats ───
    print("Seeding boats...")
    boat = await db["boats"].find_one({"name": "Bangka 1"})
    if not boat:
        r = await db["boats"].insert_one({
            "name": "Bangka 1", "type": "Outrigger", "capacity": 6,
            "companyId": company_id,
            "createdAt": now, "updatedAt": now,
        })
        boat_id = r.inserted_id
    else:
        boat_id = boat["_id"]

    # ─── Crew Members ───
    print("Seeding crew members...")
    crew_data = [
        {"firstName": "Jose", "lastName": "Reyes", "role": "captain",
         "contactNumber": "+63 917 345 6789", "vessel": "FB Maria Josefa",
         "crewType": "pakura", "notes": "Experienced captain with 15 years in fishing"},
        {"firstName": "Pedro", "lastName": "Martinez", "role": "crew",
         "contactNumber": "+63 917 456 7890", "vessel": "FB Maria Josefa",
         "crewType": "pakura", "notes": "Reliable crew member, good with nets"},
        {"firstName": "Miguel", "lastName": "Lopez", "role": "crew",
         "contactNumber": "+63 917 567 8901", "vessel": "FB Maria Josefa",
         "crewType": "pakura", "notes": "Strong worker, experienced in deep sea fishing"},
        {"firstName": "Ramon", "lastName": "Garcia", "role": "crew",
         "contactNumber": "+63 917 678 9012", "vessel": "FB Maria Josefa",
         "crewType": "pakura", "notes": ""},
        {"firstName": "Carlos", "lastName": "Aquino", "role": "crew",
         "contactNumber": "+63 917 789 0123", "vessel": "FB Maria Josefa",
         "crewType": "pakura", "notes": ""},
    ]
    crew_ids = {}
    for c in crew_data:
        existing = await db["crew"].find_one({
            "firstName": c["firstName"], "lastName": c["lastName"]
        })
        if existing:
            crew_ids[f"{c['firstName']} {c['lastName']}"] = existing["_id"]
            continue
        r = await db["crew"].insert_one({
            **c, "status": "active",
            "companyId": company_id,
            "joinedDate": (now - timedelta(days=90)).isoformat(),
            "createdAt": now, "updatedAt": now,
        })
        crew_ids[f"{c['firstName']} {c['lastName']}"] = r.inserted_id
    print(f"  {len(crew_ids)} crew members ready")

    captain_id = str(crew_ids.get("Jose Reyes", ""))
    crew_member_ids = [
        str(crew_ids.get("Pedro Martinez", "")),
        str(crew_ids.get("Miguel Lopez", "")),
        str(crew_ids.get("Ramon Garcia", "")),
        str(crew_ids.get("Carlos Aquino", "")),
    ]

    # ─── Trips ───
    print("Seeding trips...")
    trips_data = [
        {"departureDate": (now - timedelta(days=14)).isoformat(),
         "returnDate": (now - timedelta(days=11)).isoformat(),
         "status": "completed", "destination": "Visayan Sea",
         "vesselName": "FB Maria Josefa", "crewType": "pakura",
         "captainName": "Jose Reyes"},
        {"departureDate": (now - timedelta(days=7)).isoformat(),
         "returnDate": (now - timedelta(days=4)).isoformat(),
         "status": "completed", "destination": "Camotes Sea",
         "vesselName": "FB Maria Josefa", "crewType": "pakura",
         "captainName": "Jose Reyes"},
    ]
    trip_ids = []
    for i, t in enumerate(trips_data):
        existing = await db["trips"].find_one({
            "departureDate": t["departureDate"], "vesselName": t["vesselName"],
            "companyId": company_id,
        })
        if existing:
            trip_ids.append(existing["_id"])
            continue
        r = await db["trips"].insert_one({
            **t,
            "brokerId": str(user_ids.get("broker@demo.com", "")),
            "vesselId": str(vessel_ids.get("FB Maria Josefa", "")),
            "boatId": str(boat_id),
            "captainId": captain_id,
            "crewMembers": crew_member_ids,
            "companyId": company_id,
            "createdAt": now, "updatedAt": now,
        })
        trip_ids.append(r.inserted_id)
    print(f"  {len(trip_ids)} trips ready")

    # ─── Fish Sales ───
    print("Seeding fish sales...")
    sales_data = [
        # Trip 1
        {"tripId": str(trip_ids[0]), "species": "Tuna", "weightKg": 45,
         "pricePerKg": 350, "totalAmount": 15750, "buyer": "Market Vendor A"},
        {"tripId": str(trip_ids[0]), "species": "Bangus", "weightKg": 387,
         "pricePerKg": 94.65, "totalAmount": 36618, "buyer": "Market Vendor B"},
        # Trip 2
        {"tripId": str(trip_ids[1]), "species": "Galunggong", "weightKg": 200,
         "pricePerKg": 120, "totalAmount": 24000, "buyer": "Market Vendor A"},
        {"tripId": str(trip_ids[1]), "species": "Lapu-Lapu", "weightKg": 35,
         "pricePerKg": 450, "totalAmount": 15750, "buyer": "Market Vendor C"},
    ]
    for s in sales_data:
        existing = await db["fish-sales"].find_one({
            "tripId": s["tripId"], "species": s["species"], "companyId": company_id,
        })
        if existing:
            continue
        await db["fish-sales"].insert_one({
            **s, "companyId": company_id,
            "createdAt": now, "updatedAt": now,
        })
    print(f"  {len(sales_data)} fish sales ready")

    # ─── Expenses ───
    print("Seeding expenses...")
    expenses_data = [
        {"tripId": str(trip_ids[0]), "category": "Starting (Operational)",
         "amount": 6000, "description": "Fuel, ice, and bait"},
        {"tripId": str(trip_ids[0]), "category": "Grocery",
         "amount": 3500, "description": "Food and supplies"},
        {"tripId": str(trip_ids[0]), "category": "Motorman Payment",
         "amount": 2500, "description": "Motorman payment"},
        {"tripId": str(trip_ids[1]), "category": "Fuel",
         "amount": 5000, "description": "Diesel fuel"},
        {"tripId": str(trip_ids[1]), "category": "Ice",
         "amount": 2000, "description": "Ice blocks"},
    ]
    for e in expenses_data:
        existing = await db["expenses"].find_one({
            "tripId": e["tripId"], "description": e["description"],
            "companyId": company_id,
        })
        if existing:
            continue
        await db["expenses"].insert_one({
            **e, "companyId": company_id,
            "recordedBy": str(user_ids.get("broker@demo.com", "")),
            "expenseDate": now.isoformat(),
            "createdAt": now, "updatedAt": now,
        })
    print(f"  {len(expenses_data)} expenses ready")

    # ─── Cash Advances ───
    print("Seeding cash advances...")
    ca_data = [
        {"requestedBy": str(crew_ids.get("Pedro Martinez", "")),
         "amount": 2000, "reason": "Family emergency", "status": "approved"},
        {"requestedBy": str(crew_ids.get("Miguel Lopez", "")),
         "amount": 1500, "reason": "Medical expenses", "status": "approved"},
        {"requestedBy": captain_id,
         "amount": 3000, "reason": "Vessel repairs", "status": "approved"},
    ]
    for ca in ca_data:
        existing = await db["cash-advances"].find_one({
            "requestedBy": ca["requestedBy"], "amount": ca["amount"],
            "companyId": company_id,
        })
        if existing:
            continue
        await db["cash-advances"].insert_one({
            **ca, "companyId": company_id,
            "tripId": str(trip_ids[0]),
            "approvedBy": str(user_ids.get("broker@demo.com", "")),
            "approvedDate": now.isoformat(),
            "createdAt": now, "updatedAt": now,
        })
    print(f"  {len(ca_data)} cash advances ready")

    # ─── Catches ───
    print("Seeding catches...")
    catches_data = [
        {"tripId": str(trip_ids[0]),
         "speciesBreakdown": {"Tuna": 45, "Bangus": 387},
         "totalWeight": 432, "totalValue": 52368},
        {"tripId": str(trip_ids[1]),
         "speciesBreakdown": {"Galunggong": 200, "Lapu-Lapu": 35},
         "totalWeight": 235, "totalValue": 39750},
    ]
    for c in catches_data:
        existing = await db["catches"].find_one({
            "tripId": c["tripId"], "companyId": company_id,
        })
        if existing:
            continue
        await db["catches"].insert_one({
            **c, "companyId": company_id,
            "catchDate": now.isoformat(),
            "createdAt": now, "updatedAt": now,
        })
    print(f"  {len(catches_data)} catches ready")

    # ─── Profit Sharing Policies ───
    print("Seeding profit sharing policies...")
    existing_policy = await db["profit-sharing-policies"].find_one({
        "companyId": company_id, "name": "Standard Pakura Policy",
    })
    if not existing_policy:
        await db["profit-sharing-policies"].insert_one({
            "name": "Standard Pakura Policy",
            "boatOwnerId": str(user_ids.get("owner@demo.com", "")),
            "pakuraDivisor": 3, "tongkoDivisor": 2,
            "sinakahan": 1000,
            "captainOwnerSplitType": "members_split",
            "totalMembers": 4, "captainMembersShare": 1,
            "captainIsOwner": False,
            "brokerPercentage": 10, "boatOwnerPercentage": 60,
            "fishermanPercentage": 30,
            "isActive": True,
            "companyId": company_id,
            "createdAt": now, "updatedAt": now,
        })
    print("  Policy ready")

    # ─── Profit Shares ───
    print("Seeding profit shares...")
    for i, tid in enumerate(trip_ids):
        existing = await db["profit_shares"].find_one({
            "tripId": str(tid), "companyId": company_id,
        })
        if existing:
            continue
        gross = 52368 if i == 0 else 39750
        expenses = 12000 if i == 0 else 7000
        net = gross - expenses
        broker_share = gross * 0.10
        crew_pool = net * 0.30
        per_crew = crew_pool / 4
        owner_share = net - broker_share - crew_pool

        fisherman_shares = {}
        for cid in crew_member_ids:
            fisherman_shares[cid] = round(per_crew, 2)
        # Captain gets extra
        fisherman_shares[captain_id] = round(per_crew * 1.5, 2)

        await db["profit_shares"].insert_one({
            "tripId": str(tid),
            "boatOwnerId": str(user_ids.get("owner@demo.com", "")),
            "generatedBy": str(user_ids.get("broker@demo.com", "")),
            "calculationDate": now.isoformat(),
            "totalRevenue": gross,
            "totalExpenses": expenses,
            "totalCashAdvances": 6500 if i == 0 else 0,
            "netProfit": net,
            "fishermanShares": fisherman_shares,
            "boatOwnerShare": round(owner_share, 2),
            "brokerShare": round(broker_share, 2),
            "brokerPercentage": 10,
            "boatOwnerPercentage": 60,
            "fishermanPercentage": 30,
            "status": "paid" if i == 0 else "draft",
            "companyId": company_id,
            "createdAt": now, "updatedAt": now,
        })
    print(f"  {len(trip_ids)} profit shares ready")

    # ─── Forecasts ───
    print("Seeding forecasts...")
    for species in ["Tuna", "Bangus", "Galunggong", "Lapu-Lapu"]:
        existing = await db["forecasts"].find_one({
            "species": species, "companyId": company_id,
        })
        if existing:
            continue
        await db["forecasts"].insert_one({
            "species": species, "month": now.month,
            "estimatedCatch": 150, "pricePerKg": 200,
            "companyId": company_id,
            "createdAt": now, "updatedAt": now,
        })
    print("  Forecasts ready")

    print()
    print("=" * 50)
    print("DEMO DATA SEEDED SUCCESSFULLY!")
    print("=" * 50)
    print()
    print("Login credentials (all use password: Demo1234!):")
    print("  Admin:   admin@demo.com")
    print("  Broker:  broker@demo.com")
    print("  Owner:   owner@demo.com")
    print("  Captain: captain@demo.com")
    print("  Crew:    pedro@demo.com / miguel@demo.com")
    print("           ramon@demo.com / carlos@demo.com")
    print()

    await disconnect_db()


if __name__ == "__main__":
    asyncio.run(seed_demo_data())
