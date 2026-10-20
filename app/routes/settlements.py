"""
SplitSmart Settlements & Balances Blueprint
Provides endpoints for recording repayments and fetching live balance breakdowns,
sponsor debt rollups, and simplified settlement plans.
"""

from decimal import Decimal
from flask import Blueprint, request, jsonify, session
from services.auth_service import login_required
from services.settlement_service import (
    record_settlement,
    get_group_settlements,
    get_group_balances
)

settlements_bp = Blueprint("settlements", __name__)


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


@settlements_bp.route("/groups/<int:group_id>/settle", methods=["POST"])
@login_required
def settle_route(group_id: int):
    """
    Logs a direct repayment between two group members.
    Accepts JSON or form data:
    - payer_id / payer_member_id
    - payee_id / payee_member_id
    - amount
    - payment_method ('CASH', 'UPI', 'BANK_TRANSFER', 'Cash', etc.)
    - reference_note / payment_reference
    - notes
    """
    data = request.get_json(silent=True) or request.form.to_dict()
    if not data:
        return jsonify({"success": False, "error": "Request body must be provided."}), 400

    payer_id = data.get("payer_id") or data.get("payer_member_id")
    payee_id = data.get("payee_id") or data.get("payee_member_id")
    amount = data.get("amount")

    if payer_id is None:
        return jsonify({"success": False, "error": "payer_id is required."}), 400
    if payee_id is None:
        return jsonify({"success": False, "error": "payee_id is required."}), 400
    if amount is None:
        return jsonify({"success": False, "error": "amount is required."}), 400

    payment_method = data.get("payment_method", "CASH")
    reference_note = data.get("reference_note") or data.get("payment_reference")
    notes = data.get("notes")

    try:
        settlement = record_settlement(
            group_id=group_id,
            payer_id=payer_id,
            payee_id=payee_id,
            amount=amount,
            payment_method=payment_method,
            payment_reference=reference_note,
            notes=notes
        )
        return jsonify({"success": True, "settlement": serialize_for_json(settlement)}), 201
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to record settlement: {str(e)}"}), 500


@settlements_bp.route("/groups/<int:group_id>/balances", methods=["GET"])
@login_required
def balances_route(group_id: int):
    """
    Returns live balance recalculation combining expenses, child-to-parent debt rollups,
    and settlements.
    
    Response JSON:
        1. consumption_breakdown: What each member (including children) consumed
        2. effective_balances: Net balances for responsible adult members (+ owed, - owes)
        3. settlement_plan: Minimum transaction steps to settle all debts
    """
    try:
        balance_data = get_group_balances(group_id)
        serialized = serialize_for_json(balance_data)
        return jsonify({
            "success": True,
            "consumption_breakdown": serialized.get("consumption_breakdown", {}),
            "effective_balances": serialized.get("effective_balances", {}),
            "settlement_plan": serialized.get("settlement_plan", []),
            "raw_balances": serialized.get("raw_balances", {}),
            "rolled_balances": serialized.get("rolled_balances", {}),
            "member_details": serialized.get("member_details", {})
        }), 200
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to calculate balances: {str(e)}"}), 500


@settlements_bp.route("/groups/<int:group_id>/settlements", methods=["GET"])
@login_required
def list_settlements_route(group_id: int):
    """Lists all historical repayments for the group."""
    try:
        settlements = get_group_settlements(group_id)
        return jsonify({"success": True, "settlements": serialize_for_json(settlements)}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400
