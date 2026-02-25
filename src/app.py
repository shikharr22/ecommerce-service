from flask import Flask, jsonify
from sqlalchemy import text

from src.db import engine
# Importing models registers them with Base.metadata — required before any
# ORM operation or schema introspection.
import src.models  # noqa: F401


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
    # Blueprints                                                           #
    # Each domain gets its own Blueprint registered with a URL prefix.    #
    # The actual route handlers will be added in Phase 2.                 #
    # ------------------------------------------------------------------ #
    # from src.routes.products import products_bp
    # app.register_blueprint(products_bp, url_prefix="/api/v1/products")
    #
    # from src.routes.orders import orders_bp
    # app.register_blueprint(orders_bp, url_prefix="/api/v1/orders")

    # ------------------------------------------------------------------ #
    # Request teardown                                                     #
    # ------------------------------------------------------------------ #
    @app.teardown_appcontext
    def close_db_session(exception: BaseException | None) -> None:
        """
        Called automatically after every request context is popped.
        Sessions are managed per-request via get_db(); nothing to clean up
        at the app-context level beyond this hook existing as an extension
        point for future scoped session support.
        """
        pass

    # ------------------------------------------------------------------ #
    # Health check                                                         #
    # ------------------------------------------------------------------ #
    @app.get("/health")
    def health() -> tuple:
        """
        Liveness + readiness probe.

        Returns 200 if the app is running and can reach the database.
        Returns 503 if the database is unreachable.

        Useful for:
        - Docker / Kubernetes health checks
        - Verifying the app wired up correctly after deployment
        """
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return jsonify({"status": "ok", "database": "reachable"}), 200
        except Exception as exc:
            return jsonify({"status": "error", "database": str(exc)}), 503

    return app
