from __future__ import annotations

import hmac

from django.conf import settings
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from reports.serializers import LoginSerializer
from reports.utils.auth import create_access_token


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        username = serializer.validated_data["username"]
        password = serializer.validated_data["password"]

        valid_user = hmac.compare_digest(username, settings.INTGEST_ADMIN_USER)
        valid_password = hmac.compare_digest(password, settings.INTGEST_ADMIN_PASSWORD)
        if not (valid_user and valid_password):
            return Response({"detail": "Credenciais invalidas."}, status=401)

        return Response(
            {
                "access": create_access_token(username),
                "user": {"username": username},
                "expires_in": settings.INTGEST_AUTH_TOKEN_TTL_SECONDS,
            }
        )


class MeView(APIView):
    def get(self, request):
        return Response({"user": {"username": request.user.username}})
