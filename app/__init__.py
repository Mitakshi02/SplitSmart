import os
from flask import Flask
from .config import Config

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Ensure uploads directory exists safely
    upload_folder = app.config.get("UPLOAD_FOLDER")
    if upload_folder:
        os.makedirs(upload_folder, exist_ok=True)

    # Register Blueprints
    from .routes.auth import auth_bp
    from .routes.groups import groups_bp
    from .routes.expenses import expenses_bp
    from .routes.fund import fund_bp
    from .routes.settlements import settlements_bp
    from .routes.ai import ai_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(groups_bp)
    app.register_blueprint(expenses_bp)
    app.register_blueprint(fund_bp)
    app.register_blueprint(settlements_bp)
    app.register_blueprint(ai_bp)



    @app.route("/")
    def index():
        from flask import session, redirect, url_for
        if "user_id" in session:
            return redirect(url_for("groups.list_groups_view"))
        return redirect(url_for("auth.login_view"))

    @app.errorhandler(404)
    def page_not_found(e):
        from flask import render_template, request, jsonify
        if request.is_json:
            return jsonify({"error": "Resource not found"}), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        from flask import render_template, request, jsonify
        if request.is_json:
            return jsonify({"error": "Internal server error"}), 500
        return render_template("errors/500.html"), 500

    return app


