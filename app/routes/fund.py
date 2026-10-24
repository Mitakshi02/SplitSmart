"""
SplitSmart Common Trip Fund (Pooled Kitty) Blueprint
Provides endpoints for recording pool contributions and querying fund equity status.
"""

from decimal import Decimal
from flask import Blueprint, request, jsonify, session
from services.auth_service import login_required
from services.pool_service import record_contribution, get_group_fund_status, get_group_contributions, disband_and_refund_kitty
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
@fund_bp.route("/groups/<int:group_id>/kitty/contribute", methods=["POST"])
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

    # Validate that member is not a dependent
    from services.expense_service import resolve_member_id
    try:
        resolved_mid = resolve_member_id(group_id, member_id)
        member_check = execute_query(
            "SELECT id, sponsor_id, role FROM group_members WHERE id = %s AND group_id = %s",
            (resolved_mid, group_id),
            fetchone=True
        )
        if member_check and (member_check.get("sponsor_id") is not None or str(member_check.get("role", "")).upper() == "CHILD"):
            return jsonify({
                "success": False,
                "error": "Dependents cannot contribute directly to the Kitty. The contribution must be recorded by their sponsor."
            }), 400
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400

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
@fund_bp.route("/groups/<int:group_id>/kitty/status", methods=["GET"])
@fund_bp.route("/groups/<int:group_id>/kitty", methods=["GET"])
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


@fund_bp.route("/groups/<int:group_id>/fund/disband", methods=["POST"])
@fund_bp.route("/groups/<int:group_id>/kitty/disband", methods=["POST"])
@login_required
def disband_kitty_route(group_id: int):
    """
    Disbands the Common Kitty Pool:
    - Generates settlement payout steps to refund remaining member equity stakes.
    - Records refund settlements and clears the Kitty balance to 0.00.
    """
    user_id = session.get("user_id")
    wants_json = request.is_json or "application/json" in request.headers.get("Accept", "") or "application/json" in request.headers.get("Content-Type", "")
    try:
        res = disband_and_refund_kitty(group_id=group_id, user_id=user_id)
        if wants_json:
            return jsonify(serialize_for_json(res)), 200
        from flask import flash, redirect, url_for
        payouts_str = ", ".join([f"{p['display_name']}: INR {p['amount']:.2f}" for p in res.get("payout_steps", [])])
        flash(f"Kitty disbanded successfully. Refund payouts: {payouts_str or 'None'}", "success")
        return redirect(url_for("groups.group_detail_view", group_id=group_id))
    except PermissionError as pe:
        if wants_json:
            return jsonify({"success": False, "error": str(pe)}), 403
        from flask import flash, redirect, url_for
        flash(str(pe), "danger")
        return redirect(url_for("groups.group_detail_view", group_id=group_id))
    except ValueError as ve:
        if wants_json:
            return jsonify({"success": False, "error": str(ve)}), 400
        from flask import flash, redirect, url_for
        flash(str(ve), "danger")
        return redirect(url_for("groups.group_detail_view", group_id=group_id))
    except Exception as e:
        if wants_json:
            return jsonify({"success": False, "error": f"Failed to disband kitty: {str(e)}"}), 500
        from flask import flash, redirect, url_for
        flash(f"Failed to disband kitty: {str(e)}", "danger")
        return redirect(url_for("groups.group_detail_view", group_id=group_id))
