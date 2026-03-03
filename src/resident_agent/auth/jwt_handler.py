"""JWT token generation and validation handler."""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import hashlib
import secrets
import hmac
import jwt

from ..core.config import Settings


class JWTHandler:
    """Handle JWT token creation, validation, and password hashing."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def create_access_token(
        self,
        user_id: str,
        role: str = "resident",
        additional_claims: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a JWT access token.

        Args:
            user_id: User identifier
            role: User role (resident, staff, admin)
            additional_claims: Extra claims to include in token

        Returns:
            Encoded JWT access token
        """
        expire = datetime.utcnow() + timedelta(minutes=self.settings.access_token_expire_minutes)

        payload = {
            "sub": user_id,
            "role": role,
            "exp": expire.timestamp(),
            "iat": datetime.utcnow().timestamp(),
            "type": "access"
        }

        # Add any additional claims
        if additional_claims:
            payload.update(additional_claims)

        return jwt.encode(payload, self.settings.secret_key, algorithm="HS256")

    def create_refresh_token(self, user_id: str) -> str:
        """Create a JWT refresh token.

        Args:
            user_id: User identifier

        Returns:
            Encoded JWT refresh token
        """
        expire = datetime.utcnow() + timedelta(days=self.settings.refresh_token_expire_days)

        payload = {
            "sub": user_id,
            "exp": expire.timestamp(),
            "iat": datetime.utcnow().timestamp(),
            "type": "refresh"
        }

        return jwt.encode(payload, self.settings.secret_key, algorithm="HS256")

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode a JWT token.

        Args:
            token: JWT token string

        Returns:
            Decoded payload if valid, None if invalid or expired
        """
        try:
            payload = jwt.decode(
                token,
                self.settings.secret_key,
                algorithms=["HS256"]
            )

            # Check expiration
            if payload.get("exp") and payload["exp"] < datetime.utcnow().timestamp():
                return None  # Token has expired

            return payload

        except jwt.InvalidTokenError:
            return None
        except jwt.ExpiredSignatureError:
            return None
        except Exception:
            return None

    def hash_password(self, password: str) -> str:
        """Hash a password using SHA-256 with random salt.

        Args:
            password: Plain text password

        Returns:
            Hashed password string in format: salt$hash
        """
        salt = secrets.token_hex(16)
        hash_value = hashlib.sha256((salt + password).encode()).hexdigest()
        return f"{salt}${hash_value}"

    def verify_password(self, password: str, hashed: str) -> bool:
        """Verify a password against a hash.

        Args:
            password: Plain text password to verify
            hashed: Hashed password to compare against (salt$hash format)

        Returns:
            True if password matches, False otherwise
        """
        try:
            salt, stored_hash = hashed.split("$")
            computed_hash = hashlib.sha256((salt + password).encode()).hexdigest()
            return hmac.compare_digest(computed_hash, stored_hash)
        except Exception:
            return False
