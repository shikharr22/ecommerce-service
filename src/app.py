import logging
from datetime import datetime, timezone

from flask import Flask, jsonify
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from db import engine
from routes.products import products_bp
from routes.cart import cart_bp
from routes.orders import orders_bp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)


def create_app() -> Flask:
    """
    Application factory.

    Why a factory instead of a module-level `app = Flask(__name__)`?
    - Tests can call create_app() multiple times with different configs,
      each getting a fully isolated Flask instance.
    - Avoids circular import issues that arise when blueprints and extensions
      all import a single shared `app` object.
    """
    app = Flask(__name__)

    # ------------------------------------------------------------------ #
    # Blueprints — each domain registered under /api/v1/                  #
    # ------------------------------------------------------------------ #
    app.register_blueprint(products_bp, url_prefix="/api/v1/products")
    app.register_blueprint(cart_bp,     url_prefix="/api/v1/carts")
    app.register_blueprint(orders_bp,   url_prefix="/api/v1/orders")

    # ------------------------------------------------------------------ #
    # Error handlers — consistent JSON error envelope                     #
    # ------------------------------------------------------------------ #
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"success": False, "error": str(e.description)}), 400

    @app.errorhandler(401)
    def unauthorized(e):
        return jsonify({"success": False, "error": str(e.description)}), 401

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"success": False, "error": str(e.description)}), 404

    @app.errorhandler(SQLAlchemyError)
    def db_error(e):
        return jsonify({"success": False, "error": "A database error occurred."}), 500

    @app.errorhandler(500)
    def internal_error(e):
        return jsonify({"success": False, "error": "An internal server error occurred."}), 500

    # ------------------------------------------------------------------ #
    # Health check                                                         #
    # ------------------------------------------------------------------ #
    @app.get("/health")
    def health():
        """Liveness + readiness probe. Returns 503 if DB is unreachable."""
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return jsonify({
                "status": "ok",
                "database": "reachable",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }), 200
        except Exception as exc:
            return jsonify({"status": "error", "database": str(exc)}), 503

    return app


if __name__ == "__main__":
    application = create_app()
    application.run(debug=True, host="0.0.0.0", port=5000)

