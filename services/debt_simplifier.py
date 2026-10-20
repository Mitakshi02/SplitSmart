"""
SplitSmart Debt Simplification Engine
Implements a greedy bipartite debt-minimization algorithm to reduce complex webs
of mutual debt down to the minimum possible number of direct peer-to-peer settlements.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Any, Union

CENT = Decimal('0.01')


def to_decimal(val: Union[str, int, float, Decimal, None]) -> Decimal:
    """Helper to convert any numerical value to Decimal safely."""
    if val is None:
        return Decimal('0.00')
    if isinstance(val, Decimal):
        return val
    return Decimal(str(val))


def simplify_debts(net_balances: Dict[Any, Union[Decimal, str, float]]) -> List[Dict[str, Any]]:
    """
    Minimizes cross-debts among group members using a greedy matching algorithm.
    
    Args:
        net_balances: Dict[member_id, net_balance]
            - Negative values represent debtors (members who owe money).
            - Positive values represent creditors (members who are owed money).
            - Zero values represent settled members.
            
    Returns:
        List of optimized settlement transactions:
        [
            {"from_member": debtor_id, "to_member": creditor_id, "amount": Decimal('...')}
        ]
    """
    # 1. Filter out settled members and separate into debtors and creditors
    debtors: List[List[Any]] = []   # [[member_id, debt_amount_positive]]
    creditors: List[List[Any]] = [] # [[member_id, credit_amount_positive]]

    for member_id, balance_raw in net_balances.items():
        bal = to_decimal(balance_raw).quantize(CENT, rounding=ROUND_HALF_UP)
        if bal < -CENT:
            debtors.append([member_id, -bal])  # store as positive debt
        elif bal > CENT:
            creditors.append([member_id, bal]) # store as positive credit

    # Sort descending by amount to prioritize settling large obligations first
    debtors.sort(key=lambda x: x[1], reverse=True)
    creditors.sort(key=lambda x: x[1], reverse=True)

    settlements: List[Dict[str, Any]] = []

    # 2. Greedy bipartite matching
    d_idx = 0
    c_idx = 0

    while d_idx < len(debtors) and c_idx < len(creditors):
        debtor_id, debt_amt = debtors[d_idx]
        creditor_id, credit_amt = creditors[c_idx]

        settle_amt = min(debt_amt, credit_amt).quantize(CENT, rounding=ROUND_HALF_UP)

        if settle_amt > Decimal('0.00'):
            settlements.append({
                "from_member": debtor_id,
                "to_member": creditor_id,
                "amount": settle_amt
            })

        # Update remaining balances
        debt_amt -= settle_amt
        credit_amt -= settle_amt

        debtors[d_idx][1] = debt_amt
        creditors[c_idx][1] = credit_amt

        # Advance pointers if satisfied
        if debt_amt <= CENT / Decimal('2'):
            d_idx += 1
        if credit_amt <= CENT / Decimal('2'):
            c_idx += 1

    return settlements
