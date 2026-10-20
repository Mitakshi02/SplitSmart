"""
SplitSmart Groups Blueprint Re-export
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.routes.groups import groups_bp

__all__ = ["groups_bp"]
