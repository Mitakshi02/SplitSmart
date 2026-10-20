"""
SplitSmart Authentication Routes & Endpoints
"""

from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for
from services.auth_service import (
    register_user,
    authenticate_user,
    login_user_session,
    logout_user_session,
    login_required,
    get_user_by_id
)

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register_view():
    if request.method == "POST":
        data = request.get_json(silent=True) or request.form.to_dict()
        name = data.get("name")
        email = data.get("email")
        phone = data.get("phone")
        password = data.get("password")

        try:
            user = register_user(name=name, email=email, phone=phone, password=password)
            login_user_session(user)

            next_url = request.args.get("next") or request.form.get("next")
            if request.is_json:
                return jsonify({
                    "success": True,
                    "message": "User registered successfully.",
                    "user": user,
                    "next": next_url
                }), 201

            return redirect(next_url or url_for("groups.list_groups_view"))
        except ValueError as err:
            if request.is_json:
                return jsonify({"error": str(err)}), 400
            return render_template("auth/register.html", error=str(err), data=data)

    return render_template("auth/register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login_view():
    if request.method == "POST":
        data = request.get_json(silent=True) or request.form.to_dict()
        email_or_phone = data.get("email_or_phone") or data.get("email") or data.get("phone")
        password = data.get("password")

        user = authenticate_user(email_or_phone, password)
        if not user:
            err_msg = "Invalid credentials. Please verify your email/phone and password."
            if request.is_json:
                return jsonify({"error": err_msg}), 401
            return render_template("auth/login.html", error=err_msg)

        login_user_session(user)
        next_url = request.args.get("next") or request.form.get("next")

        if request.is_json:
            return jsonify({
                "success": True,
                "message": "Logged in successfully.",
                "user": user,
                "next": next_url
            }), 200

        return redirect(next_url or url_for("groups.list_groups_view"))

    return render_template("auth/login.html")


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout_view():
    logout_user_session()
    if request.is_json:
        return jsonify({"success": True, "message": "Logged out successfully."}), 200
    return redirect(url_for("auth.login_view"))


@auth_bp.route("/me", methods=["GET"])
@login_required
def me_view():
    user = get_user_by_id(session["user_id"])
    return jsonify({"user": user}), 200
