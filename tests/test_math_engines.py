"""
SplitSmart Mathematical Verification Test Suite
Phase 2: Verifies zero-drift decimal arithmetic, penny reconciliation,
sponsor debt rollups, and greedy debt minimization.
"""

import sys
import os
import unittest
from decimal import Decimal

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.receipt_math import calculate_itemized_receipt_split
from services.balance_engine import (
    calculate_raw_group_balances,
    rollup_sponsor_balances,
    calculate_pool_equity
)
from services.debt_simplifier import simplify_debts


class TestMathEngines(unittest.TestCase):

    def test_itemized_receipt_split_penny_reconciliation(self):
        """
        1. Itemized split with 4 dishes shared unequally, plus tax, tip, and discount,
        verifying that the penny reconciler prevents off-by-one errors.
        """
        items = [
            {"name": "Truffle Pizza", "price": Decimal('35.50'), "assigned_members": [1, 2]},
            {"name": "Pasta Carbonara", "price": Decimal('22.00'), "assigned_members": [2, 3]},
            {"name": "Ribeye Steak", "price": Decimal('48.75'), "assigned_members": [1, 3, 4]},
            {"name": "Chocolate Lava Cake", "price": Decimal('14.25'), "assigned_members": [4]},
        ]
        tax = Decimal('10.85')
        tip = Decimal('18.00')
        discount = Decimal('15.00')

        result = calculate_itemized_receipt_split(items, tax=tax, tip=tip, discount=discount)

        bill_summary = result["bill_summary"]
        member_subtotals = result["member_subtotals"]
        member_final_shares = result["member_final_shares"]

        # Expected items subtotal: 35.50 + 22.00 + 48.75 + 14.25 = 120.50
        self.assertEqual(bill_summary["items_subtotal"], Decimal('120.50'))
        
        # Expected net adjustment: 10.85 + 18.00 - 15.00 = 13.85
        self.assertEqual(bill_summary["net_adjustment"], Decimal('13.85'))

        # Expected total bill: 120.50 + 13.85 = 134.35
        expected_total = Decimal('134.35')
        self.assertEqual(bill_summary["total_bill"], expected_total)

        # Dish subtotal sum must equal items subtotal
        self.assertEqual(sum(member_subtotals.values()), Decimal('120.50'))

        # CRITICAL TEST: Sum of individual rounded shares MUST equal total_bill to the exact penny
        actual_shares_sum = sum(member_final_shares.values())
        self.assertEqual(
            actual_shares_sum, 
            expected_total, 
            f"Penny reconciliation failed! Expected {expected_total}, got {actual_shares_sum}"
        )

        # Verify all members are Decimals with 2 decimal places
        for mid, share in member_final_shares.items():
            self.assertIsInstance(share, Decimal)
            self.assertEqual(share.as_tuple().exponent, -2)

    def test_raw_group_balances(self):
        """
        Verifies raw net balance calculation from expenses and settlements.
        """
        payers = [
            {"member_id": 1, "amount_paid": Decimal('100.00')},
            {"member_id": 2, "amount_paid": Decimal('50.00')},
        ]
        splits = [
            {"member_id": 1, "owed_amount": Decimal('50.00')},
            {"member_id": 2, "owed_amount": Decimal('50.00')},
            {"member_id": 3, "owed_amount": Decimal('50.00')},
        ]
        settlements = [
            {"payer_member_id": 3, "payee_member_id": 1, "amount": Decimal('20.00'), "status": "completed"}
        ]

        # Prior to settlement:
        # Member 1: Paid 100 - Owed 50 = +50
        # Member 2: Paid 50 - Owed 50 = 0
        # Member 3: Paid 0 - Owed 50 = -50
        # After settlement (Member 3 sent 20 to Member 1):
        # Member 1: +50 - 20 (received) = +30
        # Member 2: 0
        # Member 3: -50 + 20 (sent) = -30
        balances = calculate_raw_group_balances(payers, splits, settlements)

        self.assertEqual(balances[1], Decimal('30.00'))
        self.assertEqual(balances[2], Decimal('0.00'))
        self.assertEqual(balances[3], Decimal('-30.00'))
        # Total sum of balances must be 0
        self.assertEqual(sum(balances.values()), Decimal('0.00'))

    def test_child_to_parent_debt_rollup(self):
        """
        2. Child-to-parent debt rollup where children have negative and positive balances,
        verifying that children balances become 0.00 and parent absorbs net amounts.
        """
        raw_balances = {
            1: Decimal('-50.00'),  # Dad
            2: Decimal('100.00'),  # Mom
            3: Decimal('-30.00'),  # Teen child (owes money)
            4: Decimal('20.00'),   # Younger child (is owed a refund)
            5: Decimal('-40.00'),  # Independent Friend
        }

        # Sponsor hierarchy:
        # Member 3 (Teen) -> sponsored by Member 1 (Dad)
        # Member 4 (Younger child) -> sponsored by Member 2 (Mom)
        # Members 1, 2, 5 have no sponsor
        sponsor_map = {
            3: 1,
            4: 2,
            1: None,
            2: None,
            5: None,
        }

        rolled_balances = rollup_sponsor_balances(raw_balances, sponsor_map)

        # Dependent children must end with exactly Decimal('0.00')
        self.assertEqual(rolled_balances[3], Decimal('0.00'), "Child 3 balance must be 0.00")
        self.assertEqual(rolled_balances[4], Decimal('0.00'), "Child 4 balance must be 0.00")

        # Dad absorbed Teen Child's debt (-50 + -30 = -80.00)
        self.assertEqual(rolled_balances[1], Decimal('-80.00'))

        # Mom absorbed Younger Child's credit (100 + 20 = 120.00)
        self.assertEqual(rolled_balances[2], Decimal('120.00'))

        # Independent friend unaffected
        self.assertEqual(rolled_balances[5], Decimal('-40.00'))

        # Total group balance is conserved
        self.assertEqual(sum(raw_balances.values()), sum(rolled_balances.values()))

    def test_debt_simplifier(self):
        """
        3. Debt simplification verification: sum of transactions settles all debts,
        net balances after simulated settlements equal 0 for all participants,
        and number of transactions is strictly minimized.
        """
        net_balances = {
            1: Decimal('-60.00'),  # Debtor 1 owes 60
            2: Decimal('-40.00'),  # Debtor 2 owes 40
            3: Decimal('70.00'),   # Creditor 1 is owed 70
            4: Decimal('30.00'),   # Creditor 2 is owed 30
            5: Decimal('0.00'),    # Already settled
        }

        transactions = simplify_debts(net_balances)

        # Verify minimum transaction count (at most 3 transactions needed for 4 active members)
        self.assertLessEqual(len(transactions), 3)

        # Verify sum of transaction amounts equals total debt (100.00)
        total_transferred = sum(t["amount"] for t in transactions)
        self.assertEqual(total_transferred, Decimal('100.00'))

        # Simulate settlement application to verify all balances become 0
        simulated_balances = dict(net_balances)
        for t in transactions:
            simulated_balances[t["from_member"]] += t["amount"]
            simulated_balances[t["to_member"]] -= t["amount"]

        for mid, remaining in simulated_balances.items():
            self.assertEqual(
                remaining.quantize(Decimal('0.01')), 
                Decimal('0.00'), 
                f"Member {mid} was not settled completely! Residual: {remaining}"
            )

    def test_pooled_kitty_equity_calculation(self):
        """
        4. Pooled kitty equity calculation: contributions, kitty spent,
        remaining balance, and member equity sum.
        """
        contributions = [
            {"member_id": 1, "amount": Decimal('500.00')},
            {"member_id": 2, "amount": Decimal('300.00')},
            {"member_id": 3, "amount": Decimal('200.00')},
        ]
        pool_expenses = [
            {"member_id": 1, "amount": Decimal('250.00')},
            {"member_id": 2, "amount": Decimal('350.00')},
            {"member_id": 3, "amount": Decimal('100.00')},
        ]

        equity_data = calculate_pool_equity(contributions, pool_expenses)

        self.assertEqual(equity_data["total_contributed"], Decimal('1000.00'))
        self.assertEqual(equity_data["total_spent"], Decimal('700.00'))
        self.assertEqual(equity_data["kitty_balance"], Decimal('300.00'))

        # Member equity check:
        # Member 1: 500 - 250 = +250.00
        # Member 2: 300 - 350 = -50.00 (consumed more than contributed)
        # Member 3: 200 - 100 = +100.00
        member_equity = equity_data["member_equity"]
        self.assertEqual(member_equity[1], Decimal('250.00'))
        self.assertEqual(member_equity[2], Decimal('-50.00'))
        self.assertEqual(member_equity[3], Decimal('100.00'))

        # Sum of member equities must equal the remaining kitty balance exactly!
        self.assertEqual(sum(member_equity.values()), equity_data["kitty_balance"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
