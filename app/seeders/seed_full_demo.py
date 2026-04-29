"""
Full demo data seeder — exercises the entire profit-sharing flow:
roles, company, users (admin/broker/owner/fisherman), vessel owner,
vessel, crew, completed trips with catches, fish sales, expenses,
and a generated profit share.

Usage:
    python -m app.seeders.seed_full_demo
    python -m app.seeders.seed_full_demo --reset   # wipes demo trips/sales first
"""
from __future__ import annotations

import argparse
import asyncio
import random
from datetime import datetime, timedelta, timezone

from bson import ObjectId

from app.core.security import hash_password
from app.db import connect_db, disconnect_db, get_db
from app.seeders.roles_permissions import (
    seed_admin_role_with_all_permissions,
    seed_boat_owner_role_with_permissions,
    seed_broker_role_with_permissions,
    seed_fisherman_role_with_permissions,
)


DEMO_PASSWORD = "P@ssw0rd123"
COMPANY_NAME = "Demo Fishing Co"
COMPANY_CODE = "DFC001"

DEMO_TAG = "demo_full"  # marker on every doc this script inserts


# ─────────────────────────── helpers ───────────────────────────


async def upsert_user(db, *, email, first, last, role_id, company_id, now):
    existing = await db["users"].find_one({"email": email})
    if existing:
        return existing["_id"]
    result = await db["users"].insert_one(
        {
            "email": email,
            "password": hash_password(DEMO_PASSWORD),
            "firstName": first,
            "lastName": last,
            "role": role_id,
            "companyId": company_id,
            "companyApproved": True,
            "isActive": True,
            "createdAt": now,
            "updatedAt": now,
            "demoTag": DEMO_TAG,
        }
    )
    return result.inserted_id


async def reset_demo(db):
    print("Resetting prior demo transactional data...")
    for col in (
        "trips",
        "catches",
        "fish_sales",
        "expenses",
        "profit_shares",
        "crew",
        "vessels",
        "vessel_owners",
        "profit_sharing_policies",
    ):
        deleted = await db[col].delete_many({"demoTag": DEMO_TAG})
        print(f"  - {col}: removed {deleted.deleted_count}")


# ─────────────────────────── main ───────────────────────────


async def seed_full_demo(reset: bool = False):
    await connect_db()
    db = get_db()
    now = datetime.now(timezone.utc)

    print("Seeding roles & permissions...")
    await seed_admin_role_with_all_permissions()
    await seed_broker_role_with_permissions()
    await seed_boat_owner_role_with_permissions()
    await seed_fisherman_role_with_permissions()

    role_map: dict[str, ObjectId] = {}
    async for r in db["roles"].find():
        role_map[r["name"]] = r["_id"]

    # ─── Company ───
    print("Seeding company...")
    company = await db["companies"].find_one({"companyName": COMPANY_NAME})
    if not company:
        result = await db["companies"].insert_one(
            {
                "companyName": COMPANY_NAME,
                "companyCode": COMPANY_CODE,
                "companyAddress": "Cebu, Philippines",
                "companyPhone": "+63 917 000 0000",
                "companyTaxId": "000-000-000",
                "createdAt": now,
                "updatedAt": now,
            }
        )
        company_id = result.inserted_id
    else:
        company_id = company["_id"]

    # ─── Users ───
    print("Seeding users...")
    super_id = await upsert_user(
        db, email="super@demo.com", first="Super", last="Admin",
        role_id=role_map.get("super"), company_id=company_id, now=now,
    )
    admin_id = await upsert_user(
        db, email="admin@demo.com", first="Admin", last="User",
        role_id=role_map.get("admin"), company_id=company_id, now=now,
    )
    broker_id = await upsert_user(
        db, email="broker@demo.com", first="Bruno", last="Broker",
        role_id=role_map.get("broker"), company_id=company_id, now=now,
    )
    owner_id = await upsert_user(
        db, email="owner@demo.com", first="Oscar", last="Owner",
        role_id=role_map.get("boat_owner") or role_map.get("owner"),
        company_id=company_id, now=now,
    )
    fisherman_ids: list[ObjectId] = []
    for i, (fn, ln) in enumerate(
        [("Pedro", "Cruz"), ("Mario", "Reyes"), ("Juan", "Santos")]
    ):
        fid = await upsert_user(
            db, email=f"fisher{i + 1}@demo.com", first=fn, last=ln,
            role_id=role_map.get("fisherman"),
            company_id=company_id, now=now,
        )
        fisherman_ids.append(fid)

    if reset:
        await reset_demo(db)

    # ─── Vessel Owner ───
    print("Seeding vessel owner...")
    vo_doc = {
        "userId": str(owner_id),
        "name": "Oscar Owner",
        "contactNumber": "+63 917 111 2222",
        "email": "owner@demo.com",
        "address": "Mactan, Cebu",
        "status": "active",
        "companyId": company_id,
        "createdAt": now,
        "updatedAt": now,
        "demoTag": DEMO_TAG,
    }
    vo_result = await db["vessel_owners"].insert_one(vo_doc)
    vessel_owner_id = vo_result.inserted_id

    # ─── Vessel ───
    print("Seeding vessel...")
    vessel_doc = {
        "vesselOwnerId": str(vessel_owner_id),
        "name": "FB Maria Clara",
        "registrationNumber": "FB-2026-001",
        "type": "Fishing Boat",
        "length": 12.5,
        "capacity": 5.0,
        "crewCapacity": 6,
        "status": "active",
        "notes": "Demo vessel",
        "companyId": company_id,
        "createdAt": now,
        "updatedAt": now,
        "demoTag": DEMO_TAG,
    }
    v_result = await db["vessels"].insert_one(vessel_doc)
    vessel_id = v_result.inserted_id

    # ─── Crew ───
    print("Seeding crew members...")
    crew_data = [
        {"first": "Pedro", "last": "Cruz", "role": "captain",
         "type": "tongko", "user": fisherman_ids[0]},
        {"first": "Mario", "last": "Reyes", "role": "crew",
         "type": "pakura", "user": fisherman_ids[1]},
        {"first": "Juan", "last": "Santos", "role": "crew",
         "type": "pakura", "user": fisherman_ids[2]},
    ]
    crew_ids = []
    crew_user_ids: list[ObjectId] = []
    for c in crew_data:
        crew_user_ids.append(c["user"])
        r = await db["crew"].insert_one(
            {
                "userId": str(c["user"]),
                "firstName": c["first"],
                "lastName": c["last"],
                "contactNumber": "+63 917 000 0000",
                "vessel": vessel_doc["name"],
                "vesselId": str(vessel_id),
                "role": c["role"],
                "crewType": c["type"],
                "status": "active",
                "companyId": company_id,
                "createdAt": now,
                "updatedAt": now,
                "demoTag": DEMO_TAG,
            }
        )
        crew_ids.append(r.inserted_id)

    # ─── Profit-sharing policy ───
    print("Seeding profit-sharing policy...")
    await db["profit_sharing_policies"].insert_one(
        {
            "name": "Default 60/30/10",
            "ownerPercentage": 60,
            "crewPercentage": 30,
            "brokerPercentage": 10,
            "isActive": True,
            "companyId": company_id,
            "createdAt": now,
            "updatedAt": now,
            "demoTag": DEMO_TAG,
        }
    )

    # ─── Trips + child docs ───
    print("Seeding trips, catches, sales, expenses, profit shares...")
    species_pool = [
        "Auxis rochei",
        "Elagatis bipinnulata",
        "Euthynnus affinis",
        "Katsuwonus pelamis",
        "Thunnus albacares",
    ]

    for trip_index in range(3):
        days_ago = (trip_index + 1) * 7
        start = now - timedelta(days=days_ago + 2)
        end = now - timedelta(days=days_ago)

        trip_doc = {
            "tripName": f"Trip #{trip_index + 1} — {start.strftime('%b %d')}",
            "vesselName": vessel_doc["name"],
            "vesselId": str(vessel_id),
            "ownerId": str(owner_id),
            "financerId": str(broker_id),
            "encoderId": str(broker_id),
            "brokerId": str(broker_id),
            # Store user ids so the fisherman pages (which filter by the
            # logged-in user's id) can match.
            "captainId": str(crew_user_ids[0]),
            "captainName": "Pedro Cruz",
            "crewMembers": [str(uid) for uid in crew_user_ids],
            "crewType": "pakura",
            "departureDate": start,
            "returnDate": end,
            "startDate": start,
            "endDate": end,
            "status": "completed",
            "location": "Bohol Sea",
            "notes": f"Demo trip {trip_index + 1}",
            "companyId": company_id,
            "companyName": COMPANY_NAME,
            "createdAt": start,
            "updatedAt": end,
            "demoTag": DEMO_TAG,
        }
        trip_result = await db["trips"].insert_one(trip_doc)
        trip_id = trip_result.inserted_id

        # ── Catch ──
        species_breakdown = {
            random.choice(species_pool): round(random.uniform(20, 60), 2)
            for _ in range(3)
        }
        total_weight = round(sum(species_breakdown.values()), 2)
        price_per_kg = random.choice([180, 220, 260])
        total_value = round(total_weight * price_per_kg, 2)

        await db["catches"].insert_one(
            {
                "tripId": str(trip_id),
                "catchDate": end,
                "totalWeight": total_weight,
                "totalValue": total_value,
                "speciesBreakdown": species_breakdown,
                "expenses": 0,
                "cashAdvances": 0,
                "notes": "Demo catch",
                "companyId": company_id,
                "createdAt": end,
                "updatedAt": end,
                "demoTag": DEMO_TAG,
            }
        )

        # ── Fish sale ──
        await db["fish_sales"].insert_one(
            {
                "tripId": str(trip_id),
                "recordedBy": str(broker_id),
                "saleDate": end,
                "buyerName": random.choice(
                    ["Cebu Market", "Mactan Buyer", "Bohol Trader"]
                ),
                "totalWeight": total_weight,
                "totalPrice": total_value,
                "pricePerKg": price_per_kg,
                "speciesBreakdown": species_breakdown,
                "notes": "Demo sale",
                "companyId": company_id,
                "createdAt": end,
                "updatedAt": end,
                "demoTag": DEMO_TAG,
            }
        )

        # ── Expenses ──
        expense_rows = [
            ("Fuel", "Diesel for trip", round(total_value * 0.10, 2)),
            ("Ice", "Ice blocks", round(total_value * 0.03, 2)),
            ("Food", "Crew provisions", round(total_value * 0.04, 2)),
        ]
        for cat, desc, amt in expense_rows:
            await db["expenses"].insert_one(
                {
                    "tripId": str(trip_id),
                    "recordedBy": str(broker_id),
                    "recordedByName": "Bruno Broker",
                    "expenseDate": end,
                    "category": cat,
                    "description": desc,
                    "amount": amt,
                    "companyId": company_id,
                    "createdAt": end,
                    "updatedAt": end,
                    "demoTag": DEMO_TAG,
                }
            )

        total_expenses = round(sum(amt for _, _, amt in expense_rows), 2)

        # Realistic Pakura-style profit computation
        broker_pct = 10.0
        small_bangka_pct = 20.0
        big_bangka_pct = 10.0
        divisor = 3  # Pakura

        gross_revenue = total_value
        # Split small/big fish randomly (~60% small, ~40% big)
        small_fish_total = round(gross_revenue * 0.6, 2)
        big_fish_total = round(gross_revenue - small_fish_total, 2)
        total_small_weight = round(total_weight * 0.7, 2)

        broker_share = round(gross_revenue * broker_pct / 100, 2)
        small_bangka = round(small_fish_total * small_bangka_pct / 100, 2)
        big_bangka = round(big_fish_total * big_bangka_pct / 100, 2)
        bangka_share = round(small_bangka + big_bangka, 2)

        small_crew_pool = round(small_fish_total - small_bangka, 2)
        big_crew_pool = round(big_fish_total - big_bangka, 2)
        crew_pool = round((small_crew_pool + big_crew_pool) / divisor, 2)

        captain_owner_net = round(
            gross_revenue - broker_share - bangka_share - crew_pool, 2
        )
        captain_share = round(captain_owner_net * 0.25, 2)
        owner_share_val = round(captain_owner_net - captain_share, 2)

        net_profit = round(gross_revenue - broker_share - total_expenses, 2)

        per_crew_gross = round(crew_pool / max(1, len(crew_ids)), 2)

        # Build crewBreakdown with realistic deductions
        cash_advances = [500.0, 300.0, 0.0]
        crew_breakdown = []
        fisherman_shares = {}
        for idx, (c_id, c_uid) in enumerate(zip(crew_ids, crew_user_ids)):
            ca = cash_advances[idx] if idx < len(cash_advances) else 0.0
            net_payout = round(per_crew_gross - ca, 2)
            crew_breakdown.append({
                "crewId": str(c_id),
                "crewName": crew_data[idx]["first"] + " " + crew_data[idx]["last"],
                "grossShare": per_crew_gross,
                "smallFishEarnings": round(per_crew_gross * 0.5, 2),
                "bigFishEarnings": round(per_crew_gross * 0.5, 2) if idx == 0 else 0,
                "bigFishDirectAttribution": round(big_fish_total, 2) if idx == 0 else 0,
                "cashAdvanceDeduction": ca,
                "sinakahan": 0,
                "kusinero": 0,
                "customDeductions": 0,
                "totalDeductions": ca,
                "netPayout": net_payout,
            })
            fisherman_shares[str(c_uid)] = net_payout

        # ── Profit share ──
        await db["profit_shares"].insert_one(
            {
                "tripId": str(trip_id),
                "boatOwnerId": str(owner_id),
                "generatedBy": str(broker_id),
                "calculationDate": end,
                "crewType": "pakura",
                "grossRevenue": gross_revenue,
                "smallFishTotal": small_fish_total,
                "bigFishTotal": big_fish_total,
                "totalSmallWeight": total_small_weight,
                "brokerShare": broker_share,
                "brokerPercentage": broker_pct,
                "bangkaShare": bangka_share,
                "smallBangka": small_bangka,
                "bigBangka": big_bangka,
                "smallBangkaPercentage": small_bangka_pct,
                "bigBangkaPercentage": big_bangka_pct,
                "crewPool": crew_pool,
                "smallCrewPool": small_crew_pool,
                "bigCrewPool": big_crew_pool,
                "divisor": divisor,
                "captainOwnerNet": captain_owner_net,
                "captainShare": captain_share,
                "ownerShare": owner_share_val,
                "captainId": str(crew_ids[0]),
                "captainIsOwner": False,
                "totalExpenses": total_expenses,
                "totalCashAdvances": sum(cash_advances[:len(crew_ids)]),
                "sinakahan": 0.0,
                "kusineroAmount": 0.0,
                "nilicomanEnabled": False,
                "nilicomanTotal": 0.0,
                "nilicomanOwner": 0.0,
                "nilicomanCrewEach": 0.0,
                "netProfit": net_profit,
                "totalRevenue": gross_revenue,
                "fishermanShares": fisherman_shares,
                "crewBreakdown": crew_breakdown,
                "status": "approved",
                "notes": "Auto-generated demo share",
                "companyId": company_id,
                "createdAt": end,
                "updatedAt": end,
                "demoTag": DEMO_TAG,
            }
        )

    print()
    print("=" * 60)
    print("FULL DEMO DATA SEEDED")
    print("=" * 60)
    print(f"Password for all accounts: {DEMO_PASSWORD}")
    print("  super@demo.com   (super)")
    print("  admin@demo.com   (admin)")
    print("  broker@demo.com  (broker)")
    print("  owner@demo.com   (boat owner)")
    print("  fisher1@demo.com / fisher2@demo.com / fisher3@demo.com")
    print()
    print("Created: 1 vessel owner, 1 vessel, 3 crew, 3 completed trips,")
    print("         3 catches, 3 fish sales, 9 expenses, 3 profit shares,")
    print("         1 profit-sharing policy.")
    print()
    print("Re-run with --reset to wipe & recreate transactional demo data.")
    await disconnect_db()


def _parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--reset", action="store_true",
                   help="delete existing demo transactional data first")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(seed_full_demo(reset=args.reset))
