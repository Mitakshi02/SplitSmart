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

    # 2. Resolve member ID
    resolved_mid = resolve_member_id(group_id, member_id)

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

    # Fetch display name
    member = execute_query(
        "SELECT display_name FROM group_members WHERE id = %s",
        (resolved_mid,),
        fetchone=True
    )
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

    # 4. Fetch all group members so everyone is represented in member_equity
    members = execute_query(
        "SELECT id, display_name, sponsor_id FROM group_members WHERE group_id = %s ORDER BY id ASC",
        (group_id,)
    ) or []

    # 5. Run calculation through pure balance engine
    raw_equity_result = calculate_pool_equity(contributions, pool_expenses_by_member)

    total_contributed = raw_equity_result["total_contributed"]
    total_spent = raw_equity_result["total_spent"]
    kitty_balance = raw_equity_result["kitty_balance"]
    member_equity_map = raw_equity_result["member_equity"]

    # 6. Build detailed members breakdown
    members_breakdown = []
    deficits: Dict[int, Decimal] = {}

    # Pre-aggregate contributions and consumption per member for reporting
    contrib_sums: Dict[int, Decimal] = {}
    for c in contributions:
        mid = c["member_id"]
        contrib_sums[mid] = contrib_sums.get(mid, Decimal('0.00')) + to_decimal(c["amount"])

    consumed_sums: Dict[int, Decimal] = {}
    for e in pool_expenses_by_member:
        mid = e["member_id"]
        consumed_sums[mid] = consumed_sums.get(mid, Decimal('0.00')) + to_decimal(e["amount"])

    for m in members:
        mid = m["id"]
        m_contrib = contrib_sums.get(mid, Decimal('0.00')).quantize(CENT, rounding=ROUND_HALF_UP)
        m_consumed = consumed_sums.get(mid, Decimal('0.00')).quantize(CENT, rounding=ROUND_HALF_UP)
        m_equity = member_equity_map.get(mid, m_contrib - m_consumed).quantize(CENT, rounding=ROUND_HALF_UP)

        # Make sure member_equity_map contains this member
        member_equity_map[mid] = m_equity

        is_deficit = m_equity < Decimal('0.00')
        if is_deficit:
            deficits[mid] = m_equity

        members_breakdown.append({
            "member_id": mid,
            "display_name": m["display_name"],
            "sponsor_id": m.get("sponsor_id"),
            "contributed": m_contrib,
            "consumed": m_consumed,
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
