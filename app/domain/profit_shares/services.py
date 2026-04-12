"""Server-side profit sharing computation engine.

Implements the 10-step algorithm from the thesis specification:
  1. Prepare Data
  2. Compute Small Fish Earnings (Straight Price)
  3. Compute Big Fish Earnings (direct crew attribution)
  4. Combine Earnings per crew
  5. Apply Policy-Based Deductions (bangka, sinakahan, kusinero, etc.)
  6. Special Rules (Pakura / Tongko divisors)
  7. Compute Final Earnings (crew, owner, broker, captain)
  8–10. Save, lock, output (handled by the route layer)

All monetary values are in Philippine Pesos (PHP).
"""

from __future__ import annotations

from typing import Any

from app.db import get_db
from app.utils import to_object_id


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def compute_profit_share(
    trip_id: str,
    policy_id: str | None = None,
    company_id: str | None = None,
) -> dict[str, Any]:
    """Run the full profit-sharing computation for a trip.

    Parameters
    ----------
    trip_id : str
        The MongoDB ``_id`` of the trip document.
    policy_id : str | None
        Explicit policy to use.  When *None*, the engine looks up the
        active policy for the trip's vessel owner.
    company_id : str | None
        Optional company scope (for multi-tenant isolation).

    Returns
    -------
    dict
        A complete breakdown ready for persistence or preview.
    """
    db = get_db()

    # ── Step 1: Prepare Data ─────────────────────────────────────────────

    # 1a. Trip
    trip = await db["trips"].find_one({"_id": to_object_id(trip_id)})
    if not trip:
        raise ValueError(f"Trip not found: {trip_id}")

    # Verify trip is completed and sales are approved
    trip_status = (trip.get("status") or "").lower()
    if trip_status != "completed":
        raise ValueError(
            f"Trip must be completed before computing profit share (current: {trip_status})"
        )
    if not trip.get("salesApproved", False):
        raise ValueError(
            "Fish sales must be reviewed and approved before computing profit share. "
            "Please approve the sales for this trip first."
        )

    crew_type = (trip.get("crewType") or "pakura").lower()
    captain_id = trip.get("captainId") or trip.get("captainName")
    crew_members: list[dict] = trip.get("crewMembers") or []
    crew_details: list[dict] = trip.get("crewDetails") or []
    crew_ids: list[str] = []
    crew_name_map: dict[str, str] = {}

    # Build crew roster — try crewDetails first (richer), fallback to crewMembers
    for cd in crew_details:
        cid = str(cd.get("_id") or cd.get("id") or cd.get("crewMemberId") or "")
        name = cd.get("name") or cd.get("fullName") or ""
        if cid:
            crew_ids.append(cid)
            crew_name_map[cid] = name
    if not crew_ids:
        for cm in crew_members:
            if isinstance(cm, str):
                crew_ids.append(cm)
            elif isinstance(cm, dict):
                cid = str(cm.get("_id") or cm.get("id") or "")
                if cid:
                    crew_ids.append(cid)
                    crew_name_map[cid] = cm.get("name") or cm.get("fullName") or ""

    crew_count = len(crew_ids)

    # 1b. Fish sales for this trip (with lineItems)
    fish_sales_cursor = db["fish_sales"].find({"tripId": trip_id})
    fish_sales = [doc async for doc in fish_sales_cursor]
    # Also check ObjectId variant
    if not fish_sales:
        fish_sales_cursor = db["fish_sales"].find({"tripId": to_object_id(trip_id)})
        fish_sales = [doc async for doc in fish_sales_cursor]

    # 1c. Expenses
    expenses_cursor = db["expenses"].find({"tripId": trip_id})
    expenses = [doc async for doc in expenses_cursor]
    if not expenses:
        expenses_cursor = db["expenses"].find({"tripId": to_object_id(trip_id)})
        expenses = [doc async for doc in expenses_cursor]

    total_expenses = sum(float(e.get("amount", 0)) for e in expenses)

    # 1d. Approved cash advances
    ca_query: dict[str, Any] = {"tripId": trip_id, "status": "approved"}
    ca_cursor = db["cash_advances"].find(ca_query)
    cash_advances = [doc async for doc in ca_cursor]
    if not cash_advances:
        ca_query["tripId"] = to_object_id(trip_id)
        ca_cursor = db["cash_advances"].find(ca_query)
        cash_advances = [doc async for doc in ca_cursor]

    cash_advance_per_crew: dict[str, float] = {}
    for ca in cash_advances:
        requestor = str(ca.get("requestedBy") or "")
        cash_advance_per_crew[requestor] = (
            cash_advance_per_crew.get(requestor, 0)
            + float(ca.get("amount", 0))
        )
    total_cash_advances = sum(cash_advance_per_crew.values())

    # 1e. Policy
    policy = await _resolve_policy(db, trip, policy_id)

    # Extract policy fields with sensible defaults
    broker_pct = float(policy.get("brokerPercentage", 10)) / 100
    small_bangka_pct = float(policy.get("smallBangkaPercentage", 20)) / 100
    big_bangka_pct = float(policy.get("bigBangkaPercentage", 10)) / 100
    pakura_divisor = int(policy.get("pakuraDivisor", 3))
    tongko_divisor = int(policy.get("tongkoDivisor", 2))
    sinakahan_amount = float(policy.get("sinakahan", 0))
    kusinero_amount = float(policy.get("kusineroAmount", 0))
    captain_owner_split_type = policy.get("captainOwnerSplitType", "members_split")
    total_members = int(policy.get("totalMembers", 4))
    captain_members_share = int(policy.get("captainMembersShare", 1))
    captain_is_owner = bool(policy.get("captainIsOwner", False))
    nilicoman_enabled = bool(policy.get("nilicomanEnabled", False))
    nilicoman_owner_pct = float(policy.get("nilicomanOwnerPercentage", 60)) / 100
    custom_deductions: list[dict] = policy.get("customDeductions") or []

    # ── Collect line items from all fish sales ───────────────────────────

    small_items: list[dict] = []
    big_items: list[dict] = []

    for sale in fish_sales:
        line_items = sale.get("lineItems") or []
        if line_items:
            for item in line_items:
                cat = (item.get("category") or "small_fish").lower()
                if "big" in cat:
                    big_items.append(item)
                else:
                    small_items.append(item)
        else:
            # Legacy sale without lineItems — treat entire sale as small fish
            small_items.append({
                "kilos": float(sale.get("totalWeight", 0)),
                "pricePerKg": (
                    float(sale.get("pricePerKg", 0))
                    or (float(sale.get("totalPrice", 0)) / max(float(sale.get("totalWeight", 1)), 0.01))
                ),
                "caughtById": None,
            })

    # ── Step 2: Small Fish Earnings ──────────────────────────────────────

    small_fish_total = sum(
        float(i.get("kilos", 0)) * float(i.get("pricePerKg", 0))
        for i in small_items
    )
    total_small_weight = sum(float(i.get("kilos", 0)) for i in small_items)

    # ── Step 3: Big Fish Earnings (per crew attribution) ─────────────────

    big_fish_total = sum(
        float(i.get("kilos", 0)) * float(i.get("pricePerKg", 0))
        for i in big_items
    )

    big_fish_per_crew: dict[str, float] = {}
    for item in big_items:
        cid = str(item.get("caughtById") or "")
        amt = float(item.get("kilos", 0)) * float(item.get("pricePerKg", 0))
        if cid:
            big_fish_per_crew[cid] = big_fish_per_crew.get(cid, 0) + amt

    gross_revenue = small_fish_total + big_fish_total

    # ── Step 4: Broker Share ─────────────────────────────────────────────

    broker_share = round(gross_revenue * broker_pct, 2)

    # ── Step 5: Bangka (Boat) Share ──────────────────────────────────────

    small_bangka = round(small_fish_total * small_bangka_pct, 2)
    big_bangka = round(big_fish_total * big_bangka_pct, 2)
    total_bangka = small_bangka + big_bangka

    # ── Step 6: Crew Pool (Pakura / Tongko) ──────────────────────────────

    small_remaining = small_fish_total - small_bangka
    big_remaining = big_fish_total - big_bangka

    divisor = pakura_divisor if crew_type == "pakura" else tongko_divisor
    if divisor <= 0:
        divisor = 3  # safety fallback

    small_crew_pool = round(small_remaining / divisor, 2)
    big_crew_pool = round(big_remaining / divisor, 2)
    total_crew_pool = small_crew_pool + big_crew_pool

    crew_share_each = round(total_crew_pool / crew_count, 2) if crew_count > 0 else 0

    # ── Step 7: Captain / Owner Net ──────────────────────────────────────

    captain_owner_net = round(
        gross_revenue - broker_share - total_crew_pool - total_expenses, 2
    )

    if captain_owner_split_type == "members_split" and total_members > 0:
        per_member = captain_owner_net / total_members
        captain_share = round(per_member * captain_members_share, 2)
        owner_share = round(captain_owner_net - captain_share, 2)
    else:
        # Fixed percentage fallback (from legacy fields)
        owner_pct = float(policy.get("boatOwnerPercentage", 60)) / 100
        owner_share = round(captain_owner_net * owner_pct, 2)
        captain_share = round(captain_owner_net - owner_share, 2)

    if captain_is_owner:
        owner_share = round(owner_share + captain_share, 2)
        captain_share = 0

    # ── Step 8: Per-crew deductions & final payout ───────────────────────

    net_profit = round(gross_revenue - total_expenses, 2)
    crew_breakdown: list[dict[str, Any]] = []
    fisherman_shares: dict[str, float] = {}

    # Sinakahan logic differs by crew type:
    # - Pakura: flat sinakahan amount per crew (from policy)
    # - Tongko: sinakahan = total pakura crew pool / tongko crew count
    #   (cross-type redistribution — tongko crew receive sinakahan from pakura pool)
    if crew_type == "tongko" and crew_count > 0:
        # For Tongko: sinakahan is derived from what the pakura pool would have been
        pakura_pool = round((small_remaining + big_remaining) / pakura_divisor, 2)
        tongko_sinakahan_each = round(pakura_pool / crew_count, 2)
    else:
        tongko_sinakahan_each = 0.0

    for cid in crew_ids:
        gross = crew_share_each
        ca_deduction = cash_advance_per_crew.get(cid, 0)

        # Sinakahan: depends on crew type
        if crew_type == "pakura":
            sinakahan_deduction = sinakahan_amount if sinakahan_amount > 0 else 0
        else:
            # Tongko: sinakahan = pakura pool / tongko crew count
            sinakahan_deduction = tongko_sinakahan_each

        # Kusinero: flat deduction if configured
        kusinero_deduction = kusinero_amount if kusinero_amount > 0 else 0

        # Custom deductions
        custom_total = sum(float(d.get("amount", 0)) for d in custom_deductions)

        total_deductions = ca_deduction + sinakahan_deduction + kusinero_deduction + custom_total
        net_payout = round(gross - total_deductions, 2)

        fisherman_shares[cid] = net_payout
        crew_breakdown.append({
            "crewId": cid,
            "crewName": crew_name_map.get(cid, ""),
            "grossShare": gross,
            "smallFishEarnings": round(crew_share_each * (small_crew_pool / total_crew_pool) if total_crew_pool > 0 else 0, 2),
            "bigFishEarnings": big_fish_per_crew.get(cid, 0),
            "bigFishDirectAttribution": round(big_fish_per_crew.get(cid, 0), 2),
            "cashAdvanceDeduction": ca_deduction,
            "sinakahan": sinakahan_deduction,
            "kusinero": kusinero_deduction,
            "customDeductions": custom_total,
            "totalDeductions": total_deductions,
            "netPayout": net_payout,
        })

    # ── Step 9: Nilicoman (optional redistribution) ──────────────────────

    nilicoman_total = 0.0
    nilicoman_owner = 0.0
    nilicoman_crew_each = 0.0
    if nilicoman_enabled and captain_owner_net > 0:
        # Nilicoman is typically a portion of the captain/owner residual
        # redistributed: owner gets nilicomanOwnerPct, rest split among crew
        nilicoman_total = captain_owner_net  # base for redistribution
        nilicoman_owner = round(nilicoman_total * nilicoman_owner_pct, 2)
        nilicoman_crew_total = nilicoman_total - nilicoman_owner
        nilicoman_crew_each = round(nilicoman_crew_total / crew_count, 2) if crew_count > 0 else 0

        # Apply to crew payouts
        for entry in crew_breakdown:
            entry["nilicoman"] = nilicoman_crew_each
            entry["netPayout"] = round(entry["netPayout"] + nilicoman_crew_each, 2)
            fisherman_shares[entry["crewId"]] = entry["netPayout"]

        # Add nilicoman to owner share
        owner_share = round(owner_share + nilicoman_owner, 2)

    # ── Build result ─────────────────────────────────────────────────────

    policy_id_str = str(policy.get("_id", "")) if policy.get("_id") else None

    return {
        "tripId": trip_id,
        "crewType": crew_type,
        "grossRevenue": gross_revenue,
        "smallFishTotal": small_fish_total,
        "bigFishTotal": big_fish_total,
        "totalSmallWeight": total_small_weight,
        "brokerShare": broker_share,
        "brokerPercentage": round(broker_pct * 100, 2),
        "bangkaShare": total_bangka,
        "smallBangka": small_bangka,
        "bigBangka": big_bangka,
        "smallBangkaPercentage": round(small_bangka_pct * 100, 2),
        "bigBangkaPercentage": round(big_bangka_pct * 100, 2),
        "crewPool": total_crew_pool,
        "smallCrewPool": small_crew_pool,
        "bigCrewPool": big_crew_pool,
        "divisor": divisor,
        "captainOwnerNet": captain_owner_net,
        "captainShare": captain_share,
        "ownerShare": owner_share,
        "captainId": str(captain_id) if captain_id else None,
        "captainIsOwner": captain_is_owner,
        "totalExpenses": total_expenses,
        "totalCashAdvances": total_cash_advances,
        "sinakahan": sinakahan_amount,
        "kusineroAmount": kusinero_amount,
        "nilicomanEnabled": nilicoman_enabled,
        "nilicomanTotal": nilicoman_total,
        "nilicomanOwner": nilicoman_owner,
        "nilicomanCrewEach": nilicoman_crew_each,
        "netProfit": net_profit,
        "totalRevenue": gross_revenue,
        "fishermanShares": fisherman_shares,
        "crewBreakdown": crew_breakdown,
        "crewCount": crew_count,
        "boatOwnerPercentage": round(float(policy.get("boatOwnerPercentage", 0)), 2),
        "fishermanPercentage": round(float(policy.get("fishermanPercentage", 0)), 2),
        "policyId": policy_id_str,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _resolve_policy(
    db: Any, trip: dict, policy_id: str | None
) -> dict[str, Any]:
    """Find the profit-sharing policy for a trip.

    Resolution order:
    1. Explicit ``policy_id``
    2. Active policy matching the trip's vessel owner
    3. Empty dict (all defaults)
    """
    if policy_id:
        doc = await db["profit_sharing_policies"].find_one(
            {"_id": to_object_id(policy_id)}
        )
        if doc:
            return doc

    # Resolve vessel owner from the trip's vessel
    vessel_id = trip.get("vesselId")
    owner_id: str | None = None
    if vessel_id:
        vessel = await db["vessels"].find_one({"_id": to_object_id(str(vessel_id))})
        if vessel:
            owner_id = str(vessel.get("vesselOwnerId") or vessel.get("ownerId") or "")

    if not owner_id:
        owner_id = str(trip.get("brokerId") or "")

    if owner_id:
        doc = await db["profit_sharing_policies"].find_one({
            "boatOwnerId": owner_id,
            "isActive": True,
        })
        if doc:
            return doc
        # Try with ObjectId
        try:
            doc = await db["profit_sharing_policies"].find_one({
                "boatOwnerId": to_object_id(owner_id),
                "isActive": True,
            })
            if doc:
                return doc
        except Exception:
            pass

    # Return empty dict so all policy fields fall back to defaults
    return {}
