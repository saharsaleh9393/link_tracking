"""Create local credentials once; never print or overwrite existing values."""

import secrets
from pathlib import Path


def main():
    target = Path(".env")
    if target.exists():
        print(".env already exists; preserved")
        return
    example = Path(".env.example").read_text(encoding="utf-8")
    replacements = {
        "replace-with-at-least-32-random-characters": secrets.token_urlsafe(48),
        "replace-with-a-different-32-character-key": secrets.token_urlsafe(48),
        "replace-with-an-independent-random-key": secrets.token_urlsafe(48),
    }
    for old, new in replacements.items():
        example = example.replace(old, new)
    # Exclusive creation avoids races and protects previous configuration.
    with target.open("x", encoding="utf-8") as handle:
        handle.write(example)
    target.chmod(0o600)
    print("Created .env with independent random keys; keep this file private")


if __name__ == "__main__":
    main()
