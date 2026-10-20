"""
SplitSmart Balance & Pool Equity Engine
Pure Decimal calculations for group member balances, child-to-parent debt rollups,
and common trip fund (kitty) pool equity tracking.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Any, Optional, Union

CENT = Decimal('0.01')


def to_decimal(val: Union[str, int, float, Decimal, None]) -> Decimal:
    """Helper to convert any numerical value to Decimal safely."""
    if val is None:
        return Decimal('0.00')
    if isinstance(val, Decimal):
        return val
    return Decimal(str(val))


def calculate_raw_group_balances(
    payers: List[Dict[str, Any]],
    splits: List[Dict[str, Any]],
    settlements: Optional[List[Dict[str, Any]]] = None
) -> Dict[Any, Decimal]:
    """
    Computes net balance per member.
    
    Convention:
        - Positive balance (+): Creditor (is owed money).
        - Negative balance (-): Debtor (owes money).
        - Zero balance (0.00): Settled.
        
    Formula:
        Net Balance = (Total Expenses Paid - Total Expenses Owed) 
                    + (Settlements Sent - Settlements Received)
                    
    Args:
        payers: List of dicts with 'member_id' and 'amount_paid'
        splits: List of dicts with 'member_id' and 'owed_amount'
        settlements: Optional list of dicts with 'payer_member_id', 'payee_member_id', 'amount',
                     and optional 'status' (default 'completed')
                     
    Returns:
        Dict[member_id, Decimal] with quantized balances.
    """
    balances: Dict[Any, Decimal] = {}

    # 1. Add amounts paid for expenses (+)
    for p in payers:
        mid = p['member_id']
        amt = to_decimal(p['amount_paid']).quantize(CENT, rounding=ROUND_HALF_UP)
        balances[mid] = balances.get(mid, Decimal('0.00')) + amt

    # 2. Subtract amounts owed for expenses (-)
    for s in splits:
        mid = s['member_id']
        amt = to_decimal(s['owed_amount']).quantize(CENT, rounding=ROUND_HALF_UP)
        balances[mid] = balances.get(mid, Decimal('0.00')) - amt

    # 3. Factor in completed settlements
    # Sending a settlement reduces debt (+ towards 0); receiving a settlement satisfies credit (- towards 0).
    if settlements:
        for st in settlements:
            status = st.get('status', 'completed')
            if status != 'completed':
                continue
            amt = to_decimal(st['amount']).quantize(CENT, rounding=ROUND_HALF_UP)
            payer_id = st['payer_member_id']
            payee_id = st['payee_member_id']

            # Payer gave money -> balance increases (debt reduced)
            balances[payer_id] = balances.get(payer_id, Decimal('0.00')) + amt
            # Payee received money -> balance decreases (credit satisfied)
            balances[payee_id] = balances.get(payee_id, Decimal('0.00')) - amt

    # Ensure all balances are quantized to CENT
    return {mid: bal.quantize(CENT, rounding=ROUND_HALF_UP) for mid, bal in balances.items()}


def rollup_sponsor_balances(
    raw_balances: Dict[Any, Decimal],
    sponsor_map: Dict[Any, Optional[Any]]
) -> Dict[Any, Decimal]:
    """
    Rolls dependent balances into their sponsor's balance (e.g. child -> parent in Family Trip mode).
    Dependents are guaranteed to have a net balance of Decimal('0.00') on the final settlement sheet.
    
    Supports multi-level hierarchies (e.g. child -> parent -> grandparent) by resolving to root sponsor.
    
    Args:
        raw_balances: Dict[member_id, Decimal]
        sponsor_map: Dict[member_id, sponsor_member_id]
        
    Returns:
        Dict[member_id, Decimal] with rolled-up balances.
    """
    # Start with a copy of all members in raw_balances or sponsor_map
    all_members = set(raw_balances.keys()) | set(sponsor_map.keys())
    rolled_balances = {m: raw_balances.get(m, Decimal('0.00')) for m in all_members}

    def get_root_sponsor(member_id: Any) -> Any:
        visited = set()
        current = member_id
        while current in sponsor_map and sponsor_map[current] is not None:
            sponsor = sponsor_map[current]
            if sponsor == current or sponsor in visited:
                break  # Prevent circular references
            visited.add(current)
            current = sponsor
        return current

    # Transfer balances from dependents to their root sponsor
    for member_id, sponsor_id in sponsor_map.items():
        if sponsor_id is not None and sponsor_id != member_id:
            root_sponsor = get_root_sponsor(member_id)
            if root_sponsor != member_id:
                dep_balance = rolled_balances.get(member_id, Decimal('0.00'))
                if dep_balance != Decimal('0.00'):
                    rolled_balances[root_sponsor] = rolled_balances.get(root_sponsor, Decimal('0.00')) + dep_balance
                    rolled_balances[member_id] = Decimal('0.00')

    # Quantize all balances
    return {m: b.quantize(CENT, rounding=ROUND_HALF_UP) for m, b in rolled_balances.items()}


def calculate_pool_equity(
    contributions: List[Dict[str, Any]],
    pool_expenses_by_member: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Tracks collective fund kitty balance and individual member remaining equity stakes.
    
    Args:
        contributions: List of dicts with 'member_id' and 'amount'
        pool_expenses_by_member: List of dicts with 'member_id' and 'amount' (consumed from kitty)
        
    Returns:
        Dict with:
            - 'total_contributed': Decimal
            - 'total_spent': Decimal
            - 'kitty_balance': Decimal (remaining fund in the common kitty)
            - 'member_equity': Dict[member_id, Decimal] (individual equity stake)
    """
    member_contributions: Dict[Any, Decimal] = {}
    member_consumed: Dict[Any, Decimal] = {}
    total_contributed = Decimal('0.00')
    total_spent = Decimal('0.00')

    all_members = set()

    for c in contributions:
        mid = c['member_id']
        amt = to_decimal(c['amount']).quantize(CENT, rounding=ROUND_HALF_UP)
        member_contributions[mid] = member_contributions.get(mid, Decimal('0.00')) + amt
        total_contributed += amt
        all_members.add(mid)

    for e in pool_expenses_by_member:
        mid = e['member_id']
        amt = to_decimal(e['amount']).quantize(CENT, rounding=ROUND_HALF_UP)
        member_consumed[mid] = member_consumed.get(mid, Decimal('0.00')) + amt
        total_spent += amt
        all_members.add(mid)

    kitty_balance = (total_contributed - total_spent).quantize(CENT, rounding=ROUND_HALF_UP)

    # Member equity = Contribution - Consumed from pool
    member_equity: Dict[Any, Decimal] = {}
    for mid in all_members:
        contrib = member_contributions.get(mid, Decimal('0.00'))
        consumed = member_consumed.get(mid, Decimal('0.00'))
        equity = contrib - consumed
        member_equity[mid] = equity.quantize(CENT, rounding=ROUND_HALF_UP)

    return {
        "total_contributed": total_contributed.quantize(CENT, rounding=ROUND_HALF_UP),
        "total_spent": total_spent.quantize(CENT, rounding=ROUND_HALF_UP),
        "kitty_balance": kitty_balance,
        "member_equity": member_equity
    }
