"""Install the official free DB-IP Country Lite MMDB using verified HTTPS.

Run from the checkout root. Existing databases require explicit --update.
"""

import argparse
import gzip
import hashlib
import json
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import maxminddb


def install(month: str, target: Path, update: bool = False):
    if not re.fullmatch(r"\d{4}-(?:0[1-9]|1[0-2])", month):
        raise ValueError("Use YYYY-MM for the database release")
    if target.exists() and not update:
        print("Existing country database preserved; use --update explicitly to refresh it.")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://download.db-ip.com/free/dbip-country-lite-{month}.mmdb.gz"
    with tempfile.TemporaryDirectory(dir=target.parent) as directory:
        compressed = Path(directory) / "country.mmdb.gz"
        candidate = Path(directory) / "country.mmdb"
        with urlopen(url, timeout=60) as response, compressed.open("wb") as output:
            if response.url != url:
                raise ValueError("Unexpected download redirect; no database installed")
            size = 0
            while chunk := response.read(65536):
                size += len(chunk)
                if size > 16 * 1024 * 1024:
                    raise ValueError("Country download exceeds the supported size")
                output.write(chunk)
        with gzip.open(compressed, "rb") as source, candidate.open("wb") as output:
            size = 0
            while chunk := source.read(65536):
                size += len(chunk)
                if size > 64 * 1024 * 1024:
                    raise ValueError("Country database exceeds the supported size")
                output.write(chunk)
        with maxminddb.open_database(str(candidate)) as reader:
            if "country" not in reader.metadata().database_type.lower():
                raise ValueError("Downloaded file is not a country MMDB")
        digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
        # The old file remains intact until the new download has passed validation.
        candidate.replace(target)
    target.with_suffix(".source.json").write_text(
        json.dumps(
            {
                "source": url,
                "release": month,
                "sha256": digest,
                "attribution": "IP Geolocation by DB-IP (https://db-ip.com)",
                "license": "CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/)",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Country database installed. Release: {month}; SHA-256: {digest}")
    print(
        "IP Geolocation by DB-IP (https://db-ip.com), CC BY 4.0. Restart the API after installation."
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--month", default=datetime.now(UTC).strftime("%Y-%m"))
    parser.add_argument("--output", type=Path, default=Path(".local/geoip/country.mmdb"))
    parser.add_argument("--update", action="store_true")
    args = parser.parse_args()
    try:
        install(args.month, args.output, args.update)
    except HTTPError as exc:
        parser.exit(
            1,
            f"Country database download failed (HTTP {exc.code}). Check Internet access or choose an available --month.\n",
        )
    except (URLError, OSError, EOFError, ValueError, maxminddb.InvalidDatabaseError):
        parser.exit(
            1,
            "Country database installation did not complete. A database is replaced only after validation. Check network/trust, release and permissions; on Windows stop the API before --update.\n",
        )


if __name__ == "__main__":
    main()
