import hmac
import ipaddress
import re
from urllib.parse import urlsplit

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import get_settings

bearer = HTTPBearer(auto_error=False)


class ConfiguredTrustedHosts:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        hosts = [v.strip() for v in get_settings().http_allowed_hosts.split(",") if v.strip()]
        await TrustedHostMiddleware(self.app, allowed_hosts=hosts or ["*"], www_redirect=False)(
            scope, receive, send
        )


def authorize(credentials: HTTPAuthorizationCredentials | None, reporting: bool):
    settings = get_settings()
    token = credentials.credentials if credentials else ""
    admin = hmac.compare_digest(token, settings.admin_api_key.get_secret_value())
    report = hmac.compare_digest(token, settings.report_api_key.get_secret_value())
    if not (admin or (reporting and report)):
        raise HTTPException(
            401, "Invalid bearer credential", headers={"WWW-Authenticate": "Bearer"}
        )


def require_admin(credentials=Depends(bearer)):
    authorize(credentials, False)


def require_reporting(credentials=Depends(bearer)):
    authorize(credentials, True)


def validate_destination(value: str) -> str:
    """Validate without DNS/network fetch; preserve the original URL byte-for-byte."""
    if len(value) > 4096 or re.search(r"[\s\x00-\x1f\x7f\\]", value):
        raise ValueError("URL contains whitespace, controls or backslashes")
    if re.search(r"%(?:0[0-9a-f]|1[0-9a-f]|7f)", value, re.I):
        raise ValueError("URL contains encoded control characters")
    try:
        parts = urlsplit(value)
        host = parts.hostname
        port = parts.port
    except ValueError as exc:
        raise ValueError("Invalid URL") from exc
    if parts.scheme.lower() not in {"https", "http"} or not host:
        raise ValueError("A complete HTTP(S) URL is required")
    if parts.username is not None or parts.password is not None:
        raise ValueError("URL credentials are forbidden")
    if port not in {None, 80, 443}:
        raise ValueError("Only public web ports are supported")
    host = host.lower().rstrip(".")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", host) or "." not in host:
            raise ValueError("Use a public ASCII hostname (IDNs must use punycode)") from None
        if len(host) > 253 or any(
            not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
            for label in host.split(".")
        ):
            raise ValueError("Invalid hostname labels") from None
        if host.endswith((".localhost", ".local", ".internal", ".test")):
            raise ValueError("Local destinations are forbidden") from None
        if all(c in "0123456789.xabcdef" for c in host) and re.match(r"^(?:0x|\d)", host):
            raise ValueError("Ambiguous numeric host") from None
    else:
        if not address.is_global:
            raise ValueError("Private or reserved addresses are forbidden")
    allowed = get_settings().allowed_hosts
    if allowed and host not in allowed:
        raise ValueError("Destination host is not allowlisted")
    return value
