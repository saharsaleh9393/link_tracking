"""Generate private, non-overwriting deployment inputs using only Python's stdlib."""

import argparse
import ipaddress
import os
import re
import secrets
from pathlib import Path


def write_new(path: Path, text: str, mode=0o600):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(text)
    path.chmod(mode)  # Honor the intended mount mode even with an owner-only umask.


def initialize(
    root: Path, *, mode: str, env_name: str, project: str, port: int, subnet: str, database: str
):
    if not re.fullmatch(r"[a-z][a-z0-9-]{2,40}", project):
        raise ValueError("Use a simple Compose project name")
    if not re.fullmatch(r"[a-z][a-z0-9_]{2,50}", database):
        raise ValueError("Use a simple database name")
    if not 1024 <= port <= 65535:
        raise ValueError("Choose an unprivileged local HTTP port")
    network = ipaddress.ip_network(subnet, strict=True)
    if network.version != 4 or network.prefixlen != 24 or not network.is_private:
        raise ValueError("Choose a private IPv4 /24 not used by another network")
    env_file = root / env_name
    secret_dir = root / ".local" / "deployment" / project / "secrets"
    if env_file.exists() or secret_dir.exists():
        raise FileExistsError(
            "Deployment inputs already exist; refusing to replace secrets or env files"
        )
    if not re.fullmatch(r"\.env\.[A-Za-z0-9_.-]+", env_name) or env_file.name.endswith(".example"):
        raise ValueError("Use a separate .env.production or .env.simulation file")
    secret_dir.mkdir(mode=0o700, parents=True)
    # Files must be readable across the non-root container UIDs. Their host parent
    # directories are owner-only; Compose file secrets are read-only bind mounts.
    secret_dir.parent.chmod(0o700)
    secret_dir.chmod(0o700)
    values = {
        key: secrets.token_urlsafe(48)
        for key in (
            "postgres_password",
            "owner_password",
            "app_password",
            "admin_api_key",
            "report_api_key",
            "visitor_hmac_key",
            "dashboard_password",
            "dashboard_session_secret",
        )
    }
    values["owner_database_url"] = (
        f"postgresql+psycopg://linkspace_owner:{values['owner_password']}@db:5432/{database}"
    )
    values["app_database_url"] = (
        f"postgresql+psycopg://linkspace_app:{values['app_password']}@db:5432/{database}"
    )
    for key, value in values.items():
        write_new(secret_dir / key, value + "\n", 0o644)
    for path in (root / ".local" / "geoip", root / ".local" / "backups"):
        path.mkdir(parents=True, exist_ok=True)
    (root / ".local" / "backups").chmod(0o700)
    # These bind-mounted files contain no secrets and must be readable by the
    # postgres/Caddy container identities even under a restrictive host umask.
    for name in ("Caddyfile", "Caddyfile.local", "routes.caddy", "postgres-init.sh", "database.sh"):
        path = root / "deploy" / name
        if path.is_file():
            path.chmod(0o644)
    local = mode == "simulation"
    dashboard = f"http://panel.localhost:{port}" if local else "https://panel.example.com"
    tracking = f"http://go.localhost:{port}" if local else "https://go.example.com"
    entries = {
        "COMPOSE_PROJECT_NAME": project,
        "APP_ENV": mode,
        "RELEASE_TAG": "local-test" if local else "replace-with-git-sha",
        "BIND_ADDRESS": "127.0.0.1" if local else "0.0.0.0",
        "HTTP_PORT": str(port if local else 80),
        "HTTPS_PORT": "443",
        "DASHBOARD_ORIGIN": dashboard,
        "PUBLIC_BASE_URL": tracking,
        "DASHBOARD_SITE": "http://panel.localhost" if local else dashboard,
        "TRACKING_SITES": "http://go.localhost" if local else tracking,
        "HTTP_ALLOWED_HOSTS": "api,127.0.0.1,localhost,panel.localhost,go.localhost"
        if local
        else "api,127.0.0.1,localhost,panel.example.com,go.example.com",
        "DASHBOARD_SECURE_COOKIES": "false" if local else "true",
        "ACME_EMAIL": "ops@example.invalid",
        "DASHBOARD_TRACKING_PATHS": '"/r/* /go/*"',
        "LINKSPACE_ROOT_ORIGINS": "",
        "LINKSPACE_ROUTED_ORIGINS": "",
        "EDGE_SUBNET": str(network),
        "EDGE_DYNAMIC_RANGE": str(list(network.subnets(prefixlen_diff=1))[1]),
        "PROXY_IP": str(network.network_address + 2),
        "POSTGRES_DB": database,
        "SECRETS_DIRECTORY": secret_dir.relative_to(root).as_posix(),
        "GEOIP_DIRECTORY": "./.local/geoip",
        "BACKUP_DIRECTORY": "./.local/backups",
        "BACKUP_UID": str(os.getuid() if hasattr(os, "getuid") else 1000),
        "BACKUP_GID": str(os.getgid() if hasattr(os, "getgid") else 1000),
        "RAW_RETENTION_DAYS": "90",
        "WORKER_INTERVAL_SECONDS": "60",
        "DB_POOL_SIZE": "10",
        "DB_MAX_OVERFLOW": "5",
    }
    write_new(
        env_file,
        "# Generated locally. Do not commit; review before production use.\n"
        + "".join(f"{key}={value}\n" for key, value in entries.items()),
    )
    return env_file


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["simulation", "production"], default="simulation")
    parser.add_argument("--env-file")
    parser.add_argument("--project")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--subnet", default="172.30.50.0/24")
    parser.add_argument("--database", default="linkspace")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        path = initialize(
            root,
            mode=args.mode,
            env_name=args.env_file or f".env.{args.mode}",
            project=args.project
            or ("linkspace-sim" if args.mode == "simulation" else "linkspace-prod"),
            port=args.port,
            subnet=args.subnet,
            database=args.database,
        )
    except (ValueError, OSError) as exc:
        parser.exit(
            1, f"Initialization refused: {type(exc).__name__}. Check arguments/existing files.\n"
        )
    print(
        f"Created {path.name}. Read dashboard_password privately in its SECRETS_DIRECTORY. No secret values were printed."
    )


if __name__ == "__main__":
    main()
