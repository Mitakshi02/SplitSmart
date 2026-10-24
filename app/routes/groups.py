"""
SplitSmart Group Management & Hybrid Member Onboarding Routes
"""

from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for, flash
from services.auth_service import login_required
from services.group_service import (
    create_group,
    add_group_member,
    create_family_unit,
    get_family_units,
    get_group_by_id,
    get_group_by_invite_code,
    get_group_members,
    get_unclaimed_placeholders,
    claim_member_placeholder,
    join_group_as_new_member,
    update_group_member,
    delete_group_member,
    delete_group
)
from db import execute_query

groups_bp = Blueprint("groups", __name__)


@groups_bp.route("/groups", methods=["GET"])
@login_required
def list_groups_view():
    """Lists all groups for the currently logged in user."""
    user_id = session["user_id"]
    query = """
        SELECT g.*, gm.role AS user_role, gm.joined_at AS member_since
        FROM `groups` g
        JOIN group_members gm ON g.id = gm.group_id
        WHERE gm.user_id = %s
        ORDER BY g.created_at DESC
    """
    user_groups = execute_query(query, (user_id,)) or []

    if request.is_json:
        return jsonify({"groups": user_groups}), 200

    return render_template("groups/list.html", groups=user_groups)


@groups_bp.route("/groups/create", methods=["GET", "POST"])
@login_required
def create_group_view():
    """Creates a new group with standardized shared-ledger model and category tag."""
    user_id = session["user_id"]

    if request.method == "POST":
        data = request.get_json(silent=True) or request.form.to_dict()
        name = data.get("name")
        category = data.get("category") or "Other"
        # Standardize all groups to use the identical core shared-ledger model
        mode = data.get("mode") or data.get("type") or "regular"
        funding_mode = data.get("fund_mode") or data.get("funding_mode") or "individual"
        description = data.get("description")
        currency = data.get("currency") or "INR"

        try:
            group = create_group(
                creator_user_id=user_id,
                name=name,
                category=category,
                mode=mode,
                funding_mode=funding_mode,
                description=description,
                currency=currency
            )
            if request.is_json:
                return jsonify({"success": True, "group": group}), 201
            return redirect(url_for("groups.group_detail_view", group_id=group["id"]))
        except ValueError as err:
            if request.is_json:
                return jsonify({"error": str(err)}), 400
            return render_template("groups/create.html", error=str(err), data=data)

    return render_template("groups/create.html")


@groups_bp.route("/groups/<int:group_id>", methods=["GET"])
@login_required
def group_detail_view(group_id: int):
    """Fetches details, members, and family units for a group."""
    group = get_group_by_id(group_id)
    if not group:
        if request.is_json:
            return jsonify({"error": "Group not found"}), 404
        return render_template("errors/404.html", message="Group not found"), 404

    members = get_group_members(group_id)
    families = get_family_units(group_id)
    unclaimed = get_unclaimed_placeholders(group_id)

    from services.expense_service import get_group_expenses
    from services.settlement_service import get_group_balances, get_group_settlements
    from services.pool_service import get_group_fund_status

    expenses = get_group_expenses(group_id)
    balances = get_group_balances(group_id)
    settlements = get_group_settlements(group_id)
    fund_status = get_group_fund_status(group_id) if group.get("funding_mode") in ("pooled_kitty", "common_fund", "kitty") else None
    kitty_balance = fund_status.get("kitty_balance", 0.0) if fund_status else 0.0

    if request.is_json:
        return jsonify({
            "group": group,
            "members": members,
            "families": families,
            "unclaimed_placeholders": unclaimed,
            "expenses": expenses,
            "balances": balances,
            "settlements": settlements,
            "fund_status": fund_status,
            "kitty_balance": kitty_balance
        }), 200

    return render_template(
        "groups/dashboard.html",
        group=group,
        members=members,
        families=families,
        unclaimed=unclaimed,
        expenses=expenses,
        balances=balances,
        settlements=settlements,
        fund_status=fund_status,
        kitty_balance=kitty_balance
    )



@groups_bp.route("/groups/<int:group_id>/members/add", methods=["POST"])
@login_required
def add_member_view(group_id: int):
    """Directly adds a member or guest placeholder to the group."""
    data = request.get_json(silent=True) or request.form.to_dict()
    display_name = data.get("display_name") or data.get("name")
    contact_info = data.get("contact_info") or data.get("email") or data.get("phone")
    role = data.get("role") or "member"
    
    sponsor_id = data.get("sponsor_id")
    if sponsor_id is not None and str(sponsor_id).strip() != "":
        sponsor_id = int(sponsor_id)
    else:
        sponsor_id = None

    family_unit_id = data.get("family_unit_id")
    if family_unit_id is not None and str(family_unit_id).strip() != "":
        family_unit_id = int(family_unit_id)
    else:
        family_unit_id = None

    try:
        new_member = add_group_member(
            group_id=group_id,
            display_name=display_name,
            contact_info=contact_info,
            role=role,
            sponsor_id=sponsor_id,
            family_unit_id=family_unit_id
        )
        if request.is_json:
            return jsonify({"success": True, "member": new_member}), 201
        return redirect(url_for("groups.group_detail_view", group_id=group_id))
    except ValueError as err:
        if request.is_json:
            return jsonify({"error": str(err)}), 400
        return redirect(url_for("groups.group_detail_view", group_id=group_id, error=str(err)))


@groups_bp.route("/groups/<int:group_id>/members/<int:member_id>/edit", methods=["POST"])
@groups_bp.route("/groups/<int:group_id>/members/<int:member_id>/update", methods=["POST"])
@login_required
def update_member_view(group_id: int, member_id: int):
    """Updates a member's display name, role, contact, or sponsor (Adult/Child)."""
    data = request.get_json(silent=True) or request.form.to_dict()
    display_name = data.get("display_name") or data.get("name")
    contact_info = data.get("contact_info") or data.get("email") or data.get("phone")
    role = data.get("role") or "member"
    sponsor_id = data.get("sponsor_id")
    family_unit_id = data.get("family_unit_id")

    wants_json = request.is_json or "application/json" in request.headers.get("Accept", "") or "application/json" in request.headers.get("Content-Type", "")

    try:
        res = update_group_member(
            group_id=group_id,
            member_id=member_id,
            display_name=display_name,
            contact_info=contact_info,
            role=role,
            sponsor_id=sponsor_id,
            family_unit_id=family_unit_id
        )
        if wants_json:
            return jsonify({"success": True, "result": res}), 200
        return redirect(url_for("groups.group_detail_view", group_id=group_id))
    except Exception as err:
        if wants_json:
            return jsonify({"success": False, "error": str(err)}), 400
        return redirect(url_for("groups.group_detail_view", group_id=group_id, error=str(err)))


@groups_bp.route("/groups/<int:group_id>/members/<int:member_id>/delete", methods=["POST"])
@login_required
def delete_member_view(group_id: int, member_id: int):
    """Deletes/removes a member from the group if they have no active transactions."""
    wants_json = request.is_json or "application/json" in request.headers.get("Accept", "") or "application/json" in request.headers.get("Content-Type", "")

    try:
        res = delete_group_member(group_id=group_id, member_id=member_id)
        if wants_json:
            return jsonify({"success": True, "result": res}), 200
        return redirect(url_for("groups.group_detail_view", group_id=group_id))
    except Exception as err:
        if wants_json:
            return jsonify({"success": False, "error": str(err)}), 400
        return redirect(url_for("groups.group_detail_view", group_id=group_id, error=str(err)))


@groups_bp.route("/groups/<int:group_id>/families/create", methods=["POST"], endpoint="create_family_view")
@groups_bp.route("/groups/<int:group_id>/families/new", methods=["POST"], endpoint="create_family_unit_view")
@login_required
def create_family_view(group_id: int):
    """Creates a family unit in a Family Trip group."""
    data = request.get_json(silent=True) or request.form.to_dict()
    family_name = data.get("name") or data.get("family_name") or data.get("unit_name")

    try:
        family = create_family_unit(group_id=group_id, name=family_name)
        if request.is_json:
            return jsonify({"success": True, "family": family}), 201
        return redirect(url_for("groups.group_detail_view", group_id=group_id))
    except ValueError as err:
        if request.is_json:
            return jsonify({"error": str(err)}), 400
        return redirect(url_for("groups.group_detail_view", group_id=group_id, error=str(err)))


@groups_bp.route("/join/<string:invite_code>", methods=["GET", "POST"])
def join_group_view(invite_code: str):
    """
    Shareable invite link endpoint.
    - If user is not logged in: prompts login/registration while preserving redirect URL.
    - If logged in: allows claiming an existing placeholder OR joining fresh as a new member.
    """
    group = get_group_by_invite_code(invite_code)
    if not group:
        if request.is_json:
            return jsonify({"error": "Invalid or expired invite code."}), 404
        return render_template("errors/404.html", message="Invalid invite link."), 404

    # 1. Check user login status
    if "user_id" not in session:
        if request.is_json:
            return jsonify({
                "error": "Authentication required",
                "login_url": url_for("auth.login_view", next=request.url)
            }), 401
        return redirect(url_for("auth.login_view", next=request.url))

    user_id = session["user_id"]

    # 2. Check if already joined
    group_id = group["id"]
    query = "SELECT id, display_name FROM group_members WHERE group_id = %s AND user_id = %s"
    existing_membership = execute_query(query, (group_id, user_id), fetchone=True)

    if request.method == "POST":
        data = request.get_json(silent=True) or request.form.to_dict()
        action = data.get("action", "join_fresh")  # 'claim' or 'join_fresh'

        try:
            if action == "claim":
                member_id = int(data.get("member_id"))
                result = claim_member_placeholder(group_id=group_id, member_id=member_id, user_id=user_id)
                if request.is_json:
                    return jsonify({"success": True, "action": "claimed", "result": result}), 200
                return redirect(url_for("groups.group_detail_view", group_id=group_id))
            else:
                display_name = data.get("display_name")
                result = join_group_as_new_member(group_id=group_id, user_id=user_id, display_name=display_name)
                if request.is_json:
                    return jsonify({"success": True, "action": "joined_fresh", "result": result}), 200
                return redirect(url_for("groups.group_detail_view", group_id=group_id))
        except (ValueError, TypeError) as err:
            if request.is_json:
                return jsonify({"error": str(err)}), 400
            unclaimed = get_unclaimed_placeholders(group_id)
            return render_template(
                "groups/join.html",
                group=group,
                unclaimed=unclaimed,
                existing_membership=existing_membership,
                error=str(err)
            )

    # GET request
    unclaimed = get_unclaimed_placeholders(group_id)
    if request.is_json:
        return jsonify({
            "group": group,
            "unclaimed_placeholders": unclaimed,
            "already_joined": existing_membership is not None
        }), 200

    return render_template(
        "groups/join.html",
        group=group,
        unclaimed=unclaimed,
        existing_membership=existing_membership
    )


@groups_bp.route("/groups/<int:group_id>/delete", methods=["POST"])
@login_required
def delete_group_view(group_id: int):
    """
    Safely deletes a group if all balances are settled and user is the creator/admin.
    Automatically handles prorated refunds when an active kitty balance exists.
    """
    wants_json = request.is_json or "application/json" in request.headers.get("Accept", "") or "application/json" in request.headers.get("Content-Type", "")
    user_id = session.get("user_id")
    try:
        res = delete_group(group_id, user_id)
        flash("Group deleted successfully", "success")
        if wants_json:
            return jsonify({
                "success": True,
                "message": "Group deleted successfully",
                "prorated_refunds": res.get("prorated_refunds", [])
            }), 200
        return redirect(url_for("groups.list_groups_view"))
    except PermissionError as pe:
        if wants_json:
            return jsonify({"error": str(pe)}), 403
        flash(str(pe), "danger")
        return redirect(url_for("groups.group_detail_view", group_id=group_id))
    except ValueError as ve:
        if wants_json:
            return jsonify({"error": str(ve)}), 400
        flash(str(ve), "danger")
        return redirect(url_for("groups.group_detail_view", group_id=group_id))
    except Exception as err:
        if wants_json:
            return jsonify({"error": f"Failed to delete group: {str(err)}"}), 500
        flash(f"Failed to delete group: {str(err)}", "danger")
        return redirect(url_for("groups.group_detail_view", group_id=group_id))
