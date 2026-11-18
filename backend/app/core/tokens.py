from datetime import UTC, datetime
from typing import Literal, TypeVar
from uuid import uuid4

from jose import JWTError, jwt
from pydantic import BaseModel, ValidationError

from app.core.config import Settings
from app.core.exceptions import BizException


class TokenClaims(BaseModel):
    sub: str
    jti: str
    exp: int


class AccessClaims(TokenClaims):
    kind: Literal["access"]
    refresh_jti: str
    refresh_exp: int


class RefreshClaims(TokenClaims):
    kind: Literal["refresh"]


Claims = TypeVar("Claims", bound=TokenClaims)


class TokenIssuer:
    def __init__(self, settings: Settings) -> None:
        self.secret = settings.jwt_secret.get_secret_value()
        self.algorithm = settings.jwt_alg
        self.access_seconds = settings.access_token_expire_min * 60
        self.refresh_seconds = settings.refresh_token_expire_day * 86400

    def decode(self, raw: str, claims: type[Claims]) -> Claims:
        try:
            if not self.secret:
                raise JWTError("JWT secret is missing")
            payload = jwt.decode(
                raw,
                self.secret,
                algorithms=[self.algorithm],
                options={"require_sub": True, "require_jti": True, "require_exp": True},
            )
            token = claims.model_validate(payload, strict=True)
            if token.exp <= int(datetime.now(UTC).timestamp()):
                raise JWTError("Token has expired")
            return token
        except (JWTError, ValidationError, TypeError) as exc:
            raise BizException(1002, "未登录或登录凭证已失效") from exc

    def issue(self, subject: str) -> dict:
        if not self.secret:
            raise BizException(5001, "认证服务尚未配置签名密钥")
        now = int(datetime.now(UTC).timestamp())
        refresh = RefreshClaims(
            kind="refresh", sub=subject, jti=uuid4().hex, exp=now + self.refresh_seconds
        )
        access = AccessClaims(
            kind="access",
            sub=subject,
            jti=uuid4().hex,
            exp=now + self.access_seconds,
            refresh_jti=refresh.jti,
            refresh_exp=refresh.exp,
        )
        return {
            "accessToken": jwt.encode(access.model_dump(), self.secret, algorithm=self.algorithm),
            "refreshToken": jwt.encode(refresh.model_dump(), self.secret, algorithm=self.algorithm),
            "expiresIn": self.access_seconds,
        }
