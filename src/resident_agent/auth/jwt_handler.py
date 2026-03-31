"""JWT handling for Resident Agent authentication."""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import structlog

from jose import JWTError, jwt

from resident_agent.core.config import Settings
from resident_agent.core.exceptions import AuthenticationError

logger = structlog.get_logger()


class JWTHandler:
    """JWT token creation and validation."""

    ALGORITHM = "HS256"

    def __init__(self, settings: Optional[Settings] = None):
        """Initialize JWT handler.

        Args:
            settings: Application settings (uses default if not provided)
        """
        self.settings = settings or Settings.get()

    def create_access_token(
        self,
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None,
    ) -> str:
        """Create a JWT access token.

        Args:
            data: Payload data to encode (typically {"sub": user_id, ...})
            expires_delta: Custom expiration time

        Returns:
            Encoded JWT string
        """
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(
                minutes=self.settings.jwt_access_token_expire_minutes
            )

        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "iss": "resident-agent",
        })

        encoded_jwt = jwt.encode(
            to_encode,
            self.settings.jwt_secret_key,
            algorithm=self.ALGORITHM,
        )

        logger.debug(
            "access_token_created",
            subject=data.get("sub"),
            expires_at=expire.isoformat(),
        )

        return encoded_jwt

    def create_refresh_token(
        self,
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None,
    ) -> str:
        """Create a JWT refresh token.

        Args:
            data: Payload data to encode
            expires_delta: Custom expiration time

        Returns:
            Encoded JWT string
        """
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(
                days=self.settings.jwt_refresh_token_expire_days
            )

        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "iss": "resident-agent",
            "type": "refresh",
        })

        encoded_jwt = jwt.encode(
            to_encode,
            self.settings.jwt_secret_key,
            algorithm=self.ALGORITHM,
        )

        logger.debug(
            "refresh_token_created",
            subject=data.get("sub"),
            expires_at=expire.isoformat(),
        )

        return encoded_jwt

    def decode_token(self, token: str) -> Dict[str, Any]:
        """Decode and validate a JWT token.

        Args:
            token: JWT token string

        Returns:
            Decoded payload dict

        Raises:
            AuthenticationError: If token is invalid or expired
        """
        try:
            payload = jwt.decode(
                token,
                self.settings.jwt_secret_key,
                algorithms=[self.ALGORITHM],
                issuer="resident-agent",
            )
            logger.debug("token_decoded", subject=payload.get("sub"))
            return payload

        except JWTError as e:
            logger.warning("token_decode_failed", error=str(e))
            raise AuthenticationError(f"Invalid token: {str(e)}")

    def get_token_expiry(self, token: str) -> Optional[datetime]:
        """Get the expiration time of a token.

        Args:
            token: JWT token string

        Returns:
            Expiration datetime or None if invalid
        """
        try:
            payload = self.decode_token(token)
            exp = payload.get("exp")
            if exp:
                return datetime.fromtimestamp(exp)
        except AuthenticationError:
            pass
        return None

    def get_access_token_expires_in(self) -> int:
        """Get access token expiration time in seconds.

        Returns:
            Expiration time in seconds
        """
        return self.settings.jwt_access_token_expire_minutes * 60
