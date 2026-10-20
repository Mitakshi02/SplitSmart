"""
SplitSmart Auth Blueprint Re-export
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.routes.auth import auth_bp

__all__ = ["auth_bp"]
