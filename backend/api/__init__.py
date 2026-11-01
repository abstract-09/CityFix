from .admin import bp as admin_bp
from .authority import bp as authority_bp
from .public import bp as public_bp

ALL_BLUEPRINTS = (public_bp, authority_bp, admin_bp)
