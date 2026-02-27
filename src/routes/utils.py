from typing import Optional

from flask import abort, jsonify, request
from datetime import datetime, timezone


def success_response(data, message: Optional[str] = None, status: int = 200):
    """Consistent success response envelope."""
    response = {
        "success": True,
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if message:
        response["message"] = message
    return jsonify(response), status


def parse_int(
    v,
    default=None,
    min_val: Optional[int] = None,
    max_val: Optional[int] = None,
    field_name: str = "value",
) -> Optional[int]:
    """Parse an integer with optional range validation."""
    try:
        result = int(v)
        if min_val is not None and result < min_val:
            abort(400, f"{field_name} must be at least {min_val}")
        if max_val is not None and result > max_val:
            abort(400, f"{field_name} cannot exceed {max_val}")
        return result
    except (TypeError, ValueError):
        if default is not None:
            return default
        abort(400, f"Invalid {field_name}: must be a valid integer")


def parse_bool(v, default: bool = False) -> bool:
    """Parse a boolean value from a query string."""
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    return str(v).lower() in ("1", "true", "t", "yes", "y", "on")


def get_current_user_id() -> int:
    """Extract and validate user ID from X-User-Id request header."""
    uid = request.headers.get("X-User-Id")
    if not uid:
        abort(401, "Missing X-User-Id header.")
    try:
        user_id = int(uid)
        if user_id <= 0:
            abort(400, "User ID must be a positive integer.")
        return user_id
    except ValueError:
        abort(400, "Invalid X-User-Id header: must be a positive integer.")
