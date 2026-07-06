from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed


@dataclass(frozen=True)
class SignedUser:
    username: str

    @property
    def is_authenticated(self) -> bool:
        return True


def create_access_token(username: str) -> str:
    return TimestampSigner(salt="intgest-reports-auth").sign(username)


def verify_access_token(token: str) -> SignedUser:
    signer = TimestampSigner(salt="intgest-reports-auth")
    try:
        username = signer.unsign(
            token,
            max_age=settings.INTGEST_AUTH_TOKEN_TTL_SECONDS,
        )
    except SignatureExpired as exc:
        raise AuthenticationFailed("Sessao expirada.") from exc
    except BadSignature as exc:
        raise AuthenticationFailed("Token invalido.") from exc
    return SignedUser(username=username)


class SignedTokenAuthentication(BaseAuthentication):
    keyword = "Bearer"

    def authenticate(self, request):
        raw_header = get_authorization_header(request).decode("utf-8")
        if not raw_header:
            return None

        parts = raw_header.split()
        if len(parts) != 2 or parts[0] != self.keyword:
            raise AuthenticationFailed("Use Authorization: Bearer <token>.")

        user = verify_access_token(parts[1])
        return user, parts[1]
