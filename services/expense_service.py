"""
SplitSmart Expense Ledger & Multi-Payer Split Service
Handles transactional CRUD for expenses, supporting EQUAL, EXACT, PERCENTAGE,
SHARES, and ITEMIZED split modes, multi-payer splits, and Pooled Kitty funding.
"""

from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from typing import List, Dict, Any, Optional, Union

from db import get_db_connection, get_db_cursor, execute_query, execute_write
from services.receipt_math import calculate_itemized_receipt_split

CENT = Decimal('0.01')


def to_decimal(val: Union[str, int, float, Decimal, None]) -> Decimal:
    """Helper to convert any numerical value to Decimal safely."""
    if val is None:
        return Decimal('0.00')
    if isinstance(val, Decimal):
        return val
    return Decimal(str(val))


def resolve_member_id(group_id: int, identifier: int) -> int:
    """
    Ensures identifier is a valid group_member.id for the given group.
    If a user_id was passed, maps it to the member_id.
    """
    query = "SELECT id FROM group_members WHERE id = %s AND group_id = %s"
    member = execute_query(query, (identifier, group_id), fetchone=True)
    if member:
        return member["id"]

    # Try matching by user_id
    query_user = "SELECT id FROM group_members WHERE user_id = %s AND group_id = %s"
    member_by_user = execute_query(query_user, (identifier, group_id), fetchone=True)
    if member_by_user:
        return member_by_user["id"]

    raise ValueError(f"Member ID {identifier} not found in group {group_id}.")


def create_expense(
    group_id: int,
    created_by: int,
    description: str,
    amount: Union[Decimal, str, float],
    split_type: str = "EQUAL",
    payers: Optional[List[Dict[str, Any]]] = None,
    splits: Optional[List[Dict[str, Any]]] = None,
    receipt_items: Optional[List[Dict[str, Any]]] = None,
    paid_from_pool: bool = False,
    tax: Union[Decimal, str, float] = Decimal('0.00'),
    tip: Union[Decimal, str, float] = Decimal('0.00'),
    discount: Union[Decimal, str, float] = Decimal('0.00'),
    category: str = "General",
    expense_date: Optional[Union[date, str]] = None,
    currency: str = "INR"
) -> Dict[str, Any]:
    """
    Creates an expense atomically within a MySQL transaction.
    
    Args:
        group_id: Group ID
        created_by: group_member.id (or user_id) creating the expense
        description: Title or description of the expense
        amount: Total expense amount (Decimal)
        split_type: 'EQUAL', 'EXACT', 'PERCENTAGE', 'SHARES', 'ITEMIZED'
        payers: List of dicts: [{'member_id': int, 'amount_paid': Decimal}]
        splits: List of dicts: [{'member_id': int, 'owed_amount' or 'share_value': Decimal}]
        receipt_items: Optional line items for ITEMIZED split
        paid_from_pool: If True, funded by common kitty pool (no individual payers)
        tax, tip, discount: Adjustments for itemized bill calculations
        category: Expense category ('General', 'Food', 'Travel', etc.)
        expense_date: Optional date of expense (defaults to today)
        currency: 3-letter currency code (e.g. 'INR')
    """
    total_amount = to_decimal(amount).quantize(CENT, rounding=ROUND_HALF_UP)
    if total_amount <= Decimal('0.00'):
        raise ValueError("Expense amount must be greater than 0.00.")

    clean_description = (description or "").strip()
    if not clean_description:
        raise ValueError("Expense description/title is required.")

    norm_split_type = split_type.strip().lower()
    valid_splits = ("equal", "exact", "percentage", "shares", "itemized")
    if norm_split_type not in valid_splits:
        raise ValueError(f"Invalid split_type '{split_type}'. Must be one of: {valid_splits}")

    if expense_date is None:
        expense_date = date.today()
    elif isinstance(expense_date, str):
        expense_date = date.fromisoformat(expense_date.strip())

    creator_member_id = resolve_member_id(group_id, created_by)

    # 1. Fetch group details to check funding mode
    group = execute_query("SELECT id, funding_mode, currency FROM `groups` WHERE id = %s", (group_id,), fetchone=True)
    if not group:
        raise ValueError(f"Group with ID {group_id} not found.")

    funding_source = "individual"
    if paid_from_pool:
        fund_mode = str(group.get("funding_mode", "")).strip().lower()
        if fund_mode not in ("pooled_kitty", "common_fund", "common trip fund"):
            raise ValueError("Cannot pay from pool: Group is not configured for Common Fund / Pooled Kitty.")
        funding_source = "kitty"

    # 2. Validate Payers (if not paid from pool)
    validated_payers: List[Dict[str, Any]] = []
    if not paid_from_pool:
        if not payers:
            raise ValueError("At least one payer must be provided for out-of-pocket expenses.")

        payers_sum = Decimal('0.00')
        for p in payers:
            mid = resolve_member_id(group_id, p["member_id"])
            paid_val = to_decimal(p.get("amount_paid", p.get("amount", 0))).quantize(CENT, rounding=ROUND_HALF_UP)
            if paid_val < Decimal('0.00'):
                raise ValueError(f"Payer amount cannot be negative for member {mid}.")
            if paid_val > Decimal('0.00'):
                validated_payers.append({"member_id": mid, "amount_paid": paid_val})
                payers_sum += paid_val

        if payers_sum != total_amount:
            raise ValueError(f"Total paid by payers ({payers_sum}) does not match expense amount ({total_amount}).")

    # 3. Calculate Splits according to split_type
    calculated_splits: List[Dict[str, Any]] = []
    calculated_receipt_items: List[Dict[str, Any]] = []

    if norm_split_type == "equal":
        # Splits input can be list of member_ids or dicts with member_id
        if not splits:
            # Default to all group members
            all_m = execute_query("SELECT id FROM group_members WHERE group_id = %s ORDER BY id ASC", (group_id,)) or []
            participant_ids = [m["id"] for m in all_m]
        else:
            participant_ids = [resolve_member_id(group_id, s.get("member_id", s) if isinstance(s, dict) else s) for s in splits]
        # Remove duplicates while preserving order
        unique_participants = list(dict.fromkeys(participant_ids))

        num_participants = len(unique_participants)
        if num_participants == 0:
            raise ValueError("No valid participants for equal split.")

        base_share = (total_amount / Decimal(num_participants)).quantize(CENT, rounding=ROUND_HALF_UP)
        diff = total_amount - (base_share * Decimal(num_participants))

        for idx, mid in enumerate(unique_participants):
            share = base_share
            if idx == 0:
                share += diff  # Penny reconciliation on first participant
            calculated_splits.append({
                "member_id": mid,
                "owed_amount": share,
                "share_value": Decimal('1.0000')
            })

    elif norm_split_type == "exact":
        if not splits:
            raise ValueError("Splits list cannot be empty for exact split.")
        splits_sum = Decimal('0.00')
        for s in splits:
            mid = resolve_member_id(group_id, s["member_id"])
            owed = to_decimal(s.get("owed_amount", s.get("amount", 0))).quantize(CENT, rounding=ROUND_HALF_UP)
            calculated_splits.append({
                "member_id": mid,
                "owed_amount": owed,
                "share_value": None
            })
            splits_sum += owed

        if splits_sum != total_amount:
            raise ValueError(f"Sum of exact splits ({splits_sum}) does not match expense amount ({total_amount}).")

    elif norm_split_type == "percentage":
        if not splits:
            raise ValueError("Splits list cannot be empty for percentage split.")
        pct_sum = Decimal('0.00')
        for s in splits:
            mid = resolve_member_id(group_id, s["member_id"])
            pct = to_decimal(s.get("share_value", s.get("percentage", 0)))
            owed = (total_amount * (pct / Decimal('100.00'))).quantize(CENT, rounding=ROUND_HALF_UP)
            calculated_splits.append({
                "member_id": mid,
                "owed_amount": owed,
                "share_value": pct.quantize(Decimal('0.0001'))
            })
            pct_sum += pct

        if pct_sum != Decimal('100.00'):
            raise ValueError(f"Sum of split percentages ({pct_sum}%) must equal 100%.")

        # Penny reconciliation on largest percentage holder
        discrepancy = total_amount - sum(s["owed_amount"] for s in calculated_splits)
        if discrepancy != Decimal('0.00'):
            top_holder = max(calculated_splits, key=lambda x: x["share_value"] or Decimal('0'))
            top_holder["owed_amount"] += discrepancy

    elif norm_split_type == "shares":
        if not splits:
            raise ValueError("Splits list cannot be empty for shares split.")
        total_shares = sum(to_decimal(s.get("share_value", s.get("shares", 1))) for s in splits)
        if total_shares <= Decimal('0.00'):
            raise ValueError("Total shares must be greater than zero.")

        for s in splits:
            mid = resolve_member_id(group_id, s["member_id"])
            sh = to_decimal(s.get("share_value", s.get("shares", 1)))
            owed = (total_amount * (sh / total_shares)).quantize(CENT, rounding=ROUND_HALF_UP)
            calculated_splits.append({
                "member_id": mid,
                "owed_amount": owed,
                "share_value": sh.quantize(Decimal('0.0001'))
            })

        # Penny reconciliation on largest share holder
        discrepancy = total_amount - sum(s["owed_amount"] for s in calculated_splits)
        if discrepancy != Decimal('0.00'):
            top_holder = max(calculated_splits, key=lambda x: x["share_value"] or Decimal('0'))
            top_holder["owed_amount"] += discrepancy

    elif norm_split_type == "itemized":
        if not receipt_items:
            raise ValueError("Receipt items must be provided for ITEMIZED split.")

        # Ensure assigned members are valid group_member IDs
        cleaned_items = []
        for item in receipt_items:
            assigned = [resolve_member_id(group_id, m) for m in item.get("assigned_members", [])]
            cleaned_items.append({
                "name": item.get("name", "Item"),
                "price": to_decimal(item["price"]),
                "quantity": to_decimal(item.get("quantity", 1)),
                "assigned_members": assigned
            })

        itemized_result = calculate_itemized_receipt_split(
            items=cleaned_items,
            tax=tax,
            tip=tip,
            discount=discount
        )

        # Derived shares from itemized receipt math
        member_shares = itemized_result["member_final_shares"]
        for mid, owed in member_shares.items():
            calculated_splits.append({
                "member_id": mid,
                "owed_amount": owed,
                "share_value": None
            })

        calculated_receipt_items = cleaned_items

    # 4. Atomic Database Insertion
    with get_db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            # Insert main expense row
            cursor.execute(
                """
                INSERT INTO expenses (
                    group_id, title, description, category, amount, currency,
                    expense_date, split_type, funding_source, created_by_member_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    group_id, clean_description, clean_description, category,
                    total_amount, currency.upper(), expense_date,
                    norm_split_type, funding_source, creator_member_id
                )
            )
            expense_id = cursor.lastrowid

            # Insert expense payers (if not paid from pool)
            for p in validated_payers:
                cursor.execute(
                    """
                    INSERT INTO expense_payers (expense_id, member_id, amount_paid)
                    VALUES (%s, %s, %s)
                    """,
                    (expense_id, p["member_id"], p["amount_paid"])
                )

            # Insert expense splits
            for s in calculated_splits:
                cursor.execute(
                    """
                    INSERT INTO expense_splits (expense_id, member_id, owed_amount, share_value)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (expense_id, s["member_id"], s["owed_amount"], s["share_value"])
                )

            # Insert receipt items & assignments if itemized
            if norm_split_type == "itemized" and calculated_receipt_items:
                for item in calculated_receipt_items:
                    item_total = (item["price"] * item["quantity"]).quantize(CENT, rounding=ROUND_HALF_UP)
                    cursor.execute(
                        """
                        INSERT INTO receipt_items (expense_id, item_name, quantity, unit_price, total_price)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (expense_id, item["name"], item["quantity"], item["price"], item_total)
                    )
                    item_id = cursor.lastrowid

                    num_assigned = len(item["assigned_members"])
                    if num_assigned > 0:
                        fraction = (Decimal('1.0000') / Decimal(num_assigned)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
                        assigned_amt = (item_total / Decimal(num_assigned)).quantize(CENT, rounding=ROUND_HALF_UP)
                        for mid in item["assigned_members"]:
                            cursor.execute(
                                """
                                INSERT INTO receipt_item_assignments (receipt_item_id, member_id, share_fraction, assigned_amount)
                                VALUES (%s, %s, %s, %s)
                                """,
                                (item_id, mid, fraction, assigned_amt)
                            )
        finally:
            cursor.close()

    result = {
        "id": expense_id,
        "group_id": group_id,
        "title": clean_description,
        "amount": total_amount,
        "currency": currency.upper(),
        "split_type": norm_split_type,
        "funding_source": funding_source,
        "payers": validated_payers,
        "splits": calculated_splits,
        "created_by_member_id": creator_member_id
    }

    if paid_from_pool:
        from services.pool_service import get_group_fund_status
        result["fund_status"] = get_group_fund_status(group_id)

    return result



def delete_expense(expense_id: int) -> bool:
    """
    Deletes an expense. Foreign key cascade deletes related payers, splits, and receipt items.
    """
    with get_db_cursor() as (cur, _):
        cur.execute("DELETE FROM expenses WHERE id = %s", (expense_id,))
        return cur.rowcount > 0


def get_expense_details(expense_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieves full details of an expense including payers, splits, and receipt items.
    """
    expense = execute_query("SELECT * FROM expenses WHERE id = %s", (expense_id,), fetchone=True)
    if not expense:
        return None

    payers = execute_query(
        """
        SELECT ep.member_id, ep.amount_paid, gm.display_name
        FROM expense_payers ep
        JOIN group_members gm ON ep.member_id = gm.id
        WHERE ep.expense_id = %s
        """,
        (expense_id,)
    ) or []

    splits = execute_query(
        """
        SELECT es.member_id, es.owed_amount, es.share_value, gm.display_name
        FROM expense_splits es
        JOIN group_members gm ON es.member_id = gm.id
        WHERE es.expense_id = %s
        """,
        (expense_id,)
    ) or []

    receipt_items = execute_query(
        """
        SELECT id, item_name, quantity, unit_price, total_price
        FROM receipt_items
        WHERE expense_id = %s
        """,
        (expense_id,)
    ) or []

    return {
        "expense": expense,
        "payers": payers,
        "splits": splits,
        "receipt_items": receipt_items
    }


def get_group_expenses(group_id: int) -> List[Dict[str, Any]]:
    """
    Retrieves all expenses for a group ordered chronologically with payer and creator details.
    """
    query = """
        SELECT 
            e.*,
            gm.display_name AS creator_name
        FROM expenses e
        JOIN group_members gm ON e.created_by_member_id = gm.id
        WHERE e.group_id = %s
        ORDER BY e.expense_date DESC, e.id DESC
    """
    expenses = execute_query(query, (group_id,)) or []

    # Attach summary of payers and splits to each expense
    for exp in expenses:
        exp_id = exp["id"]
        exp["payers"] = execute_query(
            """
            SELECT ep.member_id, ep.amount_paid, gm.display_name
            FROM expense_payers ep
            JOIN group_members gm ON ep.member_id = gm.id
            WHERE ep.expense_id = %s
            """,
            (exp_id,)
        ) or []

        exp["splits"] = execute_query(
            """
            SELECT es.member_id, es.owed_amount, es.share_value, gm.display_name
            FROM expense_splits es
            JOIN group_members gm ON es.member_id = gm.id
            WHERE es.expense_id = %s
            """,
            (exp_id,)
        ) or []

    return expenses
