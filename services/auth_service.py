"""
SplitSmart Authentication & User Service
Handles user registration, password hashing, session management,
and transactional auto-claiming of guest placeholders upon registration.
"""

import os
import re
from functools import wraps
from typing import Optional, Dict, Any, Union
from werkzeug.security import generate_password_hash, check_password_hash
from flask import session, request, redirect, url_for, jsonify

from db import get_db_cursor, execute_query, execute_write


def is_valid_email(email: str) -> bool:
    """Basic validation for email format."""
    pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    return bool(re.match(pattern, email.strip()))


def register_user(
    name: str, 
    email: Optional[str] = None, 
    phone: Optional[str] = None, 
    password: Optional[str] = None
) -> Dict[str, Any]:
    """
    Registers a new user and automatically claims any past guest placeholders
    matching their email or phone number across all groups.
    
    Args:
        name: User's full name or display name
        email: Optional unique email address
        phone: Optional unique phone number
        password: Plain text password (will be securely hashed)
        
    Returns:
        Dict representing newly created user profile.
    """
    name = (name or "").strip()
    if not name:
        raise ValueError("Name is required.")

    clean_email = email.strip().lower() if email and email.strip() else None
    clean_phone = phone.strip() if phone and phone.strip() else None

    if not clean_email and not clean_phone:
        raise ValueError("At least an email address or phone number must be provided.")

    if clean_email and not is_valid_email(clean_email):
        raise ValueError(f"Invalid email address: {clean_email}")

    # Check for existing user with same email or phone
    with get_db_cursor() as (cur, _):
        if clean_email:
            cur.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(%s)", (clean_email,))
            if cur.fetchone():
                raise ValueError("An account with this email address already exists.")
        if clean_phone:
            cur.execute("SELECT id FROM users WHERE phone = %s", (clean_phone,))
            if cur.fetchone():
                raise ValueError("An account with this phone number already exists.")

    password_hash = generate_password_hash(password) if password else None

    # Insert user and execute transactional auto-claim
    with get_db_cursor() as (cur, conn):
        cur.execute(
            """
            INSERT INTO users (name, email, phone, password_hash)
            VALUES (%s, %s, %s, %s)
            """,
            (name, clean_email, clean_phone, password_hash)
        )
        new_user_id = cur.lastrowid

        # Transactional Auto-Claim:
        # Match past guest placeholders by email or phone and assign user_id
        claimed_count = 0
        if clean_email and clean_phone:
            cur.execute(
                """
                UPDATE group_members 
                SET user_id = %s, status = 'active'
                WHERE user_id IS NULL AND (
                    (guest_email IS NOT NULL AND LOWER(guest_email) = %s)
                    OR (guest_phone IS NOT NULL AND guest_phone = %s)
                )
                """,
                (new_user_id, clean_email, clean_phone)
            )
            claimed_count = cur.rowcount
        elif clean_email:
            cur.execute(
                """
                UPDATE group_members 
                SET user_id = %s, status = 'active'
                WHERE user_id IS NULL AND guest_email IS NOT NULL AND LOWER(guest_email) = %s
                """,
                (new_user_id, clean_email)
            )
            claimed_count = cur.rowcount
        elif clean_phone:
            cur.execute(
                """
                UPDATE group_members 
                SET user_id = %s, status = 'active'
                WHERE user_id IS NULL AND guest_phone IS NOT NULL AND guest_phone = %s
                """,
                (new_user_id, clean_phone)
            )
            claimed_count = cur.rowcount

    return {
        "id": new_user_id,
        "name": name,
        "email": clean_email,
        "phone": clean_phone,
        "claimed_placeholders": claimed_count
    }


def authenticate_user(email_or_phone: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Authenticates a user via email or phone + password.
    Returns user dict without password hash if credentials match, else None.
    """
    identifier = (email_or_phone or "").strip().lower()
    if not identifier or not password:
        return None

    query = """
        SELECT id, name, email, phone, password_hash, avatar_url, created_at 
        FROM users 
        WHERE LOWER(email) = %s OR phone = %s
        LIMIT 1
    """
    user = execute_query(query, (identifier, identifier), fetchone=True)
    if not user:
        return None

    stored_hash = user.get("password_hash")
    if not stored_hash or not check_password_hash(stored_hash, password):
        return None

    # Return safe profile
    user_copy = dict(user)
    user_copy.pop("password_hash", None)
    return user_copy


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Fetches user profile by user_id."""
    query = "SELECT id, name, email, phone, avatar_url, created_at FROM users WHERE id = %s"
    return execute_query(query, (user_id,), fetchone=True)


def login_user_session(user: Dict[str, Any]) -> None:
    """Stores user information in the active Flask session."""
    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    session["user_email"] = user.get("email")


def logout_user_session() -> None:
    """Clears user authentication session."""
    session.pop("user_id", None)
    session.pop("user_name", None)
    session.pop("user_email", None)


def login_required(f):
    """
    Decorator for views requiring an active user session.
    Redirects HTML requests to /login or returns 401 JSON for API requests.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"error": "Authentication required", "status": 401}), 401
            return redirect(url_for("auth.login_view", next=request.url))
        return f(*args, **kwargs)
    return decorated_function
