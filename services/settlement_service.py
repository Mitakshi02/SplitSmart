"""
SplitSmart Settlement & Live Balance Service
Calculates raw member balances, rolls dependent debts onto sponsors,
simplifies peer-to-peer debts into minimum direct repayments, and logs settlements.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Any, Optional, Union

from db import get_db_connection, get_db_cursor, execute_query, execute_write
from services.balance_engine import (
    calculate_raw_group_balances,
    rollup_sponsor_balances,
    to_decimal
)
from services.debt_simplifier import simplify_debts
from services.expense_service import resolve_member_id

CENT = Decimal('0.01')


def record_settlement(
    group_id: int,
    payer_id: int,
    payee_id: int,
    amount: Union[Decimal, str, float],
    payment_method: str = "Cash",
    payment_reference: Optional[str] = None,
    notes: Optional[str] = None,
    reference_note: Optional[str] = None
) -> Dict[str, Any]:
    """
    Records a direct peer-to-peer repayment between two group members.
    
    Args:
        group_id: Group ID
        payer_id: member_id (or user_id) of the person sending money
        payee_id: member_id (or user_id) of the person receiving money
        amount: Repayment amount (Decimal)
        payment_method: 'CASH', 'UPI', 'BANK_TRANSFER', 'Cash', etc.
        payment_reference: Reference number or transaction ID
        notes: Optional note
        reference_note: Alternative parameter name for reference / note
    """
    repay_amount = to_decimal(amount).quantize(CENT, rounding=ROUND_HALF_UP)
    if repay_amount <= Decimal('0.00'):
        raise ValueError("Settlement amount must be greater than 0.00.")

    # 1. Verify group exists
    group = execute_query(
        "SELECT id, currency FROM `groups` WHERE id = %s",
        (group_id,),
        fetchone=True
    )
    if not group:
        raise ValueError(f"Group with ID {group_id} not found.")

    # 2. Resolve payer and payee member IDs
    resolved_payer_id = resolve_member_id(group_id, payer_id)
    resolved_payee_id = resolve_member_id(group_id, payee_id)

    if resolved_payer_id == resolved_payee_id:
        raise ValueError("Payer and payee cannot be the same member.")

    clean_method = (payment_method or "Cash").strip()
    clean_ref = (payment_reference or reference_note or "").strip() or None
    clean_notes = (notes or "").strip() or None

    insert_sql = """
        INSERT INTO settlements (
            group_id, payer_member_id, payee_member_id, amount,
            payment_method, payment_reference, notes, status
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'completed')
    """
    with get_db_cursor() as (cur, _):
        cur.execute(
            insert_sql,
            (group_id, resolved_payer_id, resolved_payee_id, repay_amount,
             clean_method, clean_ref, clean_notes)
        )
        settlement_id = cur.lastrowid

    # Fetch display names for response
    payer_info = execute_query("SELECT display_name FROM group_members WHERE id = %s", (resolved_payer_id,), fetchone=True)
    payee_info = execute_query("SELECT display_name FROM group_members WHERE id = %s", (resolved_payee_id,), fetchone=True)

    payer_name = payer_info["display_name"] if payer_info else "Payer"
    payee_name = payee_info["display_name"] if payee_info else "Payee"

    return {
        "id": settlement_id,
        "group_id": group_id,
        "payer_id": resolved_payer_id,
        "payer_name": payer_name,
        "payee_id": resolved_payee_id,
        "payee_name": payee_name,
        "amount": repay_amount,
        "payment_method": clean_method,
        "payment_reference": clean_ref,
        "notes": clean_notes,
        "status": "completed"
    }


def get_group_settlements(group_id: int) -> List[Dict[str, Any]]:
    """
    Retrieves all recorded settlements for a group with payer and payee details.
    """
    query = """
        SELECT 
            s.id,
            s.group_id,
            s.payer_member_id,
            p1.display_name AS payer_name,
            s.payee_member_id,
            p2.display_name AS payee_name,
            s.amount,
            s.payment_method,
            s.payment_reference,
            s.notes,
            s.status,
            s.settled_at
        FROM settlements s
        JOIN group_members p1 ON s.payer_member_id = p1.id
        JOIN group_members p2 ON s.payee_member_id = p2.id
        WHERE s.group_id = %s
        ORDER BY s.settled_at DESC, s.id DESC
    """
    return execute_query(query, (group_id,)) or []


def get_group_balances(group_id: int) -> Dict[str, Any]:
    """
    Retrieves all active expenses, payers, splits, and settlements for the group.
    Applies child-to-parent debt rollups and passes effective balances to the debt simplifier.
    
    Returns:
        Dict containing:
            1. 'consumption_breakdown': Dict[member_id, Decimal] of total consumed per member
            2. 'effective_balances': Dict[member_id, Decimal] for responsible adult members (+ owed, - owes)
            3. 'settlement_plan': List of simplified repayment instructions
            4. 'raw_balances': Dict[member_id, Decimal] before sponsor rollups
            5. 'member_details': Dict of member metadata (display_name, sponsor_id)
    """
    # 1. Fetch group members
    members = execute_query(
        "SELECT id, display_name, sponsor_id, role, status FROM group_members WHERE group_id = %s ORDER BY id ASC",
        (group_id,)
    ) or []

    if not members:
        return {
            "consumption_breakdown": {},
            "effective_balances": {},
            "settlement_plan": [],
            "raw_balances": {},
            "member_details": {}
        }

    member_map = {m["id"]: m for m in members}
    name_map = {m["id"]: m["display_name"] for m in members}
    sponsor_map = {m["id"]: m.get("sponsor_id") for m in members}

    # 2. Fetch payers for peer-to-peer (out-of-pocket) expenses
    payers_query = """
        SELECT ep.member_id, ep.amount_paid
        FROM expense_payers ep
        JOIN expenses e ON ep.expense_id = e.id
        WHERE e.group_id = %s
    """
    payers = execute_query(payers_query, (group_id,)) or []

    # 3. Fetch splits for peer-to-peer expenses
    # Pool/kitty expenses are settled from the pool and tracked via pool equity,
    # so only 'individual' funding source expenses generate peer-to-peer debt.
    splits_query = """
        SELECT es.member_id, es.owed_amount
        FROM expense_splits es
        JOIN expenses e ON es.expense_id = e.id
        WHERE e.group_id = %s AND e.funding_source = 'individual'
    """
    splits = execute_query(splits_query, (group_id,)) or []

    # 4. Fetch completed peer-to-peer settlements
    # Kitty refunds settle pool equity and should not distort peer-to-peer debt balances
    settlements_query = """
        SELECT payer_member_id, payee_member_id, amount, status
        FROM settlements
        WHERE group_id = %s AND status = 'completed'
          AND (payment_reference IS NULL OR payment_reference != 'KITTY_DISBAND')
          AND (payment_method IS NULL OR payment_method != 'Kitty Refund')
    """
    settlements = execute_query(settlements_query, (group_id,)) or []

    # 5. Compute raw balances via balance engine
    raw_balances = calculate_raw_group_balances(payers, splits, settlements)

    # Ensure every group member exists in raw_balances
    for m in members:
        mid = m["id"]
        if mid not in raw_balances:
            raw_balances[mid] = Decimal('0.00')

    # 6. Apply child-to-parent debt rollup
    rolled_balances = rollup_sponsor_balances(raw_balances, sponsor_map)

    # 7. Isolate effective balances for legally responsible members (sponsor_id IS NULL)
    effective_balances: Dict[int, Decimal] = {}
    for m in members:
        mid = m["id"]
        if m.get("sponsor_id") is None:
            effective_balances[mid] = rolled_balances.get(mid, Decimal('0.00'))

    # 8. Run greedy debt simplifier on effective balances
    raw_plan = simplify_debts(effective_balances)

    settlement_plan = []
    for step in raw_plan:
        from_id = step["from_member"]
        to_id = step["to_member"]
        amt = step["amount"]
        from_name = name_map.get(from_id, f"Member {from_id}")
        to_name = name_map.get(to_id, f"Member {to_id}")
        settlement_plan.append({
            "from_member_id": from_id,
            "to_member_id": to_id,
            "from_name": from_name,
            "to_name": to_name,
            "amount": amt,
            "instruction": f"{from_name} pays {to_name} ₹{amt:,.2f}"
        })

    # 9. Compute consumption breakdown across all group expenses (both individual & pool)
    consumption_query = """
        SELECT es.member_id, COALESCE(SUM(es.owed_amount), 0.00) AS total_consumed
        FROM expense_splits es
        JOIN expenses e ON es.expense_id = e.id
        WHERE e.group_id = %s
        GROUP BY es.member_id
    """
    consumption_rows = execute_query(consumption_query, (group_id,)) or []
    consumption_map: Dict[int, Decimal] = {}
    for r in consumption_rows:
        mid = r["member_id"]
        consumption_map[mid] = to_decimal(r["total_consumed"]).quantize(CENT, rounding=ROUND_HALF_UP)

    # Ensure all members have consumption entry
    for m in members:
        mid = m["id"]
        if mid not in consumption_map:
            consumption_map[mid] = Decimal('0.00')

    return {
        "consumption_breakdown": consumption_map,
        "effective_balances": effective_balances,
        "settlement_plan": settlement_plan,
        "raw_balances": raw_balances,
        "rolled_balances": rolled_balances,
        "member_details": name_map
    }
