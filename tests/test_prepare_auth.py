import subprocess
import sys
from pathlib import Path


def test_prepare_adds_only_missing_proxy_secret_and_never_replaces_inputs(tmp_path):
    directory = tmp_path / "secrets"
    directory.mkdir()
    existing = directory / "existing_credential"
    existing.write_text("private-fixture-credential")
    env = tmp_path / ".env.test"
    original = "SECRETS_DIRECTORY=secrets\nUNRELATED=unchanged\n"
    env.write_text(original)
    command = [
        sys.executable,
        str(Path("deploy/prepare_auth.py").resolve()),
        "--env-file",
        str(env),
    ]
    first = subprocess.run(command, capture_output=True, text=True)
    assert first.returncode == 0
    proxy = directory / "dashboard_proxy_secret"
    secret = proxy.read_text()
    assert len(secret.strip()) >= 32 and secret.strip() not in first.stdout
    second = subprocess.run(command, capture_output=True, text=True)
    assert second.returncode == 0
    assert proxy.read_text() == secret
    assert env.read_text() == original
    assert existing.read_text() == "private-fixture-credential"
    proxy.write_text("invalid-fixture")
    assert subprocess.run(command, capture_output=True).returncode != 0
    assert proxy.read_text() == "invalid-fixture"
