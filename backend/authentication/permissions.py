"""
Custom authentication for file downloads.

Browsers cannot send custom headers on direct navigation (window.open / <a> tags),
so JWT-protected downloads (PDF/Excel/CSV) need an alternative: a `token` query param.

This authentication class checks the query string ONLY if no Authorization
header is present, validates it as a real SimpleJWT access token, and attaches
the corresponding user to the request — exactly like header-based auth would.

Security note: this does NOT weaken the existing header-based JWT auth. It is
an additive fallback used only by views that explicitly include it, such as
file export endpoints accessed via window.open().
"""

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


class QueryParamJWTAuthentication(JWTAuthentication):
    """
    Allows JWT authentication via ?token=<access_token> in the URL,
    falling back to the standard Authorization header if present.
    """

    def authenticate(self, request):
        # 1. Try standard header-based auth first (unchanged behavior)
        header_auth = super().authenticate(request)
        if header_auth is not None:
            return header_auth

        # 2. Fallback: look for ?token= in the query string
        raw_token = request.query_params.get('token')
        if not raw_token:
            return None

        try:
            validated_token = self.get_validated_token(raw_token)
            user = self.get_user(validated_token)
        except (InvalidToken, TokenError):
            return None

        return (user, validated_token)