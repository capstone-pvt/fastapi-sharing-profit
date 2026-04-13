"""Seed demo transactional data: vessels, crew, trips, fish sales, expenses,
cash advances, profit shares, and notifications.

Run AFTER reset_and_reseed.py (which creates roles, users, companies, species).

Usage:
    cd profit_sharing_api_fastapi
    PYTHONPATH=. python scripts/seed_demo_transactions.py
"""

from __future__ import annotations

import asyncio
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bson import ObjectId
from dotenv import load_dotenv

_project_root = Path(__file__).resolve().parents[1]
load_dotenv(_project_root / ".env")

from app.core.security import hash_password  # noqa: E402
from app.db import connect_db, disconnect_db, get_db  # noqa: E402
from app.utils import to_object_id  # noqa: E402

DEMO_TAG = "demo_full"
PASSWORD = hash_password("P@ssw0rd123")
NOW = datetime.now(timezone.utc)


async def _get_role_id(db, name: str) -> ObjectId:
    role = await db["roles"].find_one({"name": name})
    if not role:
        raise ValueError(f"Role '{name}' not found — run reset_and_reseed.py first")
    return role["_id"]


async def _get_company(db, name: str) -> dict:
    company = await db["companies"].find_one(
        {"companyName": {"$regex": f"^{name}$", "$options": "i"}}
    )
    if not company:
        raise ValueError(f"Company '{name}' not found — run reset_and_reseed.py first")
    return company


async def _upsert_user(db, email: str, data: dict) -> ObjectId:
    existing = await db["users"].find_one({"email": email})
    if existing:
        await db["users"].update_one({"_id": existing["_id"]}, {"$set": data})
        return existing["_id"]
    data["email"] = email
    result = await db["users"].insert_one(data)
    return result.inserted_id


async def seed():
    await connect_db()
    db = get_db()

    print("=" * 60)
    print("  SEEDING DEMO TRANSACTIONAL DATA")
    print("=" * 60)

    # ── Resolve roles ───────────────────────────────────────────
    admin_role = await _get_role_id(db, "admin")
    broker_role = await _get_role_id(db, "broker")
    owner_role = await _get_role_id(db, "owner")
    crew_role = await _get_role_id(db, "crew")

    company = await _get_company(db, "Demo Fishing Co")
    company_id = company["_id"]
    company_code = company.get("companyCode", "")

    # ── 1. Users (with multi-role + birthday) ───────────────────
    print("\n[1/9] Seeding users...")

    admin_id = await _upsert_user(db, "admin@demo.com", {
        "firstName": "Admin", "lastName": "Santos",
        "password": PASSWORD,
        "roles": [admin_role, broker_role, owner_role],
        "companyId": company_id, "companyApproved": True,
        "birthday": "1990-05-15",
        "demoTag": DEMO_TAG, "createdAt": NOW, "updatedAt": NOW,
    })

    broker_id = await _upsert_user(db, "broker@demo.com", {
        "firstName": "Maria", "lastName": "Cruz",
        "password": PASSWORD,
        "roles": [broker_role],
        "companyId": company_id, "companyApproved": True,
        "birthday": "1988-03-22",
        "demoTag": DEMO_TAG, "createdAt": NOW, "updatedAt": NOW,
    })

    owner_id = await _upsert_user(db, "owner@demo.com", {
        "firstName": "Oscar", "lastName": "Reyes",
        "password": PASSWORD,
        "roles": [owner_role],
        "companyId": company_id, "companyApproved": True,
        "birthday": "1985-11-08",
        "demoTag": DEMO_TAG, "createdAt": NOW, "updatedAt": NOW,
    })

    fisher_data = [
        ("Pedro", "Dela Cruz", "fisher1@demo.com", "1992-07-10"),
        ("Mario", "Santos", "fisher2@demo.com", "1995-01-25"),
        ("Juan", "Garcia", "fisher3@demo.com", "1993-09-14"),
        ("Ramon", "Flores", "fisher4@demo.com", "1991-04-03"),
        ("Jose", "Lopez", "fisher5@demo.com", "1994-12-20"),
    ]
    fisher_ids = []
    for fn, ln, email, bday in fisher_data:
        fid = await _upsert_user(db, email, {
            "firstName": fn, "lastName": ln,
            "password": PASSWORD,
            "roles": [crew_role],
            "companyId": company_id, "companyApproved": True,
            "birthday": bday,
            "demoTag": DEMO_TAG, "createdAt": NOW, "updatedAt": NOW,
        })
        fisher_ids.append(fid)

    print(f"  Created/updated 8 users (1 admin+broker+owner, 1 broker, 1 owner, 5 crew)")

    # ── 2. Vessel Owners ────────────────────────────────────────
    print("\n[2/9] Seeding vessel owners...")

    vo_docs = [
        {"userId": str(owner_id), "name": "Oscar Reyes", "email": "owner@demo.com",
         "contactNumber": "09171234567", "status": "active",
         "companyId": company_id, "demoTag": DEMO_TAG, "createdAt": NOW, "updatedAt": NOW},
        {"userId": str(admin_id), "name": "Admin Santos", "email": "admin@demo.com",
         "contactNumber": "09179876543", "status": "active",
         "companyId": company_id, "demoTag": DEMO_TAG, "createdAt": NOW, "updatedAt": NOW},
    ]
    vo_ids = []
    for vo in vo_docs:
        result = await db["vessel_owners"].update_one(
            {"email": vo["email"]}, {"$set": vo}, upsert=True
        )
        doc = await db["vessel_owners"].find_one({"email": vo["email"]})
        vo_ids.append(doc["_id"])
    print(f"  Created 2 vessel owners")

    # ── 3. Vessels ──────────────────────────────────────────────
    print("\n[3/9] Seeding vessels...")

    vessels = [
        {"name": "FB Maria Clara", "registrationNumber": "REG-2024-001",
         "type": "Fishing Boat", "length": 12.5, "capacity": 5.0, "crewCapacity": 8,
         "vesselOwnerId": str(vo_ids[0]), "status": "active",
         "notes": "Documents attached: Fishing Permit, BFAR Registration",
         "companyId": company_id, "demoTag": DEMO_TAG, "createdAt": NOW, "updatedAt": NOW},
        {"name": "FB San Pedro", "registrationNumber": "REG-2024-002",
         "type": "Trawler", "length": 15.0, "capacity": 8.0, "crewCapacity": 12,
         "vesselOwnerId": str(vo_ids[0]), "status": "active",
         "notes": "Documents attached: Fishing Permit, Coast Guard Clearance",
         "companyId": company_id, "demoTag": DEMO_TAG, "createdAt": NOW, "updatedAt": NOW},
        {"name": "FB Estrella", "registrationNumber": "REG-2024-003",
         "type": "Fishing Boat", "length": 10.0, "capacity": 3.5, "crewCapacity": 6,
         "vesselOwnerId": str(vo_ids[1]), "status": "active",
         "companyId": company_id, "demoTag": DEMO_TAG, "createdAt": NOW, "updatedAt": NOW},
    ]
    vessel_ids = []
    for v in vessels:
        result = await db["vessels"].update_one(
            {"name": v["name"], "companyId": company_id}, {"$set": v}, upsert=True
        )
        doc = await db["vessels"].find_one({"name": v["name"], "companyId": company_id})
        vessel_ids.append(doc["_id"])
    print(f"  Created 3 vessels")

    # ── 4. Crew Members (fishermen) ─────────────────────────────
    print("\n[4/9] Seeding crew members...")

    crew_docs = []
    for i, (fn, ln, email, _) in enumerate(fisher_data):
        crew_docs.append({
            "userId": str(fisher_ids[i]),
            "name": f"{fn} {ln}",
            "firstName": fn, "lastName": ln,
            "email": email,
            "position": "Captain" if i == 0 else "Crew",
            "crewType": "pakura" if i < 3 else "tongko",
            "status": "active",
            "companyId": company_id, "demoTag": DEMO_TAG,
            "createdAt": NOW, "updatedAt": NOW,
        })
    crew_member_ids = []
    for cd in crew_docs:
        await db["crew"].update_one(
            {"email": cd["email"]}, {"$set": cd}, upsert=True
        )
        doc = await db["crew"].find_one({"email": cd["email"]})
        crew_member_ids.append(doc["_id"])
    print(f"  Created 5 crew members (1 captain, 4 crew)")

    # ── 5. Profit Sharing Policy ────────────────────────────────
    print("\n[5/9] Seeding profit sharing policy...")

    policy_doc = {
        "vesselOwnerId": str(vo_ids[0]),
        "brokerPercentage": 10,
        "smallBangkaPercentage": 20,
        "bigBangkaPercentage": 10,
        "pakuraDivisor": 3,
        "tongkoDivisor": 2,
        "sinakahan": 100,
        "kusineroAmount": 50,
        "captainOwnerSplitType": "members_split",
        "totalMembers": 4,
        "captainMembersShare": 1,
        "captainIsOwner": False,
        "nilicomanEnabled": True,
        "nilicomanOwnerPercentage": 60,
        "boatOwnerPercentage": 60,
        "fishermanPercentage": 30,
        "customDeductions": [
            {"label": "Motorman", "amount": 200},
        ],
        "companyId": company_id, "demoTag": DEMO_TAG,
        "createdAt": NOW, "updatedAt": NOW,
    }
    await db["profit_sharing_policies"].update_one(
        {"vesselOwnerId": str(vo_ids[0])}, {"$set": policy_doc}, upsert=True
    )
    print("  Created profit sharing policy (Pakura, 10% broker, nilicoman enabled)")

    # ── 6. Trips + Fish Sales + Expenses ────────────────────────
    print("\n[6/9] Seeding trips, fish sales, and expenses...")

    species_list = [
        ("Bangus", 160), ("Tilapia", 140), ("Yellowfin Tuna", 350),
        ("Skipjack Tuna", 220), ("Lapu-Lapu", 450), ("Galunggong", 120),
        ("Mackerel Scad", 130), ("Tanigue", 320), ("Dalagang Bukid", 180),
    ]
    locations = ["Bohol Sea", "Cebu Strait", "Mactan Channel", "Camotes Sea"]
    buyers = ["Cebu Fish Market", "Mactan Buyer", "Bohol Trader", "Taboan Market"]

    trip_configs = [
        {"days_ago": 30, "vessel_idx": 0, "crew": [0, 1, 2], "type": "pakura", "approved": True},
        {"days_ago": 15, "vessel_idx": 0, "crew": [0, 2, 3], "type": "pakura", "approved": True},
        {"days_ago": 7, "vessel_idx": 1, "crew": [1, 3, 4], "type": "tongko", "approved": True},
        {"days_ago": 3, "vessel_idx": 0, "crew": [0, 1, 4], "type": "pakura", "approved": False},
        {"days_ago": 1, "vessel_idx": 2, "crew": [2, 3], "type": "tongko", "approved": False},
    ]

    trip_ids = []
    for t_idx, tc in enumerate(trip_configs):
        departure = NOW - timedelta(days=tc["days_ago"])
        return_date = departure + timedelta(days=2)
        captain_idx = tc["crew"][0]
        crew_ids_for_trip = [crew_member_ids[i] for i in tc["crew"]]
        crew_details = [
            {"_id": str(crew_member_ids[i]), "id": str(crew_member_ids[i]),
             "name": f"{fisher_data[i][0]} {fisher_data[i][1]}",
             "crewMemberId": str(crew_member_ids[i])}
            for i in tc["crew"]
        ]

        is_completed = tc["approved"] or tc["days_ago"] > 2
        trip_doc = {
            "tripName": f"Trip #{t_idx + 1}",
            "vesselName": vessels[tc["vessel_idx"]]["name"],
            "vesselId": vessel_ids[tc["vessel_idx"]],
            "ownerId": owner_id,
            "brokerId": broker_id,
            "financerId": broker_id,
            "encoderId": broker_id,
            "captainId": str(crew_member_ids[captain_idx]),
            "captainName": f"{fisher_data[captain_idx][0]} {fisher_data[captain_idx][1]}",
            "crewMembers": [str(cid) for cid in crew_ids_for_trip],
            "crewDetails": crew_details,
            "crewType": tc["type"],
            "departureDate": departure.isoformat(),
            "returnDate": return_date.isoformat(),
            "status": "completed" if is_completed else "in_progress",
            "salesApproved": tc["approved"],
            "salesApprovedBy": "Oscar Reyes" if tc["approved"] else None,
            "salesApprovedAt": return_date.isoformat() if tc["approved"] else None,
            "location": random.choice(locations),
            "companyId": company_id, "companyName": "Demo Fishing Co",
            "demoTag": DEMO_TAG, "createdAt": departure, "updatedAt": NOW,
        }
        result = await db["trips"].insert_one(trip_doc)
        trip_id = result.inserted_id
        trip_ids.append(trip_id)

        # Fish sales with line items
        if is_completed:
            num_entries = random.randint(4, 8)
            line_items = []
            for _ in range(num_entries):
                sp_name, sp_price = random.choice(species_list)
                is_big = random.random() < 0.3  # 30% chance big fish
                kilos = round(random.uniform(2, 25), 1)
                price = sp_price + random.randint(-20, 30)
                caught_by = random.choice(tc["crew"]) if is_big else None
                line_items.append({
                    "speciesName": sp_name,
                    "category": "big_fish" if is_big else "small_fish",
                    "kilos": kilos,
                    "pricePerKg": price,
                    "caughtById": str(crew_member_ids[caught_by]) if caught_by is not None else None,
                    "caughtByName": f"{fisher_data[caught_by][0]} {fisher_data[caught_by][1]}" if caught_by is not None else None,
                })

            total_weight = sum(li["kilos"] for li in line_items)
            total_price = sum(li["kilos"] * li["pricePerKg"] for li in line_items)

            sale_doc = {
                "tripId": str(trip_id),
                "recordedBy": str(broker_id),
                "saleDate": return_date.isoformat(),
                "buyerName": random.choice(buyers),
                "totalWeight": round(total_weight, 2),
                "totalPrice": round(total_price, 2),
                "pricePerKg": round(total_price / max(total_weight, 0.01), 2),
                "lineItems": line_items,
                "companyId": company_id, "demoTag": DEMO_TAG,
                "createdAt": return_date, "updatedAt": NOW,
            }
            await db["fish_sales"].insert_one(sale_doc)

            # Expenses
            expenses = [
                {"category": "Fuel", "amount": round(total_price * 0.08, 2),
                 "description": "Diesel fuel for trip"},
                {"category": "Ice", "amount": round(total_price * 0.03, 2),
                 "description": "Block ice for storage"},
                {"category": "Grocery", "amount": round(total_price * 0.04, 2),
                 "description": "Food for crew"},
            ]
            for exp in expenses:
                exp.update({
                    "tripId": str(trip_id), "recordedBy": str(broker_id),
                    "companyId": company_id, "demoTag": DEMO_TAG,
                    "createdAt": return_date, "updatedAt": NOW,
                })
            await db["expenses"].insert_many(expenses)

    print(f"  Created {len(trip_ids)} trips with fish sales and expenses")

    # ── 6b. Catches (per crew fish attribution) ─────────────────
    print("\n[6b/12] Seeding catches per crew...")

    catch_count = 0
    for t_idx, tc in enumerate(trip_configs):
        is_completed = tc["approved"] or tc["days_ago"] > 2
        if not is_completed:
            continue
        trip_id = trip_ids[t_idx]
        departure = NOW - timedelta(days=tc["days_ago"])
        return_date = departure + timedelta(days=2)

        for crew_idx in tc["crew"]:
            num_catches = random.randint(2, 5)
            for _ in range(num_catches):
                sp_name, sp_price = random.choice(species_list)
                weight = round(random.uniform(0.5, 15.0), 2)
                catch_doc = {
                    "tripId": str(trip_id),
                    "crewMemberId": str(crew_member_ids[crew_idx]),
                    "crewMemberName": f"{fisher_data[crew_idx][0]} {fisher_data[crew_idx][1]}",
                    "species": sp_name,
                    "weight": weight,
                    "pricePerKg": sp_price + random.randint(-15, 25),
                    "category": "big_fish" if weight > 8 else "small_fish",
                    "caughtAt": (return_date - timedelta(hours=random.randint(1, 36))).isoformat(),
                    "companyId": company_id, "demoTag": DEMO_TAG,
                    "createdAt": return_date, "updatedAt": NOW,
                }
                await db["catches"].insert_one(catch_doc)
                catch_count += 1

    print(f"  Created {catch_count} catches across completed trips")

    # ── 6c. Profit Shares (for approved trips) ──────────────────
    print("\n[6c/12] Seeding profit shares for approved trips...")

    ps_count = 0
    for t_idx, tc in enumerate(trip_configs):
        if not tc["approved"]:
            continue
        trip_id = trip_ids[t_idx]
        departure = NOW - timedelta(days=tc["days_ago"])
        return_date = departure + timedelta(days=2)

        # Get the fish sale for this trip
        sale = await db["fish_sales"].find_one({"tripId": str(trip_id)})
        if not sale:
            continue

        line_items = sale.get("lineItems", [])
        total_price = sale.get("totalPrice", 0)
        total_weight = sale.get("totalWeight", 0)

        # Compute small/big fish totals
        small_total = sum(
            li["kilos"] * li["pricePerKg"]
            for li in line_items if "big" not in (li.get("category") or "")
        )
        big_total = sum(
            li["kilos"] * li["pricePerKg"]
            for li in line_items if "big" in (li.get("category") or "")
        )
        gross_revenue = round(small_total + big_total, 2)

        # Get expenses
        trip_expenses = await db["expenses"].find({"tripId": str(trip_id)}).to_list(100)
        total_expenses = round(sum(float(e.get("amount", 0)) for e in trip_expenses), 2)

        # Get cash advances for this trip
        trip_cas = await db["cash_advances"].find(
            {"tripId": str(trip_id), "status": "approved"}
        ).to_list(100)
        ca_per_crew = {}
        for ca in trip_cas:
            rid = ca.get("requestedBy", "")
            ca_per_crew[rid] = ca_per_crew.get(rid, 0) + float(ca.get("amount", 0))
        total_cash_advances = sum(ca_per_crew.values())

        # Compute using policy
        broker_pct = 0.10
        small_bangka_pct = 0.20
        big_bangka_pct = 0.10
        divisor = 3 if tc["type"] == "pakura" else 2

        broker_share = round(gross_revenue * broker_pct, 2)
        small_bangka = round(small_total * small_bangka_pct, 2)
        big_bangka = round(big_total * big_bangka_pct, 2)
        total_bangka = small_bangka + big_bangka

        small_crew_pool = round((small_total - small_bangka) / divisor, 2)
        big_crew_pool = round((big_total - big_bangka) / divisor, 2)
        total_crew_pool = small_crew_pool + big_crew_pool

        crew_in_trip = tc["crew"]
        crew_count = len(crew_in_trip)
        crew_share_each = round(total_crew_pool / crew_count, 2) if crew_count > 0 else 0

        captain_owner_net = round(gross_revenue - broker_share - total_crew_pool - total_expenses, 2)
        per_member = captain_owner_net / 4 if captain_owner_net > 0 else 0
        captain_share = round(per_member, 2)
        owner_share_val = round(captain_owner_net - captain_share, 2)

        # Big fish per crew
        big_per_crew = {}
        for li in line_items:
            if "big" in (li.get("category") or ""):
                cid = li.get("caughtById") or ""
                big_per_crew[cid] = big_per_crew.get(cid, 0) + li["kilos"] * li["pricePerKg"]

        # Build crew breakdown
        crew_breakdown = []
        fisherman_shares = {}
        sinakahan = 100.0
        kusinero = 50.0
        custom_deductions = 200.0  # motorman

        for ci in crew_in_trip:
            cid = str(crew_member_ids[ci])
            ca_deduction = ca_per_crew.get(cid, 0)
            total_deductions = ca_deduction + sinakahan + kusinero + custom_deductions
            net_payout = round(crew_share_each - total_deductions, 2)
            big_fish_direct = round(big_per_crew.get(cid, 0), 2)

            fisherman_shares[cid] = net_payout
            crew_breakdown.append({
                "crewId": cid,
                "crewName": f"{fisher_data[ci][0]} {fisher_data[ci][1]}",
                "grossShare": crew_share_each,
                "smallFishEarnings": round(crew_share_each * 0.7, 2),
                "bigFishEarnings": big_fish_direct,
                "bigFishDirectAttribution": big_fish_direct,
                "cashAdvanceDeduction": ca_deduction,
                "sinakahan": sinakahan,
                "kusinero": kusinero,
                "customDeductions": custom_deductions,
                "totalDeductions": total_deductions,
                "netPayout": net_payout,
            })

        # Determine status: Trip #1 = paid, Trip #2 = finalized, Trip #3 = draft
        statuses = ["paid", "finalized", "draft"]
        ps_status = statuses[t_idx] if t_idx < len(statuses) else "draft"

        ps_doc = {
            "tripId": str(trip_id),
            "tripName": f"Trip #{t_idx + 1}",
            "vesselName": vessels[tc["vessel_idx"]]["name"],
            "crewType": tc["type"],
            "status": ps_status,
            "generatedBy": str(owner_id),
            "generatedAt": return_date.isoformat(),

            # Revenue
            "grossRevenue": gross_revenue,
            "smallFishTotal": round(small_total, 2),
            "bigFishTotal": round(big_total, 2),
            "totalSmallWeight": round(sum(
                li["kilos"] for li in line_items if "big" not in (li.get("category") or "")
            ), 2),
            "totalRevenue": gross_revenue,
            "netProfit": round(gross_revenue - total_expenses, 2),

            # Shares
            "brokerShare": broker_share,
            "brokerPercentage": 10,
            "bangkaShare": total_bangka,
            "smallBangka": small_bangka,
            "bigBangka": big_bangka,
            "smallBangkaPercentage": 20,
            "bigBangkaPercentage": 10,
            "crewPool": total_crew_pool,
            "smallCrewPool": small_crew_pool,
            "bigCrewPool": big_crew_pool,
            "divisor": divisor,

            # Captain/Owner
            "captainOwnerNet": captain_owner_net,
            "captainShare": captain_share,
            "ownerShare": owner_share_val,
            "captainId": str(crew_member_ids[crew_in_trip[0]]),
            "captainIsOwner": False,
            "boatOwnerPercentage": 60,
            "fishermanPercentage": 30,

            # Deductions
            "totalExpenses": total_expenses,
            "totalCashAdvances": total_cash_advances,
            "sinakahan": sinakahan,
            "kusineroAmount": kusinero,

            # Nilicoman
            "nilicomanEnabled": True,
            "nilicomanTotal": captain_owner_net if captain_owner_net > 0 else 0,
            "nilicomanOwner": round(captain_owner_net * 0.6, 2) if captain_owner_net > 0 else 0,
            "nilicomanCrewEach": round(
                (captain_owner_net * 0.4 / crew_count) if captain_owner_net > 0 and crew_count > 0 else 0, 2
            ),

            # Crew breakdown
            "crewCount": crew_count,
            "fishermanShares": fisherman_shares,
            "crewBreakdown": crew_breakdown,

            "policyId": None,
            "companyId": company_id, "demoTag": DEMO_TAG,
            "createdAt": return_date, "updatedAt": NOW,
        }

        # Add finalized/paid metadata
        if ps_status in ("finalized", "paid"):
            ps_doc["finalizedBy"] = "Oscar Reyes"
            ps_doc["finalizedAt"] = (return_date + timedelta(days=1)).isoformat()
        if ps_status == "paid":
            ps_doc["paidBy"] = "Oscar Reyes"
            ps_doc["paidAt"] = (return_date + timedelta(days=2)).isoformat()

        await db["profit_shares"].insert_one(ps_doc)
        ps_count += 1

    print(f"  Created {ps_count} profit shares (1 paid, 1 finalized, 1 draft)")

    # Add profit share notifications for crew
    ps_notifs = []
    for ci in [0, 1, 2]:  # Trip #1 crew — paid
        ps_notifs.append({
            "userId": str(fisher_ids[ci]),
            "title": "Profit Share Paid",
            "body": f"Your earnings for Trip #1 on FB Maria Clara have been paid.",
            "category": "profit_share", "isRead": ci == 0,
            "createdAt": NOW - timedelta(days=26),
        })
    if ps_notifs:
        await db["notifications"].insert_many(ps_notifs)
        print(f"  Created {len(ps_notifs)} profit share notifications")

    # ── 7. Cash Advances ────────────────────────────────────────
    print("\n[7/9] Seeding cash advances...")

    ca_docs = [
        {"tripId": str(trip_ids[0]), "requestedBy": str(fisher_ids[0]),
         "requesterName": "Pedro Dela Cruz", "requesterRole": "crew",
         "amount": 500, "reason": "Personal emergency",
         "status": "approved", "approvedBy": str(broker_id),
         "companyId": company_id, "demoTag": DEMO_TAG,
         "createdAt": NOW - timedelta(days=28), "updatedAt": NOW},
        {"tripId": str(trip_ids[0]), "requestedBy": str(fisher_ids[1]),
         "requesterName": "Mario Santos", "requesterRole": "crew",
         "amount": 300, "reason": "Medicine",
         "status": "approved", "approvedBy": str(broker_id),
         "companyId": company_id, "demoTag": DEMO_TAG,
         "createdAt": NOW - timedelta(days=28), "updatedAt": NOW},
        {"tripId": str(trip_ids[2]), "requestedBy": str(fisher_ids[3]),
         "requesterName": "Ramon Flores", "requesterRole": "crew",
         "amount": 1000, "reason": "Family needs",
         "status": "pending",
         "companyId": company_id, "demoTag": DEMO_TAG,
         "createdAt": NOW - timedelta(days=5), "updatedAt": NOW},
    ]
    await db["cash_advances"].insert_many(ca_docs)
    print(f"  Created {len(ca_docs)} cash advances (2 approved, 1 pending)")

    # ── 8. Notifications ────────────────────────────────────────
    print("\n[8/9] Seeding notifications...")

    notif_docs = [
        {"userId": str(owner_id), "title": "Trip Completed",
         "body": "Trip #1 on FB Maria Clara has been completed.",
         "category": "trip", "isRead": True, "createdAt": NOW - timedelta(days=28)},
        {"userId": str(owner_id), "title": "New Cash Advance Request",
         "body": "Ramon Flores requested a cash advance of PHP 1,000.",
         "category": "cash_advance", "isRead": False, "createdAt": NOW - timedelta(days=5)},
        {"userId": str(fisher_ids[0]), "title": "Cash Advance Approved",
         "body": "Your cash advance of PHP 500 has been approved.",
         "category": "cash_advance", "isRead": True, "createdAt": NOW - timedelta(days=27)},
        {"userId": str(fisher_ids[1]), "title": "Cash Advance Approved",
         "body": "Your cash advance of PHP 300 has been approved.",
         "category": "cash_advance", "isRead": False, "createdAt": NOW - timedelta(days=27)},
        {"userId": str(admin_id), "title": "Sales Pending Approval",
         "body": "Trip #4 on FB Maria Clara has sales awaiting your approval.",
         "category": "sales_approval", "isRead": False, "createdAt": NOW - timedelta(days=2)},
    ]
    await db["notifications"].insert_many(notif_docs)
    print(f"  Created {len(notif_docs)} notifications")

    # ── 9. Forecasts ────────────────────────────────────────────
    print("\n[9/9] Seeding forecasts...")

    forecast_docs = [
        {"species": "Yellowfin Tuna", "abundance": "high", "period": "Q1 2026",
         "priceMin": 300, "priceMax": 400, "notes": "Peak season in Bohol Sea",
         "companyId": company_id, "demoTag": DEMO_TAG, "createdAt": NOW},
        {"species": "Bangus", "abundance": "moderate", "period": "Q1 2026",
         "priceMin": 140, "priceMax": 220, "notes": "Steady supply from brackish ponds",
         "companyId": company_id, "demoTag": DEMO_TAG, "createdAt": NOW},
        {"species": "Galunggong", "abundance": "high", "period": "Q1 2026",
         "priceMin": 100, "priceMax": 150, "notes": "Abundant in Camotes Sea",
         "companyId": company_id, "demoTag": DEMO_TAG, "createdAt": NOW},
    ]
    await db["forecasts"].insert_many(forecast_docs)
    print(f"  Created {len(forecast_docs)} forecasts")

    # ── Summary ─────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("  DEMO DATA SEEDED SUCCESSFULLY")
    print("=" * 60)
    print()
    print("Users (password: P@ssw0rd123):")
    print("  admin@demo.com   — Admin + Broker + Owner (multi-role)")
    print("  broker@demo.com  — Broker (Maria Cruz)")
    print("  owner@demo.com   — Owner (Oscar Reyes)")
    print("  fisher1@demo.com — Crew Captain (Pedro Dela Cruz)")
    print("  fisher2@demo.com — Crew (Mario Santos)")
    print("  fisher3@demo.com — Crew (Juan Garcia)")
    print("  fisher4@demo.com — Crew (Ramon Flores)")
    print("  fisher5@demo.com — Crew (Jose Lopez)")
    print()
    print("Vessels: FB Maria Clara, FB San Pedro, FB Estrella")
    print("Trips: 5 (3 completed+approved, 1 completed+pending, 1 in-progress)")
    print("Catches: Per crew with species, weight, category")
    print("Profit Shares: 3 (Trip#1=Paid, Trip#2=Finalized, Trip#3=Draft)")
    print("  - Full crew breakdown with deductions per member")
    print("Cash Advances: 3 (2 approved, 1 pending)")
    print("Notifications: 8+ (profit share + cash advance + sales)")
    print()

    await disconnect_db()


if __name__ == "__main__":
    asyncio.run(seed())
