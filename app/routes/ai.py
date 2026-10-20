"""
SplitSmart AI Services Blueprint
Provides endpoints for:
1. Natural language expense text parsing into structured expense records.
2. Multimodal receipt scanning with dish line items, taxes, and totals.
"""

import os
import logging
from decimal import Decimal
from flask import Blueprint, request, jsonify, session, current_app
from werkzeug.utils import secure_filename

from services.auth_service import login_required
from services.ai_nl_parser import parse_expense_text
from services.ai_receipt_scanner import scan_receipt_image
from services.group_service import get_group_members

logger = logging.getLogger(__name__)

ai_bp = Blueprint("ai", __name__)


def serialize_for_json(obj):
    """Recursively converts Decimal and dates into JSON-serializable types."""
    if isinstance(obj, Decimal):
        return float(obj)
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {str(k): serialize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [serialize_for_json(item) for item in obj]
    return obj


@ai_bp.route("/api/groups/<int:group_id>/ai/parse-nl", methods=["POST"])
@ai_bp.route("/groups/<int:group_id>/ai/parse-text", methods=["POST"])
@login_required
def parse_text_route(group_id: int):
    """
    Parses a plain-text expense description into structured expense fields.
    Input: JSON {"text": "Aman paid 1200 for dinner for everyone"}
    """
    data = request.get_json(silent=True) or request.form.to_dict()
    if not data or not data.get("text"):
        return jsonify({"success": False, "error": "Field 'text' is required."}), 400

    text = data.get("text")
    try:
        # Fetch group member roster
        members = get_group_members(group_id)
        roster = [{"id": m["id"], "name": m["display_name"]} for m in members]

        parsed = parse_expense_text(text=text, group_member_roster=roster)
        return jsonify({"success": True, "parsed": serialize_for_json(parsed)}), 200
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to parse text: {str(e)}"}), 500


@ai_bp.route("/api/groups/<int:group_id>/ai/parse-receipt", methods=["POST"])
@ai_bp.route("/groups/<int:group_id>/ai/scan-receipt", methods=["POST"])
@login_required
def scan_receipt_route(group_id: int):

    """
    Accepts an uploaded receipt image and extracts merchant, items, taxes, and totals.
    """
    if "receipt_file" not in request.files and "image" not in request.files:
        return jsonify({"success": False, "error": "No receipt file uploaded."}), 400

    file = request.files.get("receipt_file") or request.files.get("image")
    if not file or file.filename == "":
        return jsonify({"success": False, "error": "No file selected."}), 400

    filename = secure_filename(file.filename)
    mime_type = file.mimetype or "image/jpeg"
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if ext == 'pdf':
        mime_type = 'application/pdf'
    elif ext in ('jpg', 'jpeg'):
        mime_type = 'image/jpeg'
    elif ext == 'png':
        mime_type = 'image/png'
    elif ext == 'webp':
        mime_type = 'image/webp'
    file_bytes = file.read()

    # Optional: save to upload directory
    upload_dir = current_app.config.get("UPLOAD_FOLDER")
    saved_path = None
    if upload_dir and file_bytes:
        os.makedirs(upload_dir, exist_ok=True)
        saved_path = os.path.join(upload_dir, f"receipt_{group_id}_{filename}")
        try:
            with open(saved_path, "wb") as f:
                f.write(file_bytes)
        except Exception:
            saved_path = None

    try:
        receipt_data = scan_receipt_image(file_bytes, mime_type=mime_type)
        if saved_path:
            receipt_data["saved_image_path"] = saved_path

        return jsonify({"success": True, "receipt": serialize_for_json(receipt_data)}), 200
    except ValueError as ve:
        logger.warning("Receipt scan validation error: %s", ve)
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        logger.exception("Receipt scanning encountered an error: %s", e)
        return jsonify({"success": False, "error": f"Receipt scanning failed: {str(e)}"}), 500
