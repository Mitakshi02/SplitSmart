"""
SplitSmart Expense Ledger Blueprint
Provides endpoints for creating, retrieving, and deleting expenses.
Supports EQUAL, EXACT, PERCENTAGE, SHARES, and ITEMIZED splits, multi-payers,
and common kitty pool expenses.
"""

from decimal import Decimal
from flask import Blueprint, request, jsonify, session
from services.auth_service import login_required
from services.expense_service import (
    create_expense,
    delete_expense,
    get_expense_details,
    get_group_expenses
)
from db import execute_query

expenses_bp = Blueprint("expenses", __name__)


def serialize_for_json(obj):
    """Recursively converts Decimal and date objects to JSON-serializable types."""
    if isinstance(obj, Decimal):
        return float(obj)
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: serialize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [serialize_for_json(item) for item in obj]
    return obj


@expenses_bp.route("/groups/<int:group_id>/expenses", methods=["GET"])
@login_required
def list_expenses_route(group_id: int):
    """Retrieves all expenses for a group."""
    try:
        expenses = get_group_expenses(group_id)
        return jsonify({"success": True, "expenses": serialize_for_json(expenses)}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@expenses_bp.route("/groups/<int:group_id>/expenses/create", methods=["POST"])
@expenses_bp.route("/groups/<int:group_id>/expenses", methods=["POST"])
@login_required
def create_expense_route(group_id: int):
    """
    Creates an expense for the given group.
    Accepts JSON body with:
    - description (or title)
    - amount
    - split_type ('EQUAL', 'EXACT', 'PERCENTAGE', 'SHARES', 'ITEMIZED')
    - payers (list of {member_id, amount_paid})
    - splits (list of {member_id, owed_amount/share_value})
    - receipt_items (optional list of line items for ITEMIZED split)
    - paid_from_pool (bool)
    - tax, tip, discount
    - category, expense_date, currency
    """
    data = request.get_json(silent=True) or request.form.to_dict()
    if not data:
        return jsonify({"success": False, "error": "Request body must be provided."}), 400

    description = data.get("description") or data.get("title")
    amount = data.get("amount")
    split_type = data.get("split_type", "EQUAL")
    payers = data.get("payers")
    splits = data.get("splits")
    receipt_items = data.get("receipt_items")
    paid_from_pool = bool(data.get("paid_from_pool", False))
    tax = data.get("tax", 0)
    tip = data.get("tip", 0)
    discount = data.get("discount", 0)
    category = data.get("category", "General")
    expense_date = data.get("expense_date")
    currency = data.get("currency", "INR")

    # Determine creator member_id
    created_by = data.get("created_by")
    if not created_by:
        user_id = session.get("user_id")
        if user_id:
            member = execute_query(
                "SELECT id FROM group_members WHERE group_id = %s AND user_id = %s",
                (group_id, user_id),
                fetchone=True
            )
            if member:
                created_by = member["id"]

    if not created_by:
        # Fallback to the first admin or member of the group
        admin = execute_query(
            "SELECT id FROM group_members WHERE group_id = %s ORDER BY id ASC LIMIT 1",
            (group_id,),
            fetchone=True
        )
        if admin:
            created_by = admin["id"]
        else:
            return jsonify({"success": False, "error": "No valid group member found to record expense."}), 400

    try:
        expense = create_expense(
            group_id=group_id,
            created_by=created_by,
            description=description,
            amount=amount,
            split_type=split_type,
            payers=payers,
            splits=splits,
            receipt_items=receipt_items,
            paid_from_pool=paid_from_pool,
            tax=tax,
            tip=tip,
            discount=discount,
            category=category,
            expense_date=expense_date,
            currency=currency
        )
        return jsonify({"success": True, "expense": serialize_for_json(expense)}), 201
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": f"Internal error creating expense: {str(e)}"}), 500


@expenses_bp.route("/expenses/<int:expense_id>", methods=["GET"])
@login_required
def get_expense_route(expense_id: int):
    """Retrieves full details of a specific expense."""
    details = get_expense_details(expense_id)
    if not details:
        return jsonify({"success": False, "error": "Expense not found."}), 404
    return jsonify({"success": True, "expense": serialize_for_json(details)}), 200


@expenses_bp.route("/expenses/<int:expense_id>/delete", methods=["POST", "DELETE"])
@expenses_bp.route("/expenses/<int:expense_id>", methods=["DELETE"])
@login_required
def delete_expense_route(expense_id: int):
    """Deletes an expense and its cascades."""
    try:
        deleted = delete_expense(expense_id)
        if not deleted:
            return jsonify({"success": False, "error": "Expense not found or already deleted."}), 404
        return jsonify({"success": True, "message": "Expense deleted successfully."}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400
