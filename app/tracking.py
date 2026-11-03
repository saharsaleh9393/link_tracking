import hashlib
import hmac
import ipaddress
from datetime import datetime
from urllib.parse import unquote_plus, urlencode, urlsplit, urlunsplit

from fastapi import Request
from user_agents import parse

from app.config import get_settings
from app.schemas import UTM_FIELDS


def trusted_peer(request: Request) -> bool:
    try:
        peer = ipaddress.ip_address(request.client.host if request.client else "")
    except ValueError:
        return False
    ranges = get_settings().trusted_proxy_cidrs.split(",")
    return any(peer in ipaddress.ip_network(v.strip()) for v in ranges if v.strip())


def client_address(request: Request) -> str | None:
    address = request.client.host if request.client else ""
    if trusted_peer(request):
        # Walk from the socket towards the client, skipping only explicitly trusted hops.
        hops = request.headers.get("x-forwarded-for", "").split(",") + [address]
        ranges = [
            ipaddress.ip_network(v.strip())
            for v in get_settings().trusted_proxy_cidrs.split(",")
            if v.strip()
        ]
        for hop in reversed(hops):
            try:
                parsed = ipaddress.ip_address(hop.strip())
            except ValueError:
                return None
            if not any(parsed in network for network in ranges):
                return str(parsed)
    try:
        return str(ipaddress.ip_address(address))
    except ValueError:
        return None


def referrer_origin(value: str) -> str | None:
    try:
        parts = urlsplit(value[:4096])
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            return None
        port = parts.port
        host = parts.hostname
        if ":" in host:
            host = f"[{host}]"
        origin = f"{parts.scheme}://{host}" + (f":{port}" if port else "")
        return origin[:300]
    except ValueError:
        return None


def collect_metadata(request: Request, now: datetime) -> dict:
    agent = request.headers.get("user-agent", "")[:1024]
    ua = parse(agent)
    lowered = agent.lower()
    bot = ua.is_bot or any(
        word in lowered
        for word in (
            "bot",
            "crawler",
            "spider",
            "preview",
            "facebookexternalhit",
            "headless",
            "curl/",
            "python-requests",
        )
    )
    classification = "bot" if bot else ("human" if ua.browser.family != "Other" else "unknown")
    device = (
        "tablet"
        if ua.is_tablet
        else "mobile"
        if ua.is_mobile
        else "desktop"
        if ua.is_pc
        else "other"
    )
    address = client_address(request)
    digest = None
    if address:
        material = f"{now.date().isoformat()}|{address}|{ua.os.family}|{ua.browser.family}|{device}"
        digest = hmac.new(
            get_settings().visitor_hmac_key.get_secret_value().encode(),
            material.encode(),
            hashlib.sha256,
        ).hexdigest()
    country = None
    header = get_settings().country_header
    if header and trusted_peer(request):
        value = request.headers.get(header, "").upper()
        # ISO country codes; reject edge sentinels and arbitrary two-letter strings.
        if value in COUNTRY_CODES:
            country = value
    return {
        "device": device,
        "os": ua.os.family[:100],
        "browser": ua.browser.family[:100],
        "classification": classification,
        "bot_reason": "user-agent" if bot else None,
        "country": country,
        "referrer_origin": referrer_origin(request.headers.get("referer", "")),
        "visitor_digest": digest,
    }


COUNTRY_CODES = set(
    "AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM JO JP KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI VN VU WF WS YE YT ZA ZM ZW".split()
)


def effective_utms(link: dict, request: Request) -> dict:
    return {key: request.query_params.get(key, link.get(key)) for key in UTM_FIELDS}


def redirect_url(destination: str, utms: dict, forward: bool) -> str:
    if not forward:
        return destination
    parts = urlsplit(destination)
    # Existing query bytes stay untouched; never replace destination-owned parameters.
    existing = {unquote_plus(pair.split("=", 1)[0]) for pair in parts.query.split("&")}
    additions = {
        key: value for key, value in utms.items() if value is not None and key not in existing
    }
    if not additions:
        return destination
    query = parts.query + ("&" if parts.query else "") + urlencode(additions)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))
