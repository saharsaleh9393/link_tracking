"""URL normalization and routing policy; no DNS probes or per-click network calls."""

import ipaddress
import re
from urllib.parse import urlsplit

from app.config import get_settings

# First path segments owned by the API, dashboard or common web infrastructure.
RESERVED = frozenset(
    {
        "api",
        "health",
        "metrics",
        "docs",
        "redoc",
        "openapi.json",
        "openapi",
        "overview",
        "campaigns",
        "links",
        "destinations",
        "analytics",
        "clicks",
        "settings",
        "login",
        "logout",
        "_next",
        "static",
        "assets",
        "public",
        "favicon.ico",
        "robots.txt",
        "sitemap.xml",
        ".well-known",
        "r",
    }
)


def normalize_base(value: str) -> str:
    value = value.strip()
    if any(c.isspace() or ord(c) < 32 for c in value) or any(c in value for c in "\\%?#"):
        raise ValueError(
            "Use a plain HTTP(S) origin without paths, credentials or query parameters"
        )
    try:
        url = urlsplit(value)
        host = (url.hostname or "").encode("idna").decode("ascii").lower()
        port = url.port
    except (ValueError, UnicodeError):
        raise ValueError("Invalid domain or port") from None
    if (
        url.scheme not in {"http", "https"}
        or not host
        or url.username is not None
        or url.password is not None
        or url.path not in {"", "/"}
        or port == 0
        or url.netloc.endswith(":")
    ):
        raise ValueError("Use an HTTP(S) origin without paths or credentials")
    try:
        address = ipaddress.ip_address(host)
        local = address.is_loopback
        host = f"[{address.compressed}]" if address.version == 6 else address.compressed
    except ValueError:
        local = host == "localhost"
        if not local and (
            len(host) > 253
            or "." not in host
            or any(
                not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", part)
                for part in host.split(".")
            )
        ):
            raise ValueError("Use a valid domain, IP address or localhost") from None
    if url.scheme == "http" and not local:
        raise ValueError("Public link domains require HTTPS; HTTP is allowed for localhost only")
    port_suffix = f":{port}" if port and port != (443 if url.scheme == "https" else 80) else ""
    return f"{url.scheme}://{host}{port_suffix}"


def normalize_prefix(value: str) -> str:
    value = value.strip().strip("/").lower()
    if value and (
        not re.fullmatch(r"[a-z0-9_-]{1,50}", value)
        or value.startswith("_")
        or value in RESERVED - {"r"}
    ):
        raise ValueError("Use one unreserved path segment (r, go, custom), or leave empty")
    return value


def origins(value: str) -> set[str]:
    result = set()
    for item in value.split(","):
        if item.strip():
            try:
                result.add(normalize_base(item))
            except ValueError:
                continue  # Malformed operator entries fail closed.
    return result


def root_allowed(base_url: str) -> bool:
    return base_url in origins(get_settings().linkspace_root_origins)


def configuration_status(base_url: str) -> str:
    settings = get_settings()
    url = urlsplit(base_url)
    public = urlsplit(settings.public_base_url)
    if url.hostname in {"localhost", "127.0.0.1", "::1"} and url.port == public.port:
        return "local_development"
    if base_url in origins(settings.linkspace_routed_origins):
        return "operator_configured"
    return "pending_configuration"


def tracking_url(base_url: str, prefix: str, slug: str) -> str:
    return "/".join(part for part in (base_url.rstrip("/"), prefix, slug) if part)


def matches_route(link: dict, path: str, host: str) -> bool:
    base = link.get("tracking_base_url") or get_settings().public_base_url
    prefix = link.get("tracking_path_prefix")
    prefix = "r" if prefix is None else prefix
    url = urlsplit(base)
    try:
        incoming = normalize_base(f"{url.scheme}://{host}")
    except ValueError:
        return False
    if incoming != base or path != "/".join(p for p in (prefix, link["slug"]) if p):
        return False
    return bool(prefix) or root_allowed(base)
