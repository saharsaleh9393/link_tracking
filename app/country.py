"""Local MMDB lookup. No IP storage, remote requests or registered-country guessing."""

import atexit
import ipaddress
import logging
from pathlib import Path
from threading import RLock
from time import monotonic

import maxminddb

from app.config import get_settings

logger = logging.getLogger("tracker.country")


class CountryLookup:
    def __init__(self):
        self._lock = RLock()
        self._reader = None
        self._path = None
        self._checked_at = float("-inf")

    def _load(self):
        path = get_settings().geoip_database_path
        # Check for installation/replacement at most once a minute, not once per click.
        if path == self._path and monotonic() - self._checked_at < 60:
            return
        self._checked_at = monotonic()
        self._path = path
        if self._reader is not None:
            self._reader.close()
            self._reader = None
        if not path:
            return
        try:
            if not Path(path).is_file():
                return
            reader = maxminddb.open_database(path)
            if "country" not in reader.metadata().database_type.lower():
                reader.close()
                logger.warning("country_database_wrong_type")
                return
            self._reader = reader
        except (OSError, ValueError, maxminddb.InvalidDatabaseError):
            logger.warning("country_database_unavailable")

    def lookup(self, address: str | None) -> str | None:
        try:
            parsed = ipaddress.ip_address(address or "")
        except ValueError:
            return None
        parsed = getattr(parsed, "ipv4_mapped", None) or parsed
        if not parsed.is_global or parsed.is_multicast:
            return None
        with self._lock:
            self._load()
            if self._reader is None:
                return None
            try:
                result = self._reader.get(str(parsed)) or {}
                country = result.get("country") if isinstance(result, dict) else None
                return country.get("iso_code") if isinstance(country, dict) else None
            except (OSError, ValueError, maxminddb.InvalidDatabaseError):
                return None

    def available(self) -> bool:
        with self._lock:
            self._load()
            return self._reader is not None

    def close(self):
        with self._lock:
            if self._reader is not None:
                self._reader.close()
            self._reader = None
            self._path = None
            self._checked_at = float("-inf")


country_lookup = CountryLookup()
atexit.register(country_lookup.close)
