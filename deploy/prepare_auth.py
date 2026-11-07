"""Add only the new ingress secret; preserve every existing env and credential."""

import argparse
import secrets
from pathlib import Path

from init_deployment import write_new
from smoke import read_env


def prepare(env_path):
    env_path = Path(env_path).resolve()
    env = read_env(env_path)
    directory = env_path.parent / env["SECRETS_DIRECTORY"]
    if not directory.is_dir():
        raise ValueError("Existing secrets directory is required")
    target = directory / "dashboard_proxy_secret"
    if target.exists():
        if len(target.read_text().strip()) < 32:
            raise ValueError("Existing proxy secret is invalid; refusing to overwrite it")
    else:
        write_new(target, secrets.token_urlsafe(48) + "\n", 0o644)
    entrypoint = Path(__file__).parent / "proxy-entrypoint.sh"
    if entrypoint.stat().st_mode & 0o444 != 0o444:
        entrypoint.chmod(0o644)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", required=True)
    args = parser.parse_args()
    try:
        prepare(args.env_file)
    except (OSError, ValueError, KeyError):
        parser.exit(
            1, "Auth preparation refused; inspect the env path and protected secrets directory.\n"
        )
    print("Auth ingress secret ready; no existing credential or env value was replaced.")
