"""Opt-in synthetic smoke checks through the public proxy, using protected local inputs."""

import argparse
import json
import uuid
from datetime import UTC, datetime, timedelta
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


class SmokeFailure(RuntimeError):
    """A fixed diagnostic safe to print without response bodies or secrets."""


def read_env(path):
    return {
        key.strip(): value.strip().strip("\"'")
        for line in path.read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
        for key, _, value in [line.partition("=")]
    }


def run(env_path, connect_url=None, prepare_simulation_default=False):
    env = read_env(env_path)
    if connect_url and env["APP_ENV"] != "simulation":
        raise ValueError("Connection override is only for local simulation")
    if prepare_simulation_default and env["APP_ENV"] != "simulation":
        raise ValueError("Test-default preparation is only for an isolated simulation")
    directory = env_path.parent / env["SECRETS_DIRECTORY"]
    password = (directory / "dashboard_password").read_text().strip()
    report_key = (directory / "report_api_key").read_text().strip()
    dashboard, public = env["DASHBOARD_ORIGIN"], env["PUBLIC_BASE_URL"]
    opener = build_opener(NoRedirect())
    session = ""

    def call(
        origin, path, method="GET", body=None, headers=None, expected=200, authenticated=False
    ):
        request_headers = {"Host": urlsplit(origin).netloc, **(headers or {})}
        if body is not None:
            request_headers["Content-Type"] = "application/json"
        if authenticated:
            request_headers.update({"Cookie": session, "Origin": dashboard})
        request = Request(
            (connect_url or origin).rstrip("/") + path,
            method=method,
            headers=request_headers,
            data=json.dumps(body).encode() if body is not None else None,
        )
        try:
            response = opener.open(request, timeout=15)
        except HTTPError as exc:
            response = exc
        data = response.read()
        if response.status != expected:
            raise SmokeFailure(f"Unexpected HTTP status {response.status} during {method}")
        return response.headers, json.loads(
            data
        ) if data and "application/json" in response.headers.get("Content-Type", "") else data

    def api(path, method="GET", body=None, expected=200):
        return call(
            dashboard, "/api/tracker/" + path, method, body, expected=expected, authenticated=True
        )[1]

    call(dashboard, "/health/live")
    call(dashboard, "/api/tracker/links", expected=401)
    login_headers, _ = call(
        dashboard, "/api/auth", "POST", {"password": password}, {"Origin": dashboard}
    )
    cookie = SimpleCookie()
    cookie.load(login_headers["Set-Cookie"])
    token = cookie["linkspace_session"]
    assert token["httponly"] and token["samesite"].lower() == "strict"
    assert bool(token["secure"]) == (env["APP_ENV"] == "production")
    session = "linkspace_session=" + token.value
    call(
        dashboard,
        "/api/tracker/links",
        "POST",
        {},
        {"Origin": "https://evil.invalid", "Cookie": session},
        expected=403,
    )
    print("PASS login_session_and_cross_origin_protection")
    run_id = uuid.uuid4().hex[:12]
    campaign = api("campaigns", "POST", {"name": "Deployment smoke " + run_id}, expected=201)
    links = []
    window = {
        "start": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
        "end": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
    }
    destination = "https://example.com/smoke?signature=a%2Fb&keep=one%20two#part"

    def create_and_check(base, space=None):
        body = {
            "destination_url": destination,
            "campaign_id": campaign["id"],
            "slug": "smoke-" + uuid.uuid4().hex[:16],
            "utm_source": "deployment-smoke",
            "forward_utm": True,
        }
        if space:
            body["linkspace_id"] = space["id"]
        link = api("links", "POST", body, expected=201)
        links.append(link)

        def origin(value):
            parts = urlsplit(value)
            return (
                parts.scheme,
                parts.hostname,
                parts.port or (443 if parts.scheme == "https" else 80),
            )

        if origin(link["tracking_url"]) != origin(base):
            raise SmokeFailure(
                "Default Linkspace origin differs; select a correctly routed default"
            )
        path = urlsplit(link["tracking_url"]).path
        expected_location = destination.replace("#part", "&utm_source=smoke-check#part")
        headers, _ = call(
            base,
            path + "?utm_source=smoke-check&preserve=a%2Fb",
            headers={
                "X-Forwarded-For": "1.1.1.1",
                "X-Forwarded-Proto": "https",
                "CF-IPCountry": "IR",
            },
            expected=302,
        )
        assert headers["Location"] == expected_location
        call(base, path, method="HEAD", expected=302)
        summary = api("analytics/summary?" + urlencode({**window, "link_id": link["id"]}))
        assert summary["total_clicks"] == 1
        rows = api("exports/clicks?" + urlencode({**window, "link_id": link["id"]}))["items"]
        assert len(rows) == 1 and rows[0]["utm_source"] == "smoke-check"
        assert "visitor_digest" not in rows[0] and "ip" not in rows[0]
        return link

    def space_for(base, prefix):
        existing = api("linkspaces?limit=500")
        for space in existing:
            if space["base_url"] == base and space["path_prefix"] == prefix:
                return space
        result = api(
            "linkspaces",
            "POST",
            {
                "name": "Deployment smoke " + (prefix or "root"),
                "base_url": base,
                "path_prefix": prefix,
            },
            expected=201,
        )
        return result

    try:
        if prepare_simulation_default:
            space = space_for(public, "r")
            values = {
                key: space[key]
                for key in ("name", "base_url", "path_prefix", "is_active", "is_default")
            }
            api(
                "linkspaces/" + space["id"],
                "PUT",
                {**values, "is_active": True, "is_default": True},
            )
            print("PASS isolated_simulation_default_prepared")
        create_and_check(public)
        print("PASS default_link_redirect_tracking_analytics")
        prefixed = space_for(public, "smoke-" + run_id)
        link = create_and_check(public, prefixed)
        assert link["tracking_url"].startswith(public + "/smoke-" + run_id + "/")
        print("PASS custom_prefix_and_host_query_preservation")
        shared = space_for(dashboard, "r")
        create_and_check(dashboard, shared)
        print("PASS shared_dashboard_domain_legacy_prefix")
        root_enabled = env["APP_ENV"] == "simulation" or public in env.get(
            "LINKSPACE_ROOT_ORIGINS", ""
        ).split(",")
        if root_enabled:
            root = space_for(public, "")
            create_and_check(public, root)
            print("PASS dedicated_prefixless_redirect")
        else:
            print("SKIP prefixless_redirect_operator_approval_required")
        query = urlencode(window)
        call(
            public,
            "/api/v1/analytics/summary?" + query,
            headers={"Authorization": "Bearer " + report_key},
        )
        call(public, "/api/v1/links", expected=404)
        headers, _ = call(
            public,
            "/api/v1/analytics/summary?" + query,
            "OPTIONS",
            headers={"Origin": "https://evil.invalid", "Access-Control-Request-Method": "GET"},
            expected=404,
        )
        assert "Access-Control-Allow-Origin" not in headers
        print("PASS public_read_only_api_and_private_management_boundary")
    finally:
        for link in links:
            api("links/" + link["id"], "DELETE", expected=204)
        api("campaigns/" + campaign["id"], "PATCH", {"archived": True})
    print("PASS synthetic_records_archived_and_links_disabled")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--connect-url")
    parser.add_argument(
        "--prepare-simulation-default",
        action="store_true",
        help="On an isolated restored simulation only, select a test default without rewriting old links",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Required: creates labeled synthetic records and retained clicks",
    )
    args = parser.parse_args()
    if not args.write:
        parser.error("Pass --write to authorize synthetic records")
    try:
        run(args.env_file.resolve(), args.connect_url, args.prepare_simulation_default)
    except SmokeFailure as exc:
        parser.exit(1, f"Smoke failed: {exc}.\n")
    except Exception as exc:
        parser.exit(
            1, f"Smoke failed ({type(exc).__name__}). Check service health and sanitized logs.\n"
        )


if __name__ == "__main__":
    main()
