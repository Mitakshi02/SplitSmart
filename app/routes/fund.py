"""
SplitSmart Common Trip Fund (Pooled Kitty) Blueprint
Provides endpoints for recording pool contributions and querying fund equity status.
"""

from decimal import Decimal
from flask import Blueprint, request, jsonify, session
from services.auth_service import login_required
from services.pool_service import record_contribution, get_group_fund_status, get_group_contributions
from db import execute_query

fund_bp = Blueprint("fund", __name__)


def serialize_for_json(obj):
    """Recursively converts Decimal and date objects to JSON-serializable types."""
    if isinstance(obj, Decimal):
        return float(obj)
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {str(k): serialize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [serialize_for_json(item) for item in obj]
    return obj


@fund_bp.route("/groups/<int:group_id>/fund/contribute", methods=["POST"])
@login_required
def contribute_route(group_id: int):
    """
    Records an upfront member contribution to the common trip kitty.
    Accepts JSON or form data:
    - member_id (optional if logged in)
    - amount
    - payment_method ('Cash', 'UPI', 'Bank Transfer', etc.)
    - notes
    """
    data = request.get_json(silent=True) or request.form.to_dict()
    if not data:
        return jsonify({"success": False, "error": "Request body must be provided."}), 400

    member_id = data.get("member_id")
    if not member_id:
        user_id = session.get("user_id")
        if user_id:
            member = execute_query(
                "SELECT id FROM group_members WHERE group_id = %s AND user_id = %s",
                (group_id, user_id),
                fetchone=True
            )
            if member:
                member_id = member["id"]

    if not member_id:
        return jsonify({"success": False, "error": "member_id is required."}), 400

    amount = data.get("amount")
    if amount is None:
        return jsonify({"success": False, "error": "amount is required."}), 400

    payment_method = data.get("payment_method", "Cash")
    notes = data.get("notes")

    try:
        contrib = record_contribution(
            group_id=group_id,
            member_id=member_id,
            amount=amount,
            payment_method=payment_method,
            notes=notes
        )
        return jsonify({"success": True, "contribution": serialize_for_json(contrib)}), 201
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to record contribution: {str(e)}"}), 500


@fund_bp.route("/groups/<int:group_id>/fund/status", methods=["GET"])
@fund_bp.route("/groups/<int:group_id>/fund", methods=["GET"])
@login_required
def fund_status_route(group_id: int):
    """
    Retrieves the common fund / pooled kitty status:
    - total_contributed
    - total_spent
    - kitty_balance
    - member_equity
    - members_equity_breakdown
    - has_deficit
    """
    try:
        status = get_group_fund_status(group_id)
        return jsonify({"success": True, "fund_status": serialize_for_json(status)}), 200
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to retrieve fund status: {str(e)}"}), 500
