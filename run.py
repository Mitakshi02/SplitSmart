"""
SplitSmart Application Launcher
Launches the full Flask application with all AI services, debt engines, and database pools.
"""

import os
import sys
from app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "127.0.0.1")
    debug = os.environ.get("FLASK_DEBUG", "1") in ("1", "true", "True")

    use_reloader = os.environ.get("FLASK_USE_RELOADER", "0") in ("1", "true", "True")

    print("=" * 60)
    print(" SplitSmart • AI-Assisted Expense Sharing & Settlement Engine")
    print(f" Server running at: http://{host}:{port}/")
    print(f" Debug mode: {'ENABLED' if debug else 'DISABLED'}")
    print(f" Watchdog Reloader: {'ENABLED' if use_reloader else 'DISABLED'}")
    print("=" * 60)

    app.run(host=host, port=port, debug=debug, use_reloader=use_reloader)
