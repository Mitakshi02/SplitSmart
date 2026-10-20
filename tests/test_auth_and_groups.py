"""
SplitSmart Authentication, Group Management & Hybrid Onboarding Integration Test Suite
Phase 3 Verification:
1. User A creates a "Family Trip", family unit, and adds guest "Uncle Ramesh" & sponsored child "Aarav".
2. User B registers with ramesh@test.com and auto-claims Uncle Ramesh's placeholder spot.
3. User C uses the invite link to claim an unclaimed placeholder spot.
4. User D joins fresh via invite link.
"""

import os
import sys
import time
import unittest
from decimal import Decimal

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from db import execute_query, execute_write
from services.auth_service import register_user, authenticate_user
from services.group_service import (
    create_group,
    add_group_member,
    create_family_unit,
    get_group_by_id,
    get_group_members,
    get_unclaimed_placeholders,
    claim_member_placeholder,
    join_group_as_new_member
)


class TestAuthAndGroups(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()

        # Generate unique test email suffix for repeated clean execution
        cls.ts = int(time.time())

    def test_complete_phase3_workflow(self):
        ts = self.ts
        email_a = f"alok_{ts}@test.com"
        email_b = f"ramesh_{ts}@test.com"
        email_c = f"priya_{ts}@test.com"
        email_d = f"vikram_{ts}@test.com"

        # -------------------------------------------------------------
        # STEP 1: Register User A and create Family Trip
        # -------------------------------------------------------------
        user_a = register_user(
            name="Alok Sharma",
            email=email_a,
            phone=f"+9198000{ts % 10000:04d}",
            password="Password@123"
        )
        self.assertIsNotNone(user_a["id"])
        user_a_id = user_a["id"]

        # Verify authentication
        auth_a = authenticate_user(email_a, "Password@123")
        self.assertIsNotNone(auth_a)
        self.assertEqual(auth_a["id"], user_a_id)

        # Create Family Trip group
        group = create_group(
            creator_user_id=user_a_id,
            name="Goa Family Vacation",
            mode="FAMILY_TRIP",
            funding_mode="COMMON_FUND",
            description="Annual family holiday"
        )
        self.assertEqual(group["mode"], "family_trip")
        self.assertEqual(group["funding_mode"], "pooled_kitty")
        self.assertTrue(len(group["invite_code"]) >= 8)
        group_id = group["id"]
        invite_code = group["invite_code"]

        # Verify User A is member #1 and admin
        members = get_group_members(group_id)
        self.assertEqual(len(members), 1)
        self.assertEqual(members[0]["user_id"], user_a_id)
        self.assertEqual(members[0]["role"], "admin")
        creator_member_id = members[0]["id"]

        # Create Family Unit
        family = create_family_unit(group_id, "The Sharmas")
        self.assertIsNotNone(family["id"])
        family_id = family["id"]

        # Add placeholder guest "Uncle Ramesh" with email_b
        guest_ramesh = add_group_member(
            group_id=group_id,
            display_name="Uncle Ramesh",
            contact_info=email_b,
            role="member",
            family_unit_id=family_id
        )
        self.assertIsNone(guest_ramesh["user_id"])
        self.assertEqual(guest_ramesh["status"], "guest")
        self.assertEqual(guest_ramesh["guest_email"], email_b)
        ramesh_placeholder_id = guest_ramesh["id"]

        # Add child "Aarav" sponsored by User A (Alok)
        child_aarav = add_group_member(
            group_id=group_id,
            display_name="Aarav",
            role="member",
            sponsor_id=creator_member_id,
            family_unit_id=family_id
        )
        self.assertIsNone(child_aarav["user_id"])
        self.assertEqual(child_aarav["sponsor_id"], creator_member_id)

        # -------------------------------------------------------------
        # STEP 2: User B registers with ramesh email -> Transactional Auto-Claim
        # -------------------------------------------------------------
        user_b = register_user(
            name="Ramesh Sharma",
            email=email_b,
            password="Password@456"
        )
        user_b_id = user_b["id"]

        # Verify that Uncle Ramesh's placeholder was automatically claimed
        updated_ramesh = execute_query(
            "SELECT id, user_id, status, display_name FROM group_members WHERE id = %s",
            (ramesh_placeholder_id,),
            fetchone=True
        )
        self.assertEqual(
            updated_ramesh["user_id"], 
            user_b_id, 
            "Transactional auto-claim failed! Placeholder user_id was not linked."
        )
        self.assertEqual(updated_ramesh["status"], "active")

        # -------------------------------------------------------------
        # STEP 3: Shareable Invite Link Claim Flow (User C claims placeholder)
        # -------------------------------------------------------------
        # User A adds an unlinked placeholder "Aunt Priya" (without pre-set contact info)
        guest_priya = add_group_member(
            group_id=group_id,
            display_name="Aunt Priya",
            family_unit_id=family_id
        )
        priya_placeholder_id = guest_priya["id"]
        self.assertIsNone(guest_priya["user_id"])

        # Check unclaimed list
        unclaimed = get_unclaimed_placeholders(group_id)
        unclaimed_ids = [u["id"] for u in unclaimed]
        self.assertIn(priya_placeholder_id, unclaimed_ids)
        self.assertNotIn(ramesh_placeholder_id, unclaimed_ids)  # Ramesh is already claimed!

        # Register User C
        user_c = register_user(
            name="Priya Sharma",
            email=email_c,
            password="Password@789"
        )
        user_c_id = user_c["id"]

        # User C claims Aunt Priya's spot via HTTP endpoint
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_c_id
            sess["user_name"] = "Priya Sharma"

        response = self.client.post(
            f"/join/{invite_code}",
            json={"action": "claim", "member_id": priya_placeholder_id}
        )
        self.assertEqual(response.status_code, 200)
        json_resp = response.get_json()
        self.assertTrue(json_resp["success"])
        self.assertEqual(json_resp["action"], "claimed")

        # Verify DB reflects User C claim
        claimed_priya = execute_query(
            "SELECT user_id, status FROM group_members WHERE id = %s",
            (priya_placeholder_id,),
            fetchone=True
        )
        self.assertEqual(claimed_priya["user_id"], user_c_id)
        self.assertEqual(claimed_priya["status"], "active")

        # -------------------------------------------------------------
        # STEP 4: Join Fresh via Invite Code (User D)
        # -------------------------------------------------------------
        user_d = register_user(
            name="Vikram Verma",
            email=email_d,
            password="Password@999"
        )
        user_d_id = user_d["id"]

        with self.client.session_transaction() as sess:
            sess["user_id"] = user_d_id
            sess["user_name"] = "Vikram Verma"

        response_join = self.client.post(
            f"/join/{invite_code}",
            json={"action": "join_fresh", "display_name": "Vikram V."}
        )
        self.assertEqual(response_join.status_code, 200)

        # Verify Vikram is in the group members
        all_members = get_group_members(group_id)
        member_names = [m["display_name"] for m in all_members]
        self.assertIn("Vikram V.", member_names)
        self.assertIn("Aarav", member_names)
        self.assertIn("Uncle Ramesh", member_names)
        self.assertIn("Aunt Priya", member_names)
        self.assertIn("Alok Sharma", member_names)

        print("\nAll Phase 3 integration scenarios executed and verified successfully!")

    def test_group_category_and_safe_delete(self):
        """Verifies group category tags and safe delete behavior with debt safeguards."""
        from services.expense_service import create_expense
        from services.settlement_service import record_settlement
        ts = int(time.time()) + 999
        user_owner = register_user(f"Owner_{ts}", f"owner_{ts}@test.com", f"+919811{ts % 10000:04d}", "Password@123")
        user_peer = register_user(f"Peer_{ts}", f"peer_{ts}@test.com", f"+919822{ts % 10000:04d}", "Password@123")

        # 1. Create group with Category Tag "Trip"
        group = create_group(
            creator_user_id=user_owner["id"],
            name=f"Road Trip {ts}",
            category="Trip",
            mode="regular"
        )
        group_id = group["id"]
        self.assertEqual(group["category"], "Trip")

        # Fetch group to verify category persisted in DB
        fetched_group = get_group_by_id(group_id)
        self.assertEqual(fetched_group["category"], "Trip")

        # Add peer member
        peer_member = add_group_member(
            group_id=group_id,
            display_name="Peer Member",
            contact_info=user_peer["email"],
            role="member"
        )
        owner_member_id = group["creator_member_id"]
        peer_member_id = peer_member["id"]

        # 2. Add an expense so debt is unsettled
        create_expense(
            group_id=group_id,
            created_by=owner_member_id,
            description="Highway Toll & Snacks",
            amount=Decimal('400.00'),
            split_type="EQUAL",
            payers=[{"member_id": owner_member_id, "amount_paid": Decimal('400.00')}],
            splits=[{"member_id": owner_member_id}, {"member_id": peer_member_id}]
        )

        # 3. Attempt to delete group while debt is unsettled -> Expect HTTP 400
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_owner["id"]
            sess["user_name"] = "Owner"

        resp_fail = self.client.post(f"/groups/{group_id}/delete", json={})
        self.assertEqual(resp_fail.status_code, 400)
        self.assertIn("Settle all outstanding debts first", resp_fail.get_json()["error"])

        # 4. Attempt to delete group from unauthorized user -> Expect HTTP 403
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_peer["id"]
            sess["user_name"] = "Peer"

        resp_unauth = self.client.post(f"/groups/{group_id}/delete", json={})
        self.assertEqual(resp_unauth.status_code, 403)

        # 5. Settle the debt completely
        record_settlement(
            group_id=group_id,
            payer_id=peer_member_id,
            payee_id=owner_member_id,
            amount=Decimal('200.00'),
            payment_method="UPI"
        )

        # 6. Creator deletes group now that all balances == 0 -> Expect HTTP 200
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_owner["id"]
            sess["user_name"] = "Owner"

        resp_success = self.client.post(f"/groups/{group_id}/delete", json={})
        self.assertEqual(resp_success.status_code, 200)
        self.assertTrue(resp_success.get_json()["success"])

        # 7. Verify group no longer exists
        self.assertIsNone(get_group_by_id(group_id))


if __name__ == "__main__":
    unittest.main(verbosity=2)
