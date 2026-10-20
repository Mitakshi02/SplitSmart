"""
SplitSmart AI Blueprint Export
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.routes.ai import ai_bp

__all__ = ["ai_bp"]
