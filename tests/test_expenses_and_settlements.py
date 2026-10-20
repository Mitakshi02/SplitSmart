"""
SplitSmart Phase 4 Integration Test Suite
Verifies:
1. Creating a 3-person group with 1 child dependent sponsored by Member 1.
2. Logging an out-of-pocket dinner expense where Member 2 pays for everyone (including the child).
3. Verifying that the child's debt rolls onto Member 1 in effective_balances.
4. Recording a ₹500 pool contribution from each member, logging a pool-paid cab ride for 2 members, and verifying equity tracking.
5. Recording a "Settle Up" repayment from Member 1 to Member 2 and verifying the debt simplifier updates to reflect the cleared balance.
6. HTTP API route verification for expenses, fund contributions/status, settlements, and balances.
"""

import os
import sys
import time
import unittest
from decimal import Decimal

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from db import execute_query
from services.auth_service import register_user
from services.group_service import create_group, add_group_member
from services.expense_service import (
    create_expense,
    delete_expense,
    get_expense_details,
    get_group_expenses
)
from services.pool_service import (
    record_contribution,
    get_group_fund_status,
    get_group_contributions
)
from services.settlement_service import (
    record_settlement,
    get_group_balances,
    get_group_settlements
)


class TestExpensesAndSettlements(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()
        cls.ts = int(time.time())

    def test_complete_phase4_workflow(self):
        ts = self.ts
        app = self.app
        client = self.client

        # -------------------------------------------------------------
        # 1. SETUP: 3-Person Group with 1 Child Dependent sponsored by Member 1
        # -------------------------------------------------------------
        user_1 = register_user(
            name="Aman Sharma",
            email=f"aman_{ts}@test.com",
            phone=f"+919811{ts % 10000:04d}",
            password="Password@123"
        )
        user_2 = register_user(
            name="Rahul Verma",
            email=f"rahul_{ts}@test.com",
            phone=f"+919822{ts % 10000:04d}",
            password="Password@123"
        )
        user_3 = register_user(
            name="Pooja Patel",
            email=f"pooja_{ts}@test.com",
            phone=f"+919833{ts % 10000:04d}",
            password="Password@123"
        )

        # Create a Family Trip group with pooled_kitty funding mode
        group = create_group(
            name=f"Goa Vacation {ts}",
            created_by=user_1["id"],
            mode="family_trip",
            funding_mode="pooled_kitty",
            currency="INR"
        )
        group_id = group["id"]

        # Fetch Member 1 record (Aman)
        m1_rec = execute_query(
            "SELECT id FROM group_members WHERE group_id = %s AND user_id = %s",
            (group_id, user_1["id"]),
            fetchone=True
        )
        m1_id = m1_rec["id"]

        # Add Member 2 (Rahul)
        m2_res = add_group_member(group_id=group_id, display_name="Rahul Verma", user_id=user_2["id"])
        m2_id = m2_res["id"]

        # Add Member 3 (Pooja)
        m3_res = add_group_member(group_id=group_id, display_name="Pooja Patel", user_id=user_3["id"])
        m3_id = m3_res["id"]

        # Add 1 Child Dependent "Aryan" sponsored by Member 1 (Aman)
        child_res = add_group_member(
            group_id=group_id,
            display_name="Aryan (Child)",
            user_id=None,
            sponsor_id=m1_id
        )
        child_id = child_res["id"]

        # Verify members
        all_members = execute_query("SELECT id, display_name, sponsor_id FROM group_members WHERE group_id = %s", (group_id,))
        self.assertEqual(len(all_members), 4)

        # -------------------------------------------------------------
        # 2. LOGGING OUT-OF-POCKET DINNER: Member 2 pays for everyone (incl. child)
        # -------------------------------------------------------------
        # Bill: ₹1,200 total, EQUAL split among 4 participants (₹300 each)
        dinner_amount = Decimal('1200.00')
        dinner_payers = [{"member_id": m2_id, "amount_paid": dinner_amount}]
        dinner_splits = [m1_id, m2_id, m3_id, child_id]

        dinner_expense = create_expense(
            group_id=group_id,
            created_by=m2_id,
            description="Beach Shack Seafood Dinner",
            amount=dinner_amount,
            split_type="EQUAL",
            payers=dinner_payers,
            splits=dinner_splits,
            paid_from_pool=False,
            category="Food"
        )

        self.assertIsNotNone(dinner_expense["id"])
        self.assertEqual(dinner_expense["amount"], dinner_amount)
        self.assertEqual(len(dinner_expense["splits"]), 4)
        for s in dinner_expense["splits"]:
            self.assertEqual(s["owed_amount"], Decimal('300.00'))

        # -------------------------------------------------------------
        # 3. VERIFYING THAT CHILD'S DEBT ROLLS ONTO MEMBER 1 IN EFFECTIVE_BALANCES
        # -------------------------------------------------------------
        balance_data = get_group_balances(group_id)

        consumption = balance_data["consumption_breakdown"]
        raw_bal = balance_data["raw_balances"]
        effective_bal = balance_data["effective_balances"]
        plan = balance_data["settlement_plan"]

        # Verify consumption for each of the 4 participants
        self.assertEqual(consumption[m1_id], Decimal('300.00'))
        self.assertEqual(consumption[m2_id], Decimal('300.00'))
        self.assertEqual(consumption[m3_id], Decimal('300.00'))
        self.assertEqual(consumption[child_id], Decimal('300.00'))

        # Raw balances: M2 paid 1200, consumed 300 -> +900; others consumed 300 -> -300
        self.assertEqual(raw_bal[m2_id], Decimal('900.00'))
        self.assertEqual(raw_bal[m3_id], Decimal('-300.00'))
        self.assertEqual(raw_bal[child_id], Decimal('-300.00'))
        self.assertEqual(raw_bal[m1_id], Decimal('-300.00'))

        # Child is sponsored by Member 1 -> Child's -300 debt MUST roll onto Member 1:
        # Member 1's effective balance: -300 (own) + -300 (child) = -600.00
        self.assertEqual(effective_bal[m1_id], Decimal('-600.00'))
        self.assertEqual(effective_bal[m2_id], Decimal('900.00'))
        self.assertEqual(effective_bal[m3_id], Decimal('-300.00'))
        # Dependents must not be present in effective_balances (or must be 0)
        self.assertNotIn(child_id, effective_bal)

        # Total effective balances must sum exactly to 0.00
        self.assertEqual(sum(effective_bal.values()), Decimal('0.00'))

        # Settlement plan:
        # Member 1 pays Member 2 ₹600.00
        # Member 3 pays Member 2 ₹300.00
        self.assertEqual(len(plan), 2)
        plan_dict = {(p["from_member_id"], p["to_member_id"]): p["amount"] for p in plan}
        self.assertEqual(plan_dict.get((m1_id, m2_id)), Decimal('600.00'))
        self.assertEqual(plan_dict.get((m3_id, m2_id)), Decimal('300.00'))

        # -------------------------------------------------------------
        # 4. COMMON FUND (KITTY): Upfront ₹500 from each, pool cab for 2, equity tracking
        # -------------------------------------------------------------
        contrib_1 = record_contribution(group_id, m1_id, Decimal('500.00'), payment_method="UPI", notes="Pool Aman")
        contrib_2 = record_contribution(group_id, m2_id, Decimal('500.00'), payment_method="Cash", notes="Pool Rahul")
        contrib_3 = record_contribution(group_id, m3_id, Decimal('500.00'), payment_method="UPI", notes="Pool Pooja")

        self.assertEqual(contrib_1["amount"], Decimal('500.00'))
        self.assertEqual(contrib_2["amount"], Decimal('500.00'))
        self.assertEqual(contrib_3["amount"], Decimal('500.00'))

        # Fund status right after contributions: 1500 total, 0 spent, 1500 balance
        fund_status = get_group_fund_status(group_id)
        self.assertEqual(fund_status["total_contributed"], Decimal('1500.00'))
        self.assertEqual(fund_status["total_spent"], Decimal('0.00'))
        self.assertEqual(fund_status["kitty_balance"], Decimal('1500.00'))
        self.assertEqual(fund_status["member_equity"][m1_id], Decimal('500.00'))
        self.assertEqual(fund_status["member_equity"][m2_id], Decimal('500.00'))
        self.assertEqual(fund_status["member_equity"][m3_id], Decimal('500.00'))
        self.assertFalse(fund_status["has_deficit"])

        # Log pool-paid cab ride for Member 1 and Member 2 (₹400 total -> ₹200 each)
        cab_expense = create_expense(
            group_id=group_id,
            created_by=m1_id,
            description="Airport to Resort Cab",
            amount=Decimal('400.00'),
            split_type="EQUAL",
            splits=[m1_id, m2_id],
            paid_from_pool=True,
            category="Travel"
        )
        self.assertEqual(cab_expense["funding_source"], "kitty")
        self.assertEqual(len(cab_expense["payers"]), 0)  # No individual payers for pool expenses

        # Verify equity tracking after pool cab ride:
        # Total spent: 400.00, remaining kitty: 1100.00
        # M1 equity: 500 - 200 = 300.00
        # M2 equity: 500 - 200 = 300.00
        # M3 equity: 500 - 0 = 500.00
        fund_status_after = get_group_fund_status(group_id)
        self.assertEqual(fund_status_after["total_contributed"], Decimal('1500.00'))
        self.assertEqual(fund_status_after["total_spent"], Decimal('400.00'))
        self.assertEqual(fund_status_after["kitty_balance"], Decimal('1100.00'))
        self.assertEqual(fund_status_after["member_equity"][m1_id], Decimal('300.00'))
        self.assertEqual(fund_status_after["member_equity"][m2_id], Decimal('300.00'))
        self.assertEqual(fund_status_after["member_equity"][m3_id], Decimal('500.00'))
        self.assertFalse(fund_status_after["has_deficit"])

        # -------------------------------------------------------------
        # 5. "SETTLE UP" REPAYMENT: Member 1 pays Member 2 ₹600 -> Cleared Balance
        # -------------------------------------------------------------
        settlement = record_settlement(
            group_id=group_id,
            payer_id=m1_id,
            payee_id=m2_id,
            amount=Decimal('600.00'),
            payment_method="UPI",
            payment_reference="UPI-TXN-12345678",
            notes="Settling up dinner + child share"
        )
        self.assertIsNotNone(settlement["id"])
        self.assertEqual(settlement["amount"], Decimal('600.00'))
        self.assertEqual(settlement["status"], "completed")

        # Live balance recalculation: Member 1's debt must be COMPLETELY CLEARED
        updated_balances = get_group_balances(group_id)
        up_eff = updated_balances["effective_balances"]
        up_plan = updated_balances["settlement_plan"]

        # Member 1 was -600.00, sent 600.00 settlement -> net balance is now exactly 0.00
        self.assertEqual(up_eff[m1_id], Decimal('0.00'))
        # Member 2 was +900.00, received 600.00 settlement -> remaining credit is +300.00
        self.assertEqual(up_eff[m2_id], Decimal('300.00'))
        # Member 3 is untouched -> still owes -300.00
        self.assertEqual(up_eff[m3_id], Decimal('-300.00'))

        # Simplified settlement plan must now contain ONLY 1 transaction:
        # Member 3 pays Member 2 ₹300.00
        self.assertEqual(len(up_plan), 1)
        self.assertEqual(up_plan[0]["from_member_id"], m3_id)
        self.assertEqual(up_plan[0]["to_member_id"], m2_id)
        self.assertEqual(up_plan[0]["amount"], Decimal('300.00'))

        # -------------------------------------------------------------
        # 6. HTTP API ROUTE ENDPOINTS VERIFICATION
        # -------------------------------------------------------------
        with client.session_transaction() as sess:
            sess["user_id"] = user_1["id"]

        # Route GET /groups/<id>/balances
        resp_bal = client.get(f"/groups/{group_id}/balances")
        self.assertEqual(resp_bal.status_code, 200)
        bal_json = resp_bal.get_json()
        self.assertTrue(bal_json["success"])
        self.assertIn("consumption_breakdown", bal_json)
        self.assertIn("effective_balances", bal_json)
        self.assertIn("settlement_plan", bal_json)
        self.assertEqual(float(bal_json["effective_balances"][str(m1_id)]), 0.0)
        self.assertEqual(float(bal_json["effective_balances"][str(m2_id)]), 300.0)
        self.assertEqual(float(bal_json["effective_balances"][str(m3_id)]), -300.0)

        # Route GET /groups/<id>/fund/status
        resp_fund = client.get(f"/groups/{group_id}/fund/status")
        self.assertEqual(resp_fund.status_code, 200)
        fund_json = resp_fund.get_json()
        self.assertTrue(fund_json["success"])
        self.assertEqual(fund_json["fund_status"]["kitty_balance"], 1100.0)

        # Route POST /groups/<id>/expenses (Itemized receipt split with proportional tax/tip)
        itemized_payload = {
            "description": "Lunch with Itemized Split",
            "amount": 100.00,
            "split_type": "ITEMIZED",
            "payers": [{"member_id": m1_id, "amount_paid": 100.00}],
            "receipt_items": [
                {"name": "Paneer Tikka", "price": 40.00, "assigned_members": [m1_id, m2_id]},
                {"name": "Biryani", "price": 40.00, "assigned_members": [m2_id, m3_id]}
            ],
            "tax": 10.00,
            "tip": 10.00,
            "discount": 0.00
        }
        resp_exp = client.post(f"/groups/{group_id}/expenses", json=itemized_payload)
        self.assertEqual(resp_exp.status_code, 201)
        created_exp_id = resp_exp.get_json()["expense"]["id"]

        # Delete expense route
        resp_del = client.post(f"/expenses/{created_exp_id}/delete")
        self.assertEqual(resp_del.status_code, 200)

    def test_split_types_exact_percentage_and_shares(self):
        """Verifies EXACT, PERCENTAGE, and SHARES split types end-to-end."""
        ts = int(time.time()) + 100
        u1 = register_user(f"SplitUser1_{ts}", f"su1_{ts}@test.com", f"+919911{ts % 10000:04d}", "Password@123")
        u2 = register_user(f"SplitUser2_{ts}", f"su2_{ts}@test.com", f"+919922{ts % 10000:04d}", "Password@123")
        u3 = register_user(f"SplitUser3_{ts}", f"su3_{ts}@test.com", f"+919933{ts % 10000:04d}", "Password@123")

        grp = create_group(created_by=u1["id"], name=f"Split Types Group {ts}")
        grp_id = grp["id"]
        m1_id = execute_query("SELECT id FROM group_members WHERE group_id = %s AND user_id = %s", (grp_id, u1["id"]), fetchone=True)["id"]
        m2_id = add_group_member(group_id=grp_id, display_name="User 2", user_id=u2["id"])["id"]
        m3_id = add_group_member(group_id=grp_id, display_name="User 3", user_id=u3["id"])["id"]

        # 1. EXACT Split
        # Bill 150.00: M1 owes 70.00, M2 owes 50.00, M3 owes 30.00. Paid by M1.
        exact_exp = create_expense(
            group_id=grp_id,
            created_by=m1_id,
            description="Exact Split Groceries",
            amount=Decimal('150.00'),
            split_type="EXACT",
            payers=[{"member_id": m1_id, "amount_paid": Decimal('150.00')}],
            splits=[
                {"member_id": m1_id, "owed_amount": Decimal('70.00')},
                {"member_id": m2_id, "owed_amount": Decimal('50.00')},
                {"member_id": m3_id, "owed_amount": Decimal('30.00')}
            ]
        )
        self.assertEqual(exact_exp["amount"], Decimal('150.00'))
        self.assertEqual(len(exact_exp["splits"]), 3)

        # 2. PERCENTAGE Split
        # Bill 200.00: 50% (100.00), 30% (60.00), 20% (40.00). Paid by M2.
        pct_exp = create_expense(
            group_id=grp_id,
            created_by=m2_id,
            description="Percentage Split Airbnb",
            amount=Decimal('200.00'),
            split_type="PERCENTAGE",
            payers=[{"member_id": m2_id, "amount_paid": Decimal('200.00')}],
            splits=[
                {"member_id": m1_id, "share_value": Decimal('50.00')},
                {"member_id": m2_id, "share_value": Decimal('30.00')},
                {"member_id": m3_id, "share_value": Decimal('20.00')}
            ]
        )
        self.assertEqual(pct_exp["amount"], Decimal('200.00'))

        # 3. SHARES Split
        # Bill 300.00: 3 shares, 2 shares, 1 share -> 300 / 6 = 50 per share
        # M1 owes 150.00, M2 owes 100.00, M3 owes 50.00. Paid by M3.
        shares_exp = create_expense(
            group_id=grp_id,
            created_by=m3_id,
            description="Shares Split Drinks",
            amount=Decimal('300.00'),
            split_type="SHARES",
            payers=[{"member_id": m3_id, "amount_paid": Decimal('300.00')}],
            splits=[
                {"member_id": m1_id, "share_value": Decimal('3.00')},
                {"member_id": m2_id, "share_value": Decimal('2.00')},
                {"member_id": m3_id, "share_value": Decimal('1.00')}
            ]
        )
        self.assertEqual(shares_exp["amount"], Decimal('300.00'))

        # Verify live balances
        bals = get_group_balances(grp_id)
        # Sum of effective balances must be strictly 0.00
        self.assertEqual(sum(bals["effective_balances"].values()), Decimal('0.00'))

    def test_pool_deficit_detection(self):
        """Verifies deficit detection when pool expenses exceed member equity or kitty."""
        ts = int(time.time()) + 200
        u = register_user(f"KittyUser_{ts}", f"kitty_{ts}@test.com", f"+919944{ts % 10000:04d}", "Password@123")
        grp = create_group(created_by=u["id"], name=f"Deficit Pool Group {ts}", funding_mode="pooled_kitty")
        grp_id = grp["id"]
        m_id = execute_query("SELECT id FROM group_members WHERE group_id = %s", (grp_id,), fetchone=True)["id"]

        # Contribute ₹100
        record_contribution(grp_id, m_id, Decimal('100.00'))

        # Spend ₹150 from pool -> member equity becomes -50.00, kitty becomes -50.00
        create_expense(
            group_id=grp_id,
            created_by=m_id,
            description="Deficit Expense",
            amount=Decimal('150.00'),
            split_type="EQUAL",
            splits=[m_id],
            paid_from_pool=True
        )

        status = get_group_fund_status(grp_id)
        self.assertTrue(status["has_deficit"])
        self.assertEqual(status["kitty_balance"], Decimal('-50.00'))
        self.assertEqual(status["member_equity"][m_id], Decimal('-50.00'))
        self.assertIn(m_id, status["deficits"])

    def test_settlement_validations(self):
        """Verifies validation rules on settlements and expenses."""
        ts = int(time.time()) + 300
        u = register_user(f"ValUser_{ts}", f"val_{ts}@test.com", f"+919955{ts % 10000:04d}", "Password@123")
        grp = create_group(created_by=u["id"], name=f"Val Group {ts}")
        grp_id = grp["id"]
        m_id = execute_query("SELECT id FROM group_members WHERE group_id = %s", (grp_id,), fetchone=True)["id"]

        # Payer cannot settle with themselves
        with self.assertRaises(ValueError):
            record_settlement(grp_id, payer_id=m_id, payee_id=m_id, amount=Decimal('50.00'))

        # Amount must be positive
        with self.assertRaises(ValueError):
            record_settlement(grp_id, payer_id=m_id, payee_id=m_id, amount=Decimal('-10.00'))

        # Out of pocket expense requires payers
        with self.assertRaises(ValueError):
            create_expense(
                group_id=grp_id,
                created_by=m_id,
                description="No payers",
                amount=Decimal('100.00'),
                split_type="EQUAL",
                splits=[m_id],
                payers=[]
            )


if __name__ == "__main__":
    unittest.main()

