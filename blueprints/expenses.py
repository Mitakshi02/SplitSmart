"""
SplitSmart Expenses Blueprint Export
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.routes.expenses import expenses_bp

__all__ = ["expenses_bp"]
