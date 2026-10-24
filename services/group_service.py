"""
SplitSmart Group Management & Hybrid Member Onboarding Service
Supports 4 operating modes, 2 funding modes, placeholder guest onboarding,
family unit dependent hierarchies (sponsor_id), and shareable invite code claims.
"""

import string
import secrets
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Dict, Any, List, Union
from db import get_db_cursor, execute_query, execute_write
from services.balance_engine import to_decimal

CENT = Decimal('0.01')

# Mode and funding mode mappings
VALID_MODES = {
    "quick": "quick_split",
    "quick_split": "quick_split",
    "regular": "regular",
    "friends": "friends_trip",
    "friends_trip": "friends_trip",
    "family": "family_trip",
    "family_trip": "family_trip",
}

VALID_FUNDING_MODES = {
    "individual": "individual",
    "pooled_kitty": "pooled_kitty",
    "common_fund": "pooled_kitty",
    "kitty": "pooled_kitty",
}


def normalize_mode(mode: str) -> str:
    """Normalizes input mode string to valid MySQL enum."""
    cleaned = (mode or "regular").strip().lower()
    if cleaned not in VALID_MODES:
        raise ValueError(f"Invalid group mode: '{mode}'. Must be one of: {list(VALID_MODES.keys())}")
    return VALID_MODES[cleaned]


def normalize_funding_mode(funding_mode: str) -> str:
    """Normalizes input funding mode string to valid MySQL enum."""
    cleaned = (funding_mode or "individual").strip().lower()
    if cleaned not in VALID_FUNDING_MODES:
        raise ValueError(f"Invalid funding mode: '{funding_mode}'. Must be one of: {list(VALID_FUNDING_MODES.keys())}")
    return VALID_FUNDING_MODES[cleaned]


def generate_invite_code(length: int = 8) -> str:
    """Generates a secure, unique alphanumeric invite code."""
    alphabet = string.ascii_uppercase + string.digits
    for _ in range(20):
        code = "".join(secrets.choice(alphabet) for _ in range(length))
        # Ensure code doesn't exist
        existing = execute_query("SELECT id FROM `groups` WHERE invite_code = %s", (code,), fetchone=True)
        if not existing:
            return code
    raise RuntimeError("Failed to generate a unique invite code after multiple attempts.")


def create_group(
    creator_user_id: Optional[int] = None,
    name: str = "",
    mode: str = "regular",
    funding_mode: str = "individual",
    description: Optional[str] = None,
    currency: str = "INR",
    created_by: Optional[int] = None,
    category: str = "Other"
) -> Dict[str, Any]:
    """
    Creates a new group and automatically adds the creator as the first admin member.
    """
    actual_creator_id = creator_user_id if creator_user_id is not None else created_by
    if actual_creator_id is None:
        raise ValueError("creator_user_id or created_by is required.")

    name = (name or "").strip()
    if not name:
        raise ValueError("Group name is required.")

    category = (category or "Other").strip()
    norm_mode = normalize_mode(mode)
    norm_funding_mode = normalize_funding_mode(funding_mode)
    invite_code = generate_invite_code(8)

    with get_db_cursor() as (cur, conn):
        # 1. Fetch creator user details
        cur.execute("SELECT id, name FROM users WHERE id = %s", (actual_creator_id,))
        creator = cur.fetchone()
        if not creator:
            raise ValueError(f"Creator user with id {actual_creator_id} does not exist.")

        # 2. Insert group
        cur.execute(
            """
            INSERT INTO `groups` (name, description, category, mode, funding_mode, currency, invite_code, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (name, description, category, norm_mode, norm_funding_mode, currency.upper(), invite_code, actual_creator_id)
        )
        group_id = cur.lastrowid

        # 3. Add creator as first admin member
        cur.execute(
            """
            INSERT INTO group_members (group_id, user_id, display_name, role, status)
            VALUES (%s, %s, %s, 'admin', 'active')
            """,
            (group_id, actual_creator_id, creator["name"])
        )

        creator_member_id = cur.lastrowid

    return {
        "id": group_id,
        "name": name,
        "description": description,
        "category": category,
        "mode": norm_mode,
        "funding_mode": norm_funding_mode,
        "currency": currency.upper(),
        "invite_code": invite_code,
        "created_by": actual_creator_id,
        "creator_member_id": creator_member_id,
    }


def add_group_member(
    group_id: int,
    display_name: str,
    contact_info: Optional[str] = None,
    role: str = "member",
    sponsor_id: Optional[int] = None,
    family_unit_id: Optional[int] = None,
    user_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Directly adds a member or guest placeholder to a group.
    
    If user_id or contact_info matches an existing registered user, auto-links their user_id immediately.
    Otherwise, creates a placeholder with user_id = NULL.
    """
    display_name = (display_name or "").strip()
    if not display_name:
        raise ValueError("Member display name is required.")

    clean_contact = (contact_info or "").strip()
    guest_email = None
    guest_phone = None

    if clean_contact:
        if "@" in clean_contact:
            guest_email = clean_contact.lower()
        else:
            guest_phone = clean_contact

    # Verify group exists
    group = get_group_by_id(group_id)
    if not group:
        raise ValueError(f"Group with ID {group_id} not found.")

    # Normalize role to valid MySQL enum ('admin', 'member')
    norm_role = "admin" if role and role.strip().lower() == "admin" else "member"

    with get_db_cursor() as (cur, conn):
        # Check if contact_info matches an existing registered user or user_id provided
        status = "active" if user_id is not None else "guest"
        if user_id is None:
            if guest_email:
                cur.execute("SELECT id, name FROM users WHERE LOWER(email) = %s", (guest_email,))
                u = cur.fetchone()
                if u:
                    user_id = u["id"]
                    status = "active"
            elif guest_phone:
                cur.execute("SELECT id, name FROM users WHERE phone = %s", (guest_phone,))
                u = cur.fetchone()
                if u:
                    user_id = u["id"]
                    status = "active"


        # Check for duplicate user membership in this group
        if user_id is not None:
            cur.execute(
                "SELECT id FROM group_members WHERE group_id = %s AND user_id = %s",
                (group_id, user_id)
            )
            if cur.fetchone():
                raise ValueError(f"User is already a member of this group.")

        # Validate sponsor_id if provided
        if sponsor_id is not None:
            cur.execute(
                "SELECT id FROM group_members WHERE id = %s AND group_id = %s",
                (sponsor_id, group_id)
            )
            if not cur.fetchone():
                raise ValueError(f"Sponsor member ID {sponsor_id} does not exist in group {group_id}.")

        # Validate family_unit_id if provided
        if family_unit_id is not None:
            cur.execute(
                "SELECT id FROM family_units WHERE id = %s AND group_id = %s",
                (family_unit_id, group_id)
            )
            if not cur.fetchone():
                raise ValueError(f"Family unit ID {family_unit_id} does not exist in group {group_id}.")

        cur.execute(
            """
            INSERT INTO group_members (
                group_id, user_id, display_name, guest_email, guest_phone, 
                sponsor_id, family_unit_id, role, status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                group_id, user_id, display_name, guest_email, guest_phone,
                sponsor_id, family_unit_id, norm_role, status
            )
        )
        new_member_id = cur.lastrowid

    return {
        "id": new_member_id,
        "group_id": group_id,
        "user_id": user_id,
        "display_name": display_name,
        "guest_email": guest_email,
        "guest_phone": guest_phone,
        "sponsor_id": sponsor_id,
        "family_unit_id": family_unit_id,
        "role": norm_role,
        "status": status,
    }


def create_family_unit(group_id: int, name: str) -> Dict[str, Any]:
    """Creates a family unit in a Family Trip group."""
    name = (name or "").strip()
    if not name:
        raise ValueError("Family unit name is required.")

    group = get_group_by_id(group_id)
    if not group:
        raise ValueError(f"Group with ID {group_id} not found.")

    with get_db_cursor() as (cur, _):
        cur.execute(
            "INSERT INTO family_units (group_id, name) VALUES (%s, %s)",
            (group_id, name)
        )
        family_id = cur.lastrowid

    return {
        "id": family_id,
        "group_id": group_id,
        "name": name,
    }


def get_family_units(group_id: int) -> List[Dict[str, Any]]:
    """Returns all family units within a group."""
    query = "SELECT id, group_id, name, created_at FROM family_units WHERE group_id = %s ORDER BY id ASC"
    return execute_query(query, (group_id,)) or []


def get_group_by_id(group_id: int) -> Optional[Dict[str, Any]]:
    """Fetches group details by id."""
    query = "SELECT * FROM `groups` WHERE id = %s"
    return execute_query(query, (group_id,), fetchone=True)


def get_group_by_invite_code(invite_code: str) -> Optional[Dict[str, Any]]:
    """Fetches group details by invite_code."""
    code = (invite_code or "").strip().upper()
    query = "SELECT * FROM `groups` WHERE invite_code = %s"
    return execute_query(query, (code,), fetchone=True)


def get_group_members(group_id: int) -> List[Dict[str, Any]]:
    """Returns all members belonging to a group."""
    query = """
        SELECT 
            gm.id, gm.group_id, gm.user_id, gm.display_name, gm.guest_email, gm.guest_phone,
            gm.sponsor_id, s.display_name AS sponsor_name,
            gm.family_unit_id, f.name AS family_name,
            gm.role, gm.status, gm.joined_at,
            CASE WHEN gm.sponsor_id IS NOT NULL OR gm.role = 'CHILD' THEN 'CHILD' ELSE 'ADULT' END AS member_type,
            u.email AS user_email, u.phone AS user_phone
        FROM group_members gm
        LEFT JOIN group_members s ON gm.sponsor_id = s.id
        LEFT JOIN family_units f ON gm.family_unit_id = f.id
        LEFT JOIN users u ON gm.user_id = u.id
        WHERE gm.group_id = %s
        ORDER BY gm.id ASC
    """
    return execute_query(query, (group_id,)) or []


def get_unclaimed_placeholders(group_id: int) -> List[Dict[str, Any]]:
    """Returns all guest placeholders in a group that haven't been claimed yet."""
    query = """
        SELECT id, group_id, display_name, guest_email, guest_phone, role, sponsor_id
        FROM group_members
        WHERE group_id = %s AND user_id IS NULL
        ORDER BY id ASC
    """
    return execute_query(query, (group_id,)) or []


def claim_member_placeholder(group_id: int, member_id: int, user_id: int) -> Dict[str, Any]:
    """
    Claims an existing unclaimed guest placeholder for a user.
    """
    with get_db_cursor() as (cur, conn):
        # 1. Verify user is not already in the group
        cur.execute(
            "SELECT id FROM group_members WHERE group_id = %s AND user_id = %s",
            (group_id, user_id)
        )
        if cur.fetchone():
            raise ValueError("You are already an active member of this group.")

        # 2. Verify placeholder exists, belongs to group, and is unclaimed
        cur.execute(
            "SELECT id, display_name FROM group_members WHERE id = %s AND group_id = %s AND user_id IS NULL",
            (member_id, group_id)
        )
        placeholder = cur.fetchone()
        if not placeholder:
            raise ValueError(f"Placeholder member with ID {member_id} is either not found or already claimed.")

        # 3. Update placeholder to link user_id
        cur.execute(
            """
            UPDATE group_members 
            SET user_id = %s, status = 'active'
            WHERE id = %s AND user_id IS NULL
            """,
            (user_id, member_id)
        )

    return {
        "success": True,
        "member_id": member_id,
        "group_id": group_id,
        "user_id": user_id,
        "claimed_name": placeholder["display_name"]
    }


def join_group_as_new_member(
    group_id: int, 
    user_id: int, 
    display_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Adds the logged-in user as a new independent member of the group via invite code.
    """
    with get_db_cursor() as (cur, conn):
        # Check if already a member
        cur.execute(
            "SELECT id, display_name FROM group_members WHERE group_id = %s AND user_id = %s",
            (group_id, user_id)
        )
        existing = cur.fetchone()
        if existing:
            return {
                "id": existing["id"],
                "group_id": group_id,
                "user_id": user_id,
                "display_name": existing["display_name"],
                "already_member": True
            }

        # Fetch user name if display_name not provided
        cur.execute("SELECT name FROM users WHERE id = %s", (user_id,))
        u = cur.fetchone()
        if not u:
            raise ValueError(f"User with ID {user_id} not found.")

        final_name = (display_name or u["name"]).strip()

        cur.execute(
            """
            INSERT INTO group_members (group_id, user_id, display_name, role, status)
            VALUES (%s, %s, %s, 'member', 'active')
            """,
            (group_id, user_id, final_name)
        )
        new_id = cur.lastrowid

    return {
        "id": new_id,
        "group_id": group_id,
        "user_id": user_id,
        "display_name": final_name,
        "already_member": False
    }


def update_group_member(
    group_id: int,
    member_id: int,
    display_name: str,
    contact_info: Optional[str] = None,
    role: str = "member",
    sponsor_id: Optional[int] = None,
    family_unit_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Updates an existing member's display name, contact information, role, or sponsor (Adult vs Child).
    """
    display_name = (display_name or "").strip()
    if not display_name:
        raise ValueError("Member display name is required.")

    # Verify member exists in group
    query = "SELECT * FROM group_members WHERE id = %s AND group_id = %s"
    member = execute_query(query, (member_id, group_id), fetchone=True)
    if not member:
        raise ValueError(f"Member with ID {member_id} not found in group {group_id}.")

    # Prevent member from being their own sponsor
    if sponsor_id is not None and str(sponsor_id).strip() != "":
        sponsor_id = int(sponsor_id)
        if sponsor_id == member_id:
            raise ValueError("A member cannot be their own sponsor.")
        s = execute_query("SELECT id FROM group_members WHERE id = %s AND group_id = %s", (sponsor_id, group_id), fetchone=True)
        if not s:
            raise ValueError(f"Sponsor member ID {sponsor_id} does not exist.")
    else:
        sponsor_id = None

    if family_unit_id is not None and str(family_unit_id).strip() != "":
        family_unit_id = int(family_unit_id)
    else:
        family_unit_id = None

    norm_role = "admin" if role and role.strip().lower() == "admin" else "member"

    clean_contact = (contact_info or "").strip()
    guest_email = None
    guest_phone = None
    if clean_contact:
        if "@" in clean_contact:
            guest_email = clean_contact.lower()
        else:
            guest_phone = clean_contact

    with get_db_cursor() as (cur, _):
        cur.execute(
            """
            UPDATE group_members
            SET display_name = %s,
                guest_email = %s,
                guest_phone = %s,
                role = %s,
                sponsor_id = %s,
                family_unit_id = %s
            WHERE id = %s AND group_id = %s
            """,
            (display_name, guest_email, guest_phone, norm_role, sponsor_id, family_unit_id, member_id, group_id)
        )

    return {"success": True, "member_id": member_id}


def delete_group_member(group_id: int, member_id: int) -> Dict[str, Any]:
    """
    Deletes or removes a member from a group.
    Ensures that members with active transactions (expenses, splits, or settlements) cannot be deleted without first clearing transactions.
    """
    member = execute_query(
        "SELECT * FROM group_members WHERE id = %s AND group_id = %s",
        (member_id, group_id),
        fetchone=True
    )
    if not member:
        raise ValueError(f"Member with ID {member_id} does not exist in group {group_id}.")

    # Check total members - cannot delete if only member
    total_res = execute_query(
        "SELECT COUNT(*) as cnt FROM group_members WHERE group_id = %s",
        (group_id,),
        fetchone=True
    )
    if total_res and total_res["cnt"] <= 1:
        raise ValueError("Cannot delete the only remaining member in the group.")

    # Check if member has transactions
    has_paid = execute_query(
        "SELECT COUNT(*) as cnt FROM expense_payers WHERE member_id = %s",
        (member_id,),
        fetchone=True
    )["cnt"]

    has_created = execute_query(
        "SELECT COUNT(*) as cnt FROM expenses WHERE created_by_member_id = %s",
        (member_id,),
        fetchone=True
    )["cnt"]

    has_splits = execute_query(
        "SELECT COUNT(*) as cnt FROM expense_splits WHERE member_id = %s",
        (member_id,),
        fetchone=True
    )["cnt"]

    has_settlements = execute_query(
        "SELECT COUNT(*) as cnt FROM settlements WHERE payer_member_id = %s OR payee_member_id = %s",
        (member_id, member_id),
        fetchone=True
    )["cnt"]

    has_funds = execute_query(
        "SELECT COUNT(*) as cnt FROM fund_contributions WHERE member_id = %s",
        (member_id,),
        fetchone=True
    )["cnt"]

    if has_paid > 0 or has_created > 0 or has_splits > 0 or has_settlements > 0 or has_funds > 0:
        raise ValueError(
            "Cannot delete member because they have recorded expenses, splits, or settlements. "
            "Please remove or reassign their expenses first."
        )

    # Any dependents sponsored by this member will have sponsor_id set to NULL
    with get_db_cursor() as (cur, _):
        cur.execute("UPDATE group_members SET sponsor_id = NULL WHERE sponsor_id = %s", (member_id,))
        cur.execute("DELETE FROM group_members WHERE id = %s AND group_id = %s", (member_id, group_id))

    return {"success": True, "message": "Member removed successfully."}


def calculate_prorated_kitty_refunds(group_id: int) -> Dict[str, Any]:
    """
    Calculates each contributing member's prorated refund when kitty_balance > 0.
    Refund = kitty_balance * (member_contribution / total_contributions).
    """
    from services.pool_service import get_group_fund_status
    fund_status = get_group_fund_status(group_id)
    kitty_balance = to_decimal(fund_status.get("kitty_balance", Decimal('0.00')))

    if kitty_balance <= Decimal('0.00'):
        return {
            "kitty_balance": Decimal('0.00'),
            "total_contributions": Decimal('0.00'),
            "refunds": []
        }

    # Fetch total contributed per member across fund_contributions (and kitty_contributions if present)
    contrib_rows = execute_query(
        """
        SELECT fc.member_id, gm.display_name, SUM(fc.amount) as member_total
        FROM fund_contributions fc
        JOIN group_members gm ON fc.member_id = gm.id
        WHERE fc.group_id = %s
        GROUP BY fc.member_id, gm.display_name
        HAVING member_total > 0
        """,
        (group_id,)
    ) or []

    # Check if a separate kitty_contributions table exists in DB as well
    with get_db_cursor() as (cur, _):
        cur.execute("SHOW TABLES LIKE 'kitty_contributions'")
        if cur.fetchone():
            kc_rows = execute_query(
                """
                SELECT kc.member_id, gm.display_name, SUM(kc.amount) as member_total
                FROM kitty_contributions kc
                JOIN group_members gm ON kc.member_id = gm.id
                WHERE kc.group_id = %s
                GROUP BY kc.member_id, gm.display_name
                HAVING member_total > 0
                """,
                (group_id,)
            ) or []
            contrib_map = {r["member_id"]: {"member_id": r["member_id"], "display_name": r["display_name"], "member_total": to_decimal(r["member_total"])} for r in contrib_rows}
            for kr in kc_rows:
                mid = kr["member_id"]
                if mid in contrib_map:
                    contrib_map[mid]["member_total"] += to_decimal(kr["member_total"])
                else:
                    contrib_map[mid] = {"member_id": mid, "display_name": kr["display_name"], "member_total": to_decimal(kr["member_total"])}
            contrib_rows = list(contrib_map.values())

    total_contributions = sum(to_decimal(r["member_total"]) for r in contrib_rows)
    if total_contributions <= Decimal('0.00'):
        return {
            "kitty_balance": kitty_balance,
            "total_contributions": Decimal('0.00'),
            "refunds": []
        }

    refunds = []
    for r in contrib_rows:
        m_contrib = to_decimal(r["member_total"])
        m_refund = (kitty_balance * (m_contrib / total_contributions)).quantize(CENT, rounding=ROUND_HALF_UP)
        refunds.append({
            "member_id": r["member_id"],
            "display_name": r["display_name"],
            "contribution": m_contrib,
            "refund_amount": m_refund
        })

    # Penny reconciliation so sum of refunds equals kitty_balance exactly
    allocated_sum = sum(ref["refund_amount"] for ref in refunds)
    discrepancy = kitty_balance - allocated_sum
    if discrepancy != Decimal('0.00') and refunds:
        top_contributor = max(refunds, key=lambda x: x["contribution"])
        top_contributor["refund_amount"] += discrepancy

    return {
        "kitty_balance": kitty_balance,
        "total_contributions": total_contributions,
        "refunds": refunds
    }


def delete_group(group_id: int, user_id: int) -> Dict[str, Any]:
    """
    Safely deletes a group:
    1. user_id is the group creator/admin (created_by == user_id or admin role).
    2. If kitty_balance > 0, calculates each contributing member's prorated refund:
       Refund = kitty_balance * (member_contribution / total_contributions).
       Automatically records the refund settlements and clears the kitty ledger.
    3. Verifies all remaining peer-to-peer debts within the group are fully settled (all net balances == 0).
    4. Explicitly deletes all child records (settlements, kitty records, expenses, members) before deleting group.
    """
    group = get_group_by_id(group_id)
    if not group:
        raise ValueError(f"Group with ID {group_id} not found.")

    # 1. Authorization: Verify user is creator or admin
    is_creator = int(group.get("created_by") or 0) == int(user_id)
    if not is_creator:
        admin_check = execute_query(
            "SELECT id FROM group_members WHERE group_id = %s AND user_id = %s AND role = 'admin'",
            (group_id, user_id),
            fetchone=True
        )
        if not admin_check:
            raise PermissionError("Unauthorized: Only the group creator or admin can delete this group.")

    # 2. Strict guard on Kitty balance and unsettled equity
    from services.pool_service import get_group_fund_status
    fund_status = get_group_fund_status(group_id)
    kitty_bal = to_decimal(fund_status.get("kitty_balance", Decimal('0.00')))
    member_equity_map = fund_status.get("member_equity", {})
    members_breakdown = fund_status.get("members_equity_breakdown", [])
    has_unsettled_equity = (
        abs(kitty_bal) >= Decimal('0.01') or
        any(abs(to_decimal(eq)) >= Decimal('0.01') for eq in member_equity_map.values()) or
        any(abs(to_decimal(m.get("remaining_equity", Decimal('0.00')))) >= Decimal('0.01') for m in members_breakdown) or
        fund_status.get("has_deficit", False)
    )
    if has_unsettled_equity:
        raise ValueError("Cannot delete group: Please disband the Kitty and refund/settle all member equity balances first.")

    # 3. Safeguard check: verify all remaining peer-to-peer net balances are 0
    from services.settlement_service import get_group_balances
    balances = get_group_balances(group_id)
    effective_balances = balances.get("effective_balances", {})
    settlement_plan = balances.get("settlement_plan", [])

    has_unsettled = any(abs(Decimal(str(val))) >= Decimal('0.01') for val in effective_balances.values())
    if has_unsettled or len(settlement_plan) > 0:
        raise ValueError("Cannot delete group: Settle all outstanding debts first.")

    # 4. Perform cascade deletion within database transaction
    with get_db_cursor() as (cur, conn):
        cur.execute("DELETE FROM settlements WHERE group_id = %s", (group_id,))
        cur.execute("""
            DELETE FROM receipt_item_assignments 
            WHERE receipt_item_id IN (
                SELECT ri.id FROM receipt_items ri
                JOIN expenses e ON ri.expense_id = e.id
                WHERE e.group_id = %s
            )
        """, (group_id,))
        cur.execute("""
            DELETE FROM receipt_items 
            WHERE expense_id IN (SELECT id FROM expenses WHERE group_id = %s)
        """, (group_id,))
        cur.execute("""
            DELETE FROM expense_splits 
            WHERE expense_id IN (SELECT id FROM expenses WHERE group_id = %s)
        """, (group_id,))
        cur.execute("""
            DELETE FROM expense_payers 
            WHERE expense_id IN (SELECT id FROM expenses WHERE group_id = %s)
        """, (group_id,))
        cur.execute("DELETE FROM expenses WHERE group_id = %s", (group_id,))

        # Explicitly delete child Kitty records prior to deleting the group record
        cur.execute("SHOW TABLES LIKE 'kitty_contributions'")
        if cur.fetchone():
            cur.execute("DELETE FROM kitty_contributions WHERE group_id = %s", (group_id,))

        cur.execute("SHOW TABLES LIKE 'kitty_transactions'")
        if cur.fetchone():
            cur.execute("DELETE FROM kitty_transactions WHERE group_id = %s", (group_id,))

        cur.execute("DELETE FROM fund_contributions WHERE group_id = %s", (group_id,))
        cur.execute("DELETE FROM group_members WHERE group_id = %s", (group_id,))
        cur.execute("DELETE FROM family_units WHERE group_id = %s", (group_id,))
        cur.execute("DELETE FROM `groups` WHERE id = %s", (group_id,))
        conn.commit()

    return {
        "success": True,
        "message": "Group deleted successfully",
        "group_id": group_id
    }

