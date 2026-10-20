"""
SplitSmart Itemized Receipt Math Engine
Implements zero-drift itemized splitting with proportional tax, tip, and discount distribution,
and penny-level rounding reconciliation.
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


def calculate_itemized_receipt_split(
    items: List[Dict[str, Any]],
    tax: Union[Decimal, str, float] = Decimal('0.00'),
    tip: Union[Decimal, str, float] = Decimal('0.00'),
    discount: Union[Decimal, str, float] = Decimal('0.00')
) -> Dict[str, Any]:
    """
    Calculates exact member-by-member breakdown for an itemized receipt.
    
    Args:
        items: List of dicts, each with:
            - 'name': str
            - 'price': Decimal or convertible
            - 'assigned_members': list of member IDs (int or str)
        tax: Additional tax amount (Decimal)
        tip: Additional tip amount (Decimal)
        discount: Discount amount to subtract (Decimal)
        
    Returns:
        dict containing:
            - 'member_subtotals': Dict[member_id, Decimal]
            - 'member_final_shares': Dict[member_id, Decimal]
            - 'bill_summary': Dict with items_subtotal, tax, tip, discount, net_adjustment, total_bill
    """
    tax = to_decimal(tax).quantize(CENT, rounding=ROUND_HALF_UP)
    tip = to_decimal(tip).quantize(CENT, rounding=ROUND_HALF_UP)
    discount = to_decimal(discount).quantize(CENT, rounding=ROUND_HALF_UP)
    net_adjustment = tax + tip - discount

    # 1. Calculate each member's item subtotal
    member_subtotals: Dict[Any, Decimal] = {}
    total_items_subtotal = Decimal('0.00')

    # Collect all assigned members across all dishes
    all_assigned_members = set()
    for item in items:
        price = to_decimal(item['price']).quantize(CENT, rounding=ROUND_HALF_UP)
        total_items_subtotal += price
        assigned = item.get('assigned_members', [])
        if not assigned:
            continue
        
        num_assigned = len(assigned)
        # Split item price equally among assigned members
        base_split = (price / Decimal(num_assigned)).quantize(CENT, rounding=ROUND_HALF_UP)
        # Handle dish penny rounding difference
        split_diff = price - (base_split * Decimal(num_assigned))
        
        for idx, member_id in enumerate(assigned):
            all_assigned_members.add(member_id)
            share = base_split
            if idx == 0:
                share += split_diff  # assign penny difference to first member
            member_subtotals[member_id] = member_subtotals.get(member_id, Decimal('0.00')) + share

    for m in all_assigned_members:
        if m not in member_subtotals:
            member_subtotals[m] = Decimal('0.00')

    total_bill = (total_items_subtotal + net_adjustment).quantize(CENT, rounding=ROUND_HALF_UP)

    # 2. Distribute net adjustment proportionally based on consumption
    member_final_shares: Dict[Any, Decimal] = {}

    if not all_assigned_members:
        return {
            "member_subtotals": {},
            "member_final_shares": {},
            "bill_summary": {
                "items_subtotal": total_items_subtotal,
                "tax": tax,
                "tip": tip,
                "discount": discount,
                "net_adjustment": net_adjustment,
                "total_bill": total_bill
            }
        }

    if total_items_subtotal == Decimal('0.00'):
        # Edge case: Free meal or zero item total, divide net_adjustment equally
        equal_adj = (net_adjustment / Decimal(len(all_assigned_members))).quantize(CENT, rounding=ROUND_HALF_UP)
        for m in all_assigned_members:
            member_final_shares[m] = equal_adj
    else:
        # Standard case: Distribute proportionally to subtotal
        for member_id, subtotal in member_subtotals.items():
            prop_adjustment = (subtotal / total_items_subtotal) * net_adjustment
            raw_share = subtotal + prop_adjustment
            member_final_shares[member_id] = raw_share.quantize(CENT, rounding=ROUND_HALF_UP)

    # 3. Penny Reconciliation
    # Ensure sum(member_final_shares) == total_bill exactly
    computed_sum = sum(member_final_shares.values())
    discrepancy = total_bill - computed_sum

    if discrepancy != Decimal('0.00') and member_final_shares:
        # Apply discrepancy to the member with the largest subtotal (or largest final share)
        highest_payer = max(member_subtotals.keys(), key=lambda m: (member_subtotals[m], member_final_shares[m]))
        member_final_shares[highest_payer] += discrepancy

    return {
        "member_subtotals": member_subtotals,
        "member_final_shares": member_final_shares,
        "bill_summary": {
            "items_subtotal": total_items_subtotal,
            "tax": tax,
            "tip": tip,
            "discount": discount,
            "net_adjustment": net_adjustment,
            "total_bill": total_bill
        }
    }
