"""
SplitSmart Settlements Blueprint Export
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.routes.settlements import settlements_bp

__all__ = ["settlements_bp"]
