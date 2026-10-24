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
from services.group_service import (
    create_group,
    add_group_member,
    delete_group,
    calculate_prorated_kitty_refunds,
    get_group_members
)
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

    def test_spend_from_kitty_functionality(self):
        """
        Verifies:
        1. When paid_by == 'KITTY', group must be configured for common fund / pooled kitty.
        2. Expense amount cannot exceed remaining kitty balance (returns HTTP 400 / ValueError).
        3. Successful Kitty expense sets funding_source='kitty', paid_from_pool=True.
        4. No rows inserted into expense_payers.
        5. expense_splits are recorded and deduct from member pool equity.
        6. HTTP response returns updated fund_status.
        """
        ts = int(time.time()) + 400
        client = self.client

        # Register 2 users
        u1 = register_user(f"KittyA_{ts}", f"kittya_{ts}@test.com", f"+919966{ts % 10000:04d}", "Password@123")
        u2 = register_user(f"KittyB_{ts}", f"kittyb_{ts}@test.com", f"+919977{ts % 10000:04d}", "Password@123")

        # 1. Non-kitty group attempt
        regular_grp = create_group(created_by=u1["id"], name=f"Regular Group {ts}", funding_mode="individual")
        r_grp_id = regular_grp["id"]
        rm1 = execute_query("SELECT id FROM group_members WHERE group_id = %s", (r_grp_id,), fetchone=True)["id"]

        with client.session_transaction() as sess:
            sess["user_id"] = u1["id"]

        resp_invalid_mode = client.post(
            f"/groups/{r_grp_id}/expenses",
            json={
                "title": "Invalid Kitty Spend",
                "amount": 50.0,
                "paid_by": "KITTY",
                "splits": [rm1]
            }
        )
        self.assertEqual(resp_invalid_mode.status_code, 400)
        self.assertIn("Group is not configured for Common Fund", resp_invalid_mode.get_json()["error"])

        # 2. Pooled Kitty group
        kitty_grp = create_group(created_by=u1["id"], name=f"Kitty Group {ts}", funding_mode="pooled_kitty", currency="INR")
        k_grp_id = kitty_grp["id"]
        km1 = execute_query("SELECT id FROM group_members WHERE group_id = %s AND user_id = %s", (k_grp_id, u1["id"]), fetchone=True)["id"]
        km2_res = add_group_member(group_id=k_grp_id, display_name="Member Two", user_id=u2["id"])
        km2 = km2_res["id"]

        # Spend with 0 kitty balance -> should fail with 400
        resp_zero_balance = client.post(
            f"/groups/{k_grp_id}/expenses",
            json={
                "title": "Coffee from empty kitty",
                "amount": 100.0,
                "paid_by": "KITTY",
                "splits": [km1, km2]
            }
        )
        self.assertEqual(resp_zero_balance.status_code, 400)
        self.assertIn("exceeds remaining kitty balance", resp_zero_balance.get_json()["error"])

        # 3. Deposit ₹500 into kitty (₹250 from each member)
        record_contribution(k_grp_id, km1, Decimal('250.00'))
        record_contribution(k_grp_id, km2, Decimal('250.00'))

        status_before = get_group_fund_status(k_grp_id)
        self.assertEqual(status_before["kitty_balance"], Decimal('500.00'))

        # 4. Attempt to spend ₹600 (exceeds ₹500 balance) -> 400
        resp_overspend = client.post(
            f"/groups/{k_grp_id}/expenses",
            json={
                "title": "Overspending Kitty",
                "amount": 600.0,
                "paid_by": "KITTY",
                "splits": [km1, km2]
            }
        )
        self.assertEqual(resp_overspend.status_code, 400)
        self.assertIn("exceeds remaining kitty balance", resp_overspend.get_json()["error"])

        # 5. Spend ₹200 from Kitty (valid: 200 <= 500)
        resp_success = client.post(
            f"/groups/{k_grp_id}/expenses",
            json={
                "title": "Lunch from Kitty",
                "amount": 200.0,
                "paid_by": "KITTY",
                "splits": [km1, km2]
            }
        )
        self.assertEqual(resp_success.status_code, 201)
        res_data = resp_success.get_json()
        self.assertTrue(res_data["success"])
        self.assertIn("fund_status", res_data)
        self.assertEqual(res_data["fund_status"]["kitty_balance"], 300.0)

        exp_id = res_data["expense"]["id"]

        # 6. Verify database records:
        # Check expense row
        exp_row = execute_query("SELECT * FROM expenses WHERE id = %s", (exp_id,), fetchone=True)
        self.assertEqual(exp_row["funding_source"], "kitty")

        # Check expense_payers: MUST BE EMPTY (no individual member payers)
        payers = execute_query("SELECT * FROM expense_payers WHERE id = %s", (exp_id,))
        self.assertEqual(len(payers), 0)

        # Check expense_splits: MUST HAVE 2 rows of ₹100 each
        splits = execute_query("SELECT * FROM expense_splits WHERE expense_id = %s ORDER BY member_id ASC", (exp_id,))
        self.assertEqual(len(splits), 2)
        self.assertEqual(splits[0]["owed_amount"], Decimal('100.00'))
        self.assertEqual(splits[1]["owed_amount"], Decimal('100.00'))

        # Verify pool equity deducted
        status_after = get_group_fund_status(k_grp_id)
        self.assertEqual(status_after["kitty_balance"], Decimal('300.00'))
        self.assertEqual(status_after["member_equity"][km1], Decimal('150.00'))
        self.assertEqual(status_after["member_equity"][km2], Decimal('150.00'))

    def test_restrict_dependents_from_kitty_contribution(self):
        """
        Verifies:
        1. In group members, dependents have member_type == 'CHILD' and sponsor_id is not None.
        2. Backend API rejects contribution from dependent with HTTP 400.
        3. Service rejects direct contribution call with ValueError.
        """
        ts = int(time.time()) + 600
        client = self.client

        # Register sponsor user
        sponsor_user = register_user(f"Sponsor_{ts}", f"sponsor_{ts}@test.com", f"+919988{ts % 10000:04d}", "Password@123")
        grp = create_group(created_by=sponsor_user["id"], name=f"Dependent Kitty Test {ts}", funding_mode="pooled_kitty")
        grp_id = grp["id"]

        sponsor_m = execute_query("SELECT id FROM group_members WHERE group_id = %s AND user_id = %s", (grp_id, sponsor_user["id"]), fetchone=True)["id"]

        # Add child dependent sponsored by sponsor_m
        child_res = add_group_member(group_id=grp_id, display_name="Little Aarav", role="CHILD", sponsor_id=sponsor_m)
        child_id = child_res["id"]

        # Verify member list has member_type == 'CHILD'
        members = get_group_members(grp_id)
        child_member = next(m for m in members if m["id"] == child_id)
        self.assertEqual(child_member["member_type"], "CHILD")
        self.assertEqual(child_member["sponsor_id"], sponsor_m)

        with client.session_transaction() as sess:
            sess["user_id"] = sponsor_user["id"]

        # 1. API contribution rejection on dependent
        resp = client.post(
            f"/groups/{grp_id}/fund/contribute",
            json={
                "member_id": child_id,
                "amount": 200.0,
                "payment_method": "UPI"
            }
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Dependents cannot contribute directly to the Kitty", resp.get_json()["error"])

        # 2. Service level rejection on dependent
        with self.assertRaises(ValueError) as ctx:
            record_contribution(group_id=grp_id, member_id=child_id, amount=Decimal('100.00'))
        self.assertIn("Dependents cannot contribute directly to the Kitty", str(ctx.exception))

        # 3. Adult sponsor can contribute successfully
        adult_resp = client.post(
            f"/groups/{grp_id}/fund/contribute",
            json={
                "member_id": sponsor_m,
                "amount": 500.0,
                "payment_method": "UPI"
            }
        )
        self.assertEqual(adult_resp.status_code, 201)

    def test_delete_group_with_active_kitty_and_prorated_refunds(self):
        """
        Verifies:
        1. When a group has an active Kitty balance, calculate_prorated_kitty_refunds
           correctly determines each member's refund:
           Refund = kitty_balance * (member_contribution / total_contributions).
        2. Deleting the group automatically records the refund settlements, clears the ledger,
           and cascade-deletes all child kitty records without foreign key errors.
        """
        ts = int(time.time()) + 700
        client = self.client

        u1 = register_user(f"Admin_{ts}", f"admin_{ts}@test.com", f"+919911{ts % 10000:04d}", "Password@123")
        u2 = register_user(f"User2_{ts}", f"user2_{ts}@test.com", f"+919922{ts % 10000:04d}", "Password@123")

        grp = create_group(created_by=u1["id"], name=f"Active Kitty Delete Grp {ts}", funding_mode="pooled_kitty")
        grp_id = grp["id"]

        m1 = execute_query("SELECT id FROM group_members WHERE group_id = %s AND user_id = %s", (grp_id, u1["id"]), fetchone=True)["id"]
        m2_res = add_group_member(group_id=grp_id, display_name="Partner", user_id=u2["id"])
        m2 = m2_res["id"]

        # Member 1 deposits ₹400, Member 2 deposits ₹200 (Total: ₹600)
        record_contribution(grp_id, m1, Decimal('400.00'))
        record_contribution(grp_id, m2, Decimal('200.00'))

        # Spend ₹300 from kitty (Remaining kitty balance = ₹300)
        create_expense(
            group_id=grp_id,
            created_by=m1,
            description="Pool Cab",
            amount=Decimal('300.00'),
            split_type="EQUAL",
            splits=[m1, m2],
            paid_by="KITTY"
        )

        status = get_group_fund_status(grp_id)
        self.assertEqual(status["kitty_balance"], Decimal('300.00'))

        # Check prorated refunds:
        # m1 refund = 300 * (400 / 600) = 200.00
        # m2 refund = 300 * (200 / 600) = 100.00
        refunds_data = calculate_prorated_kitty_refunds(grp_id)
        self.assertEqual(refunds_data["kitty_balance"], Decimal('300.00'))
        self.assertEqual(refunds_data["total_contributions"], Decimal('600.00'))

        m1_ref = next(r for r in refunds_data["refunds"] if r["member_id"] == m1)
        m2_ref = next(r for r in refunds_data["refunds"] if r["member_id"] == m2)
        self.assertEqual(m1_ref["refund_amount"], Decimal('200.00'))
        self.assertEqual(m2_ref["refund_amount"], Decimal('100.00'))

        with client.session_transaction() as sess:
            sess["user_id"] = u1["id"]

        # 1. Deletion attempt with active Kitty balance MUST be blocked
        del_blocked_resp = client.post(f"/groups/{grp_id}/delete", headers={"Accept": "application/json"})
        self.assertEqual(del_blocked_resp.status_code, 400)
        blocked_json = del_blocked_resp.get_json()
        self.assertIn("Please disband the Kitty and refund/settle all member equity balances first", blocked_json.get("error", ""))

        # 2. Call Disband & Refund Kitty routine
        disband_resp = client.post(f"/groups/{grp_id}/kitty/disband", headers={"Accept": "application/json"})
        self.assertEqual(disband_resp.status_code, 200)
        disband_json = disband_resp.get_json()
        self.assertTrue(disband_json["success"])
        self.assertEqual(disband_json["kitty_balance"], 0.0)
        payouts = disband_json["payout_steps"]
        self.assertTrue(len(payouts) >= 2)

        # Verify fund status now shows 0.00 balance and all equities 0.00
        status_after_disband = get_group_fund_status(grp_id)
        self.assertEqual(status_after_disband["kitty_balance"], Decimal('0.00'))
        for eq in status_after_disband["member_equity"].values():
            self.assertEqual(eq, Decimal('0.00'))

        # 3. Now delete group via HTTP endpoint MUST succeed
        del_resp = client.post(f"/groups/{grp_id}/delete", headers={"Accept": "application/json"})
        self.assertEqual(del_resp.status_code, 200)
        res_json = del_resp.get_json()
        self.assertTrue(res_json["success"])

        # Verify group is completely deleted from DB
        grp_check = execute_query("SELECT id FROM `groups` WHERE id = %s", (grp_id,), fetchone=True)
        self.assertIsNone(grp_check)

        # Verify child records deleted
        fc_check = execute_query("SELECT id FROM fund_contributions WHERE group_id = %s", (grp_id,))
        self.assertEqual(len(fc_check), 0)

    def test_kitty_dependent_family_equity_rollup(self):
        """
        Verifies:
        1. Exclude dependent members (member_type == 'CHILD' or sponsor_id IS NOT NULL)
           from rendering as independent rows in the equity table.
        2. Roll up the dependent's consumed amount into their designated sponsor_id:
           Sponsor Consumed = Sponsor Personal Consumed + SUM(Dependents Consumed)
           Sponsor Remaining Equity = Sponsor Deposited - Sponsor Consumed.
        3. Ensure no dependent shows a separate 'Deficit!' badge.
        """
        ts = int(time.time()) + 800
        u1 = register_user(f"Sponsor_{ts}", f"sponsor_{ts}@test.com", f"+919933{ts % 10000:04d}", "Password@123")
        u2 = register_user(f"Mitakshi_{ts}", f"mitakshi_{ts}@test.com", f"+919944{ts % 10000:04d}", "Password@123")

        grp = create_group(created_by=u1["id"], name=f"Kitty Family Rollup {ts}", funding_mode="pooled_kitty")
        grp_id = grp["id"]

        m_sponsor = execute_query("SELECT id FROM group_members WHERE group_id = %s AND user_id = %s", (grp_id, u1["id"]), fetchone=True)["id"]
        m_child_res = add_group_member(group_id=grp_id, display_name="Aarav (Child)", role="CHILD", sponsor_id=m_sponsor)
        m_child = m_child_res["id"]
        m_mitakshi_res = add_group_member(group_id=grp_id, display_name="Mitakshi", user_id=u2["id"])
        m_mitakshi = m_mitakshi_res["id"]

        # Sponsor deposits 1500, Mitakshi deposits 1000
        record_contribution(grp_id, m_sponsor, Decimal('1500.00'))
        record_contribution(grp_id, m_mitakshi, Decimal('1000.00'))

        # Kitty expense: 600 split equally among Sponsor (200), Child (200), Mitakshi (200)
        create_expense(
            group_id=grp_id,
            created_by=m_sponsor,
            description="Theme Park Entry",
            amount=Decimal('600.00'),
            split_type="EQUAL",
            splits=[m_sponsor, m_child, m_mitakshi],
            paid_by="KITTY"
        )

        status = get_group_fund_status(grp_id)
        self.assertEqual(status["kitty_balance"], Decimal('1900.00'))
        self.assertEqual(status["total_contributed"], Decimal('2500.00'))
        self.assertEqual(status["total_spent"], Decimal('600.00'))

        # Breakdown rows check: child must be excluded!
        breakdown = status["members_equity_breakdown"]
        breakdown_ids = [row["member_id"] for row in breakdown]
        self.assertNotIn(m_child, breakdown_ids)
        self.assertIn(m_sponsor, breakdown_ids)
        self.assertIn(m_mitakshi, breakdown_ids)

        # Check Sponsor's rolled up numbers:
        # Personal consumed = 200, Dependent consumed = 200, Sponsor consumed = 400
        # Sponsor equity = 1500 - 400 = 1100
        sponsor_row = next(r for r in breakdown if r["member_id"] == m_sponsor)
        self.assertEqual(sponsor_row["personal_consumed"], Decimal('200.00'))
        self.assertEqual(sponsor_row["dependents_consumed"], Decimal('200.00'))
        self.assertEqual(sponsor_row["consumed"], Decimal('400.00'))
        self.assertEqual(sponsor_row["remaining_equity"], Decimal('1100.00'))
        self.assertFalse(sponsor_row["is_deficit"])

        # Check Mitakshi's numbers:
        mitakshi_row = next(r for r in breakdown if r["member_id"] == m_mitakshi)
        self.assertEqual(mitakshi_row["consumed"], Decimal('200.00'))
        self.assertEqual(mitakshi_row["remaining_equity"], Decimal('800.00'))
        self.assertFalse(mitakshi_row["is_deficit"])

        # Ensure no deficit anywhere
        self.assertFalse(status["has_deficit"])
        self.assertEqual(len(status["deficits"]), 0)

        # Check Deficit Rollup:
        # Sponsor deposited 1500. Let's add an expense of 1400 split between Sponsor (700) and Child (700).
        # Total Sponsor consumed becomes: 400 + 1400 = 1800.
        # Sponsor equity = 1500 - 1800 = -300 (Deficit!).
        create_expense(
            group_id=grp_id,
            created_by=m_sponsor,
            description="Luxury Resort Stay",
            amount=Decimal('1400.00'),
            split_type="EQUAL",
            splits=[m_sponsor, m_child],
            paid_by="KITTY"
        )

        deficit_status = get_group_fund_status(grp_id)
        self.assertTrue(deficit_status["has_deficit"])
        # Deficit belongs to sponsor, NOT the child!
        self.assertIn(m_sponsor, deficit_status["deficits"])
        self.assertNotIn(m_child, deficit_status["deficits"])
        self.assertEqual(deficit_status["deficits"][m_sponsor], Decimal('-300.00'))

        # Child still not in breakdown table
        new_breakdown_ids = [r["member_id"] for r in deficit_status["members_equity_breakdown"]]
        self.assertNotIn(m_child, new_breakdown_ids)
        new_sponsor_row = next(r for r in deficit_status["members_equity_breakdown"] if r["member_id"] == m_sponsor)
        self.assertTrue(new_sponsor_row["is_deficit"])
        self.assertEqual(new_sponsor_row["remaining_equity"], Decimal('-300.00'))


if __name__ == "__main__":
    unittest.main()

