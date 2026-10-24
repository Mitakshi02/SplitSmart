"""
SplitSmart Common Trip Fund (Pooled Kitty) Service
Handles contributions, kitty balance tracking, member equity stake deductions,
and deficit / low balance detection.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Any, Optional, Union

from db import get_db_connection, get_db_cursor, execute_query, execute_write
from services.balance_engine import calculate_pool_equity, to_decimal
from services.expense_service import resolve_member_id

CENT = Decimal('0.01')


def record_contribution(
    group_id: int,
    member_id: int,
    amount: Union[Decimal, str, float],
    payment_method: str = "Cash",
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """
    Records an upfront cash/UPI contribution by a member into the group's common kitty.
    
    Args:
        group_id: Group ID
        member_id: group_member.id or user_id
        amount: Decimal amount deposited
        payment_method: 'Cash', 'UPI', 'Bank Transfer', etc.
        notes: Optional note
        
    Returns:
        Dict with contribution record details.
    """
    deposit_amount = to_decimal(amount).quantize(CENT, rounding=ROUND_HALF_UP)
    if deposit_amount <= Decimal('0.00'):
        raise ValueError("Contribution amount must be greater than 0.00.")

    # 1. Verify group exists and is in pooled kitty / common fund mode
    group = execute_query(
        "SELECT id, name, funding_mode, currency FROM `groups` WHERE id = %s",
        (group_id,),
        fetchone=True
    )
    if not group:
        raise ValueError(f"Group with ID {group_id} not found.")

    funding_mode = str(group.get("funding_mode", "")).strip().lower()
    if funding_mode not in ("pooled_kitty", "common_fund", "common trip fund"):
        raise ValueError("Cannot record contribution: Group is not configured for Common Fund / Pooled Kitty.")

    # 2. Resolve member ID and validate not a dependent
    resolved_mid = resolve_member_id(group_id, member_id)
    member = execute_query(
        "SELECT id, display_name, sponsor_id, role FROM group_members WHERE id = %s AND group_id = %s",
        (resolved_mid, group_id),
        fetchone=True
    )
    if not member:
        raise ValueError(f"Member with ID {resolved_mid} not found in group {group_id}.")

    if member.get("sponsor_id") is not None or str(member.get("role", "")).upper() == "CHILD":
        raise ValueError("Dependents cannot contribute directly to the Kitty. The contribution must be recorded by their sponsor.")

    # 3. Insert record into fund_contributions
    clean_notes = (notes or "").strip() or None
    clean_method = (payment_method or "Cash").strip()

    insert_sql = """
        INSERT INTO fund_contributions (group_id, member_id, amount, payment_method, notes)
        VALUES (%s, %s, %s, %s, %s)
    """
    with get_db_cursor() as (cur, _):
        cur.execute(insert_sql, (group_id, resolved_mid, deposit_amount, clean_method, clean_notes))
        contrib_id = cur.lastrowid

    display_name = member["display_name"] if member else "Member"

    return {
        "id": contrib_id,
        "group_id": group_id,
        "member_id": resolved_mid,
        "display_name": display_name,
        "amount": deposit_amount,
        "payment_method": clean_method,
        "notes": clean_notes
    }


def get_group_contributions(group_id: int) -> List[Dict[str, Any]]:
    """
    Returns all contributions made to the group kitty, ordered chronologically.
    """
    query = """
        SELECT 
            fc.id,
            fc.group_id,
            fc.member_id,
            gm.display_name,
            fc.amount,
            fc.payment_method,
            fc.notes,
            fc.contributed_at
        FROM fund_contributions fc
        JOIN group_members gm ON fc.member_id = gm.id
        WHERE fc.group_id = %s
        ORDER BY fc.contributed_at DESC, fc.id DESC
    """
    return execute_query(query, (group_id,)) or []


def get_group_fund_status(group_id: int) -> Dict[str, Any]:
    """
    Computes total collected pool funds, total spent from pool, remaining kitty balance,
    and individual remaining equity per member. Also flags any deficit / negative equity.
    
    Returns:
        Dict with:
            - 'group_id': int
            - 'total_contributed': Decimal
            - 'total_spent': Decimal
            - 'kitty_balance': Decimal
            - 'member_equity': Dict[member_id, Decimal]
            - 'members_equity_breakdown': List[Dict] with detailed member stats
            - 'has_deficit': bool
            - 'deficits': Dict[member_id, Decimal]
            - 'contributions': List of contribution records
    """
    # 1. Fetch group info
    group = execute_query(
        "SELECT id, name, funding_mode, currency FROM `groups` WHERE id = %s",
        (group_id,),
        fetchone=True
    )
    if not group:
        raise ValueError(f"Group with ID {group_id} not found.")

    # 2. Fetch all contributions
    contributions = execute_query(
        "SELECT member_id, amount FROM fund_contributions WHERE group_id = %s",
        (group_id,)
    ) or []

    # 3. Fetch all expenses paid from the kitty pool
    # Each split of a kitty expense represents that member's consumption from the kitty
    pool_splits_query = """
        SELECT es.member_id, es.owed_amount AS amount
        FROM expense_splits es
        JOIN expenses e ON es.expense_id = e.id
        WHERE e.group_id = %s AND e.funding_source = 'kitty'
    """
    pool_expenses_by_member = execute_query(pool_splits_query, (group_id,)) or []

    # 4. Fetch all group members with sponsor and role info
    members = execute_query(
        """
        SELECT 
            gm.id, 
            gm.display_name, 
            gm.sponsor_id, 
            gm.role,
            CASE WHEN gm.sponsor_id IS NOT NULL OR gm.role = 'CHILD' THEN 'CHILD' ELSE 'ADULT' END AS member_type
        FROM group_members gm
        WHERE gm.group_id = %s
        ORDER BY gm.id ASC
        """,
        (group_id,)
    ) or []

    sponsor_map = {m["id"]: m.get("sponsor_id") for m in members}
    def find_root_sponsor(mid: int) -> int:
        curr = mid
        visited = set()
        while curr in sponsor_map and sponsor_map[curr] and curr not in visited:
            visited.add(curr)
            curr = sponsor_map[curr]
        return curr

    # Pre-aggregate contributions and consumption per member for reporting
    contrib_sums: Dict[int, Decimal] = {}
    for c in contributions:
        mid = c["member_id"]
        contrib_sums[mid] = contrib_sums.get(mid, Decimal('0.00')) + to_decimal(c["amount"])

    consumed_sums: Dict[int, Decimal] = {}
    for e in pool_expenses_by_member:
        mid = e["member_id"]
        consumed_sums[mid] = consumed_sums.get(mid, Decimal('0.00')) + to_decimal(e["amount"])

    total_contributed = sum(contrib_sums.values(), Decimal('0.00')).quantize(CENT, rounding=ROUND_HALF_UP)
    total_spent = sum(consumed_sums.values(), Decimal('0.00')).quantize(CENT, rounding=ROUND_HALF_UP)
    kitty_balance = (total_contributed - total_spent).quantize(CENT, rounding=ROUND_HALF_UP)

    # Roll up dependent consumption into designated root sponsor
    sponsor_dependents_consumed: Dict[int, Decimal] = {}
    for m in members:
        mid = m["id"]
        is_dependent = (
            str(m.get("member_type", "")).upper() == "CHILD" or 
            m.get("sponsor_id") is not None or 
            str(m.get("role", "")).upper() == "CHILD"
        )
        if is_dependent:
            root_sponsor = find_root_sponsor(mid)
            if root_sponsor and root_sponsor != mid:
                dep_c = consumed_sums.get(mid, Decimal('0.00'))
                sponsor_dependents_consumed[root_sponsor] = sponsor_dependents_consumed.get(root_sponsor, Decimal('0.00')) + dep_c

    members_breakdown = []
    deficits: Dict[int, Decimal] = {}
    member_equity_map: Dict[int, Decimal] = {}

    for m in members:
        mid = m["id"]
        is_dependent = (
            str(m.get("member_type", "")).upper() == "CHILD" or 
            m.get("sponsor_id") is not None or 
            str(m.get("role", "")).upper() == "CHILD"
        )

        if is_dependent:
            # Exclude dependent members from rendering as independent rows in the equity table.
            # No dependent shows a separate "Deficit!" badge.
            member_equity_map[mid] = Decimal('0.00')
            continue

        m_contrib = contrib_sums.get(mid, Decimal('0.00')).quantize(CENT, rounding=ROUND_HALF_UP)
        personal_consumed = consumed_sums.get(mid, Decimal('0.00')).quantize(CENT, rounding=ROUND_HALF_UP)
        dep_consumed = sponsor_dependents_consumed.get(mid, Decimal('0.00')).quantize(CENT, rounding=ROUND_HALF_UP)

        # Sponsor Consumed = Sponsor Personal Consumed + SUM(Dependents Consumed)
        m_consumed = (personal_consumed + dep_consumed).quantize(CENT, rounding=ROUND_HALF_UP)
        
        # Sponsor Remaining Equity = Sponsor Deposited - Sponsor Consumed
        m_equity = (m_contrib - m_consumed).quantize(CENT, rounding=ROUND_HALF_UP)

        member_equity_map[mid] = m_equity

        is_deficit = m_equity < Decimal('0.00')
        if is_deficit:
            deficits[mid] = m_equity

        members_breakdown.append({
            "member_id": mid,
            "display_name": m["display_name"],
            "sponsor_id": None,
            "contributed": m_contrib,
            "consumed": m_consumed,
            "personal_consumed": personal_consumed,
            "dependents_consumed": dep_consumed,
            "remaining_equity": m_equity,
            "is_deficit": is_deficit
        })

    has_deficit = len(deficits) > 0 or kitty_balance < Decimal('0.00')

    # Fetch recent contributions list for UI display
    contributions_list = get_group_contributions(group_id)

    return {
        "group_id": group_id,
        "currency": group.get("currency", "INR"),
        "total_contributed": total_contributed,
        "total_spent": total_spent,
        "kitty_balance": kitty_balance,
        "member_equity": member_equity_map,
        "members_equity_breakdown": members_breakdown,
        "has_deficit": has_deficit,
        "deficits": deficits,
        "contributions": contributions_list
    }


def disband_and_refund_kitty(group_id: int, user_id: int) -> Dict[str, Any]:
    """
    Disbands the Common Kitty Pool and refunds remaining equity stakes to members:
    1. Verifies user is group creator or admin.
    2. Retrieves current fund equity breakdown (with dependent rollups applied).
    3. If kitty_balance <= 0 and all member equities == 0, returns immediately.
    4. For each member (or sponsor) with remaining_equity > 0:
       - Generates settlement payout step to refund remaining equity (e.g., Mitakshi: INR 900, Ramesh: INR 600).
       - Records a refund settlement in `settlements` table.
       - Records balancing refund entry in `fund_contributions` so member's net contributions
         equal their consumed, resulting in remaining_equity = 0.00.
    5. If any member has a deficit (remaining_equity < 0), offsets it with a deficit settlement.
    6. Ensures kitty_balance and all member remaining equities reach 0.00.
    7. Returns settlement payout steps and updated fund status.
    """
    group = execute_query("SELECT id, created_by, currency FROM `groups` WHERE id = %s", (group_id,), fetchone=True)
    if not group:
        raise ValueError(f"Group with ID {group_id} not found.")

    is_creator = int(group.get("created_by") or 0) == int(user_id)
    if not is_creator:
        admin_check = execute_query(
            "SELECT id FROM group_members WHERE group_id = %s AND user_id = %s AND role = 'admin'",
            (group_id, user_id),
            fetchone=True
        )
        if not admin_check:
            raise PermissionError("Unauthorized: Only the group creator or admin can disband the kitty.")

    fund_status = get_group_fund_status(group_id)
    kitty_balance = to_decimal(fund_status.get("kitty_balance", Decimal('0.00')))
    members_breakdown = fund_status.get("members_equity_breakdown", [])
    currency = group.get("currency", "INR")

    has_active_equity = (
        abs(kitty_balance) >= Decimal('0.01') or 
        any(abs(to_decimal(m["remaining_equity"])) >= Decimal('0.01') for m in members_breakdown)
    )

    if not has_active_equity:
        return {
            "success": True,
            "message": "Kitty is already settled and balance is 0.00.",
            "payout_steps": [],
            "kitty_balance": 0.0,
            "fund_status": fund_status
        }

    admin_member = execute_query(
        "SELECT id FROM group_members WHERE group_id = %s AND user_id = %s",
        (group_id, user_id),
        fetchone=True
    ) or execute_query(
        "SELECT id FROM group_members WHERE group_id = %s ORDER BY id ASC LIMIT 1",
        (group_id,),
        fetchone=True
    )
    treasurer_mid = admin_member["id"] if admin_member else None

    payout_steps = []

    with get_db_cursor() as (cur, conn):
        for m in members_breakdown:
            mid = m["member_id"]
            equity = to_decimal(m["remaining_equity"]).quantize(CENT, rounding=ROUND_HALF_UP)
            d_name = m["display_name"]

            if equity > Decimal('0.00'):
                # Refund remaining equity to sponsor/independent member
                payout_steps.append({
                    "member_id": mid,
                    "display_name": d_name,
                    "amount": float(equity),
                    "action": "REFUND",
                    "description": f"Refund {currency} {equity:.2f} to {d_name}"
                })
                payer = treasurer_mid or mid
                cur.execute(
                    """
                    INSERT INTO settlements (group_id, payer_member_id, payee_member_id, amount, payment_method, payment_reference, notes, status)
                    VALUES (%s, %s, %s, %s, 'Kitty Refund', 'KITTY_DISBAND', %s, 'completed')
                    """,
                    (group_id, payer, mid, equity, f"Kitty Disband Refund of {currency} {equity:.2f} to {d_name}")
                )
                cur.execute(
                    """
                    INSERT INTO fund_contributions (group_id, member_id, amount, payment_method, notes)
                    VALUES (%s, %s, %s, 'Kitty Refund', %s)
                    """,
                    (group_id, mid, -equity, f"Kitty Disband Refund to {d_name}")
                )
            elif equity < Decimal('0.00'):
                # Settle deficit
                deficit_amt = abs(equity)
                payout_steps.append({
                    "member_id": mid,
                    "display_name": d_name,
                    "amount": float(deficit_amt),
                    "action": "DEFICIT_SETTLE",
                    "description": f"Settle deficit of {currency} {deficit_amt:.2f} by {d_name}"
                })
                payer = mid
                payee = treasurer_mid or mid
                cur.execute(
                    """
                    INSERT INTO settlements (group_id, payer_member_id, payee_member_id, amount, payment_method, payment_reference, notes, status)
                    VALUES (%s, %s, %s, %s, 'Kitty Deficit Settle', 'KITTY_DISBAND', %s, 'completed')
                    """,
                    (group_id, payer, payee, deficit_amt, f"Kitty Deficit Settlement of {currency} {deficit_amt:.2f} from {d_name}")
                )
                cur.execute(
                    """
                    INSERT INTO fund_contributions (group_id, member_id, amount, payment_method, notes)
                    VALUES (%s, %s, %s, 'Kitty Deficit Settle', %s)
                    """,
                    (group_id, mid, deficit_amt, f"Kitty Deficit Settlement by {d_name}")
                )
        conn.commit()

    updated_status = get_group_fund_status(group_id)
    return {
        "success": True,
        "message": "Kitty disbanded and all equity refunded successfully.",
        "payout_steps": payout_steps,
        "kitty_balance": float(updated_status["kitty_balance"]),
        "fund_status": updated_status
    }


def calculate_prorated_kitty_refunds(group_id: int):
    from services.group_service import calculate_prorated_kitty_refunds as _calc
    return _calc(group_id)

