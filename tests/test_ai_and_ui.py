"""
SplitSmart Phase 5 Integration & AI Test Suite
Verifies:
1. Natural language expense text parser (AI Feature 1).
2. Smart multimodal receipt scanner (AI Feature 2).
3. HTTP AI endpoints: /groups/<id>/ai/parse-text & /groups/<id>/ai/scan-receipt.
4. Full group detail view rendering with live ledger, settlement plan, and kitty widgets.
"""

import os
import io
import sys
import time
import unittest
from decimal import Decimal
from PIL import Image

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from db import execute_query
from services.auth_service import register_user
from services.group_service import create_group, add_group_member
from services.ai_nl_parser import parse_expense_text
from services.ai_receipt_scanner import scan_receipt_image


class TestAiAndFrontend(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()
        cls.ts = int(time.time())

        # Create a sample testing image (a simple 100x100 white square)
        img = Image.new('RGB', (100, 100), color='white')
        buf = io.BytesIO()
        img.save(buf, format='JPEG')
        cls.test_image_bytes = buf.getvalue()

    def test_ai_nl_parser_heuristics_and_structure(self):
        """Verifies natural language expense text parsing produces required JSON schema."""
        roster = [
            {"id": 1, "name": "Rahul Verma"},
            {"id": 2, "name": "Aman Sharma"},
            {"id": 3, "name": "Pooja Patel"}
        ]

        # Case 1: Simple everyone split
        prompt_1 = "Rahul paid 1200 for beach dinner for everyone"
        res_1 = parse_expense_text(prompt_1, group_member_roster=roster)

        self.assertEqual(res_1["amount"], Decimal('1200.00'))
        self.assertEqual(res_1["payer_name"], "Rahul Verma")
        self.assertEqual(res_1["payer_id"], 1)
        self.assertEqual(len(res_1["split_members"]), 3)
        self.assertIn("Rahul Verma", res_1["split_members"])
        self.assertIn("Aman Sharma", res_1["split_members"])
        self.assertIn("Pooja Patel", res_1["split_members"])

        # Case 2: Subset of participants
        prompt_2 = "Pooja paid 500 for groceries split between Pooja and Aman"
        res_2 = parse_expense_text(prompt_2, group_member_roster=roster)

        self.assertEqual(res_2["amount"], Decimal('500.00'))
        self.assertEqual(res_2["payer_name"], "Pooja Patel")
        self.assertEqual(res_2["payer_id"], 3)
        self.assertEqual(len(res_2["split_members"]), 2)
        self.assertIn("Pooja Patel", res_2["split_members"])
        self.assertIn("Aman Sharma", res_2["split_members"])

    def test_ai_receipt_scanner_structure(self):
        """Verifies multimodal receipt scanning extracts items, taxes, and totals."""
        res = scan_receipt_image(self.test_image_bytes, mime_type="image/jpeg")

        self.assertIn("merchant_name", res)
        self.assertIn("items", res)
        self.assertIn("subtotal", res)
        self.assertIn("tax", res)
        self.assertIn("total", res)
        self.assertIsInstance(res["total"], Decimal)
        self.assertGreater(res["total"], Decimal('0.00'))

        # Check line items
        self.assertGreater(len(res["items"]), 0)
        item = res["items"][0]
        self.assertIn("name", item)
        self.assertIn("quantity", item)
        self.assertIn("unit_price", item)
        self.assertIn("total_price", item)

    def test_http_ai_endpoints_and_group_detail_view(self):
        """Verifies Flask routes /ai/parse-text, /ai/scan-receipt, and group detail rendering."""
        ts = self.ts
        client = self.client

        # 1. Register test user & create group
        user = register_user(f"AI User {ts}", f"ai_{ts}@test.com", f"+919988{ts % 10000:04d}", "Password@123")
        grp = create_group(created_by=user["id"], name=f"AI Trip {ts}", funding_mode="pooled_kitty")
        grp_id = grp["id"]

        with client.session_transaction() as sess:
            sess["user_id"] = user["id"]
            sess["user_name"] = user["name"]

        # 2. Test /groups/<id>/ai/parse-text route
        parse_resp = client.post(
            f"/groups/{grp_id}/ai/parse-text",
            json={"text": f"{user['name']} paid 900 for lunch for everyone"}
        )
        self.assertEqual(parse_resp.status_code, 200)
        parse_json = parse_resp.get_json()
        self.assertTrue(parse_json["success"])
        self.assertEqual(parse_json["parsed"]["amount"], 900.0)

        # 3. Test /groups/<id>/ai/scan-receipt route
        data = {
            'receipt_file': (io.BytesIO(self.test_image_bytes), 'test_receipt.jpg')
        }
        ocr_resp = client.post(
            f"/groups/{grp_id}/ai/scan-receipt",
            data=data,
            content_type='multipart/form-data'
        )
        self.assertEqual(ocr_resp.status_code, 200)
        ocr_json = ocr_resp.get_json()
        self.assertTrue(ocr_json["success"])
        self.assertIn("items", ocr_json["receipt"])

        # 4. Test GET /groups/<id> HTML view rendering
        detail_resp = client.get(f"/groups/{grp_id}")
        self.assertEqual(detail_resp.status_code, 200)
        html = detail_resp.get_data(as_text=True)

        self.assertIn(grp["name"], html)
        self.assertIn("Expense Ledger", html)
        self.assertIn("Live Balances & Settle Up", html)
        self.assertIn("Common Kitty Pool", html)
        self.assertIn("Smart Receipt OCR", html)

    def test_fuzzy_name_matching(self):
        """Verifies difflib fuzzy matching resolves IDs even with partial names or typos."""
        roster = [
            {"id": 101, "name": "Uncle Ramesh Gupta"},
            {"id": 102, "name": "Sneha Kulkarni"}
        ]
        # Partial match: 'Ramesh' -> 'Uncle Ramesh Gupta'
        res = parse_expense_text("Ramesh paid 400 for sweets", group_member_roster=roster)
        self.assertEqual(res["payer_id"], 101)
        self.assertEqual(res["payer_name"], "Uncle Ramesh Gupta")
        self.assertEqual(res["amount"], Decimal('400.00'))

    def test_ai_receipt_parser_module(self):
        """Verifies services.ai_receipt_parser.parse_receipt_image directly."""
        from services.ai_receipt_parser import parse_receipt_image
        res = parse_receipt_image(self.test_image_bytes, mime_type="image/jpeg")
        self.assertIn("items", res)
        self.assertIn("total", res)
        self.assertIsInstance(res["total"], Decimal)

    def test_api_nl_and_receipt_routes(self):
        """Verifies /api/groups/<id>/ai/parse-nl and /api/groups/<id>/ai/parse-receipt."""
        ts = self.ts + 50
        client = self.client

        user = register_user(f"API User {ts}", f"api_{ts}@test.com", f"+919977{ts % 10000:04d}", "Password@123")
        grp = create_group(created_by=user["id"], name=f"API Trip {ts}")
        grp_id = grp["id"]

        with client.session_transaction() as sess:
            sess["user_id"] = user["id"]

        # Route /api/groups/<id>/ai/parse-nl
        resp_nl = client.post(
            f"/api/groups/{grp_id}/ai/parse-nl",
            json={"text": "Aman paid 650 for petrol"}
        )
        self.assertEqual(resp_nl.status_code, 200)
        self.assertTrue(resp_nl.get_json()["success"])

        # Route /api/groups/<id>/ai/parse-receipt
        data = {'receipt_file': (io.BytesIO(self.test_image_bytes), 'bill.jpg')}
        resp_ocr = client.post(
            f"/api/groups/{grp_id}/ai/parse-receipt",
            data=data,
            content_type='multipart/form-data'
        )
        self.assertEqual(resp_ocr.status_code, 200)
        self.assertTrue(resp_ocr.get_json()["success"])


if __name__ == "__main__":
    unittest.main()

