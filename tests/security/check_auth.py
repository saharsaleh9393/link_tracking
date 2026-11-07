"""Non-destructive HTTP auth checks on a newly initialized security-test project only."""

import argparse
import base64
import hashlib
import hmac
import json
import os
import subprocess
import time
import traceback
from http.cookies import SimpleCookie
from pathlib import Path

REQUEST_CODE = """import http.client,json,sys
r=json.load(sys.stdin)
c=http.client.HTTPConnection('proxy',r['port'],timeout=15)
c.request(r['method'],r['path'],body=r.get('body'),headers=r['headers'])
s=c.getresponse()
print(json.dumps({'status':s.status,'headers':dict(s.getheaders()),'body':s.read().decode()}))
"""


def read_env(path):
    return {
        key.strip(): value.strip().strip("\"'")
        for line in path.read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
        for key, _, value in [line.partition("=")]
    }


def check(env_path):
    env = read_env(env_path)
    if not env["COMPOSE_PROJECT_NAME"].startswith("linkspace-security") or not env[
        "POSTGRES_DB"
    ].startswith("security_test"):
        raise ValueError("Refusing to test an existing production/simulation project")
    directory = env_path.parent / env["SECRETS_DIRECTORY"]
    password = (directory / "dashboard_password").read_text().strip()
    signing = (directory / "dashboard_session_secret").read_text().strip()
    origin = env["DASHBOARD_ORIGIN"]
    host = origin.split("://", 1)[1]
    command = [
        "docker",
        "compose",
        "-p",
        env["COMPOSE_PROJECT_NAME"],
        "--env-file",
        str(env_path),
        "-f",
        "compose.production.yaml",
        "-f",
        "compose.simulation.yaml",
        "-f",
        "compose.security-test.yaml",
    ]

    environment = {key: value for key, value in os.environ.items() if key not in env}

    def docker(*args):
        result = subprocess.run(
            [*command, *args], capture_output=True, text=True, timeout=90, env=environment
        )
        if result.returncode:
            raise RuntimeError("Security test container command failed")
        return result.stdout

    def call(
        client="client_a",
        instance=1,
        method="GET",
        path="/api/tracker/management/overview",
        body=None,
        token=None,
        extra=None,
        raw=None,
    ):
        headers = {"Host": host, "Origin": origin, **(extra or {})}
        if token:
            headers["Cookie"] = "linkspace_session=" + token
        if body is not None or raw is not None:
            headers["Content-Type"] = "application/json"
        payload = {
            "port": 80 if instance == 1 else 8082,
            "method": method,
            "path": path,
            "headers": headers,
            "body": raw if raw is not None else json.dumps(body) if body is not None else None,
        }
        result = subprocess.run(
            [*command, "exec", "-T", client, "python", "-c", REQUEST_CODE],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=30,
            env=environment,
        )
        if result.returncode:
            raise RuntimeError("Private HTTP test transport failed")
        response = json.loads(result.stdout)
        response["headers"] = {key.lower(): value for key, value in response["headers"].items()}
        if (
            "x-linkspace-proxy-token" in response["headers"]
            or password in response["body"]
            or signing in response["body"]
        ):
            raise RuntimeError("Sensitive auth data was exposed")
        return response

    def login(client="client_a", instance=1, value=password, extra=None):
        return call(client, instance, "POST", "/api/auth", {"password": value}, extra=extra)

    def cookie(response):
        parsed = SimpleCookie()
        parsed.load(response["headers"]["set-cookie"])
        value = parsed["linkspace_session"]
        assert (
            value["httponly"]
            and value["samesite"].lower() == "strict"
            and int(value["max-age"]) == 28800
        )
        return value.value

    time.sleep(4.1)  # Let any earlier startup smoke limiter window expire; no DB reset.
    assert call()["status"] == 401
    signed_in = login()
    assert signed_in["status"] == 200
    token = cookie(signed_in)
    assert call(token=token)["status"] == 200
    cross_status = call(instance=2, token=token)["status"]
    print(f"Cross-instance protected HTTP status: {cross_status}", flush=True)
    assert cross_status == 200
    for route in (
        "overview",
        "campaigns",
        "links",
        "destinations",
        "analytics",
        "clicks",
        "settings/links",
    ):
        assert call(path="/" + route, token=token)["status"] == 200
    assert call(instance=2, method="DELETE", path="/api/auth", token=token)["status"] == 200
    for instance in (1, 2):
        assert call(instance=instance, token=token)["status"] == 401
        for route in (
            "overview",
            "campaigns",
            "links",
            "destinations",
            "analytics",
            "clicks",
            "settings/links",
        ):
            response = call(instance=instance, path="/" + route, token=token)
            assert response["status"] in (302, 303, 307, 308) and "/login" in response[
                "headers"
            ].get("location", "")
    assert call(token=token + "tampered")["status"] == 401
    payload = base64.urlsafe_b64encode(
        json.dumps(
            {"expires": int(time.time() * 1000) - 1000, "nonce": "a" * 32}, separators=(",", ":")
        ).encode()
    ).rstrip(b"=")
    signature = base64.urlsafe_b64encode(
        hmac.new(signing.encode(), payload, hashlib.sha256).digest()
    ).rstrip(b"=")
    expired = (payload + b"." + signature).decode()
    assert call(token=expired)["status"] == 401
    print("PASS login_cross_instance_validation_logout_and_old_cookie_replay_denied", flush=True)

    time.sleep(4.1)
    for raw in ("{", "null", "[]"):
        assert call(method="POST", path="/api/auth", raw=raw)["status"] == 422
    wrong = login(value="wrong-password")
    assert wrong["status"] == 401
    limited = login(
        instance=2,
        value="wrong-password",
        extra={
            "X-Forwarded-For": "8.8.8.8",
            "X-Linkspace-Client-IP": "8.8.8.8",
            "X-Linkspace-Proxy-Token": "spoofed",
        },
    )
    assert limited["status"] == 429 and 1 <= int(limited["headers"]["retry-after"]) <= 4
    assert login(client="client_b")["status"] == 200
    docker("restart", "web2")
    for _ in range(30):
        if call(instance=2, path="/health/live")["status"] == 200:
            break
        time.sleep(1)
    else:
        raise RuntimeError("Second web instance did not recover")
    # Window may expire during restart; exhaust it again then verify on the other instance.
    time.sleep(4.1)
    for _ in range(4):
        assert login(instance=2, value="wrong-password")["status"] == 401
    assert login()["status"] == 429
    assert login(client="client_b")["status"] == 200
    print("PASS shared_rate_limit_client_isolation_spoof_rejection_and_restart", flush=True)

    time.sleep(4.1)
    assert login(extra={"Origin": "https://evil.invalid"})["status"] == 403
    signed_in = login()
    assert signed_in["status"] == 200
    active = cookie(signed_in)
    assert (
        call(
            method="DELETE",
            path="/api/auth",
            token=active,
            extra={"Origin": "https://evil.invalid"},
        )["status"]
        == 403
    )
    assert call(token=active)["status"] == 200
    docker("stop", "db")
    try:
        response = call(method="DELETE", path="/api/auth", token=active)
        assert response["status"] == 503 and "set-cookie" not in response["headers"]
        assert call(token=active)["status"] == 401
        assert login(client="client_b")["status"] == 503
    finally:
        docker("start", "db")
    for _ in range(30):
        if call(token=active)["status"] == 200:
            break
        time.sleep(1)
    else:
        raise RuntimeError("Test store did not recover")
    assert call(method="DELETE", path="/api/auth", token=active)["status"] == 200
    assert call(instance=2, token=active)["status"] == 401
    print("PASS_invalid_origins_and_fail_closed_database_outage", flush=True)
    print("PASS security_auth_checks_without_customer_data_changes", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    args = parser.parse_args()
    try:
        check(args.env_file.resolve())
    except Exception as exc:
        parser.exit(
            1,
            f"Security check failed ({type(exc).__name__}, line {traceback.extract_tb(exc.__traceback__)[-1].lineno}); no credentials or response bodies were printed.\n",
        )
