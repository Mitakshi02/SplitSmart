"""
SplitSmart Fund Blueprint Export
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.routes.fund import fund_bp

__all__ = ["fund_bp"]
