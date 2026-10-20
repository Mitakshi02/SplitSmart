"""
SplitSmart Blueprints Package
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.routes.auth import auth_bp
from app.routes.groups import groups_bp
from app.routes.expenses import expenses_bp
from app.routes.fund import fund_bp
from app.routes.settlements import settlements_bp
from app.routes.ai import ai_bp

__all__ = ["auth_bp", "groups_bp", "expenses_bp", "fund_bp", "settlements_bp", "ai_bp"]


