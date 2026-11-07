import os
from functools import lru_cache
from ipaddress import ip_network
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    app_env: Literal["development", "simulation", "production"] = "development"
    http_allowed_hosts: str = ""
    dashboard_origin: str = ""

    database_url: str = "postgresql+psycopg://tracker:tracker_local_only@127.0.0.1:5432/tracker"
    admin_api_key: SecretStr
    report_api_key: SecretStr
    visitor_hmac_key: SecretStr
    public_base_url: str = "http://127.0.0.1:8000"
    # Operator attestations after DNS/TLS/proxy setup; these cannot be set by the UI.
    linkspace_routed_origins: str = ""
    linkspace_root_origins: str = ""
    destination_allowed_hosts: str = ""
    trusted_proxy_cidrs: str = ""
    country_header: str = ""
    geoip_database_path: str = ".local/geoip/country.mmdb"
    link_cache_ttl_seconds: float = Field(2, ge=0, le=60)
    link_cache_max_size: int = Field(10000, ge=1, le=100000)
    raw_retention_days: int = Field(90, ge=1)
    worker_interval_seconds: int = Field(60, ge=1)
    db_pool_size: int = Field(10, ge=1, le=100)
    db_max_overflow: int = Field(5, ge=0, le=100)
    db_statement_timeout_ms: int = Field(5000, ge=100, le=60000)

    @model_validator(mode="before")
    @classmethod
    def read_secret_files(cls, values):
        values = dict(values)
        for key in ("database_url", "admin_api_key", "report_api_key", "visitor_hmac_key"):
            path = os.environ.get(key.upper() + "_FILE")
            if path:
                if key.upper() in os.environ and os.environ[key.upper()]:
                    raise ValueError(f"Use either {key.upper()} or its _FILE setting")
                try:
                    values[key] = Path(path).read_text(encoding="utf-8").strip()
                except OSError:
                    raise ValueError(f"Cannot read secret file for {key}") from None
                if not values[key]:
                    raise ValueError(f"Empty secret file for {key}")
        return values

    @model_validator(mode="after")
    def validate_secrets(self):
        values = [self.admin_api_key, self.report_api_key, self.visitor_hmac_key]
        raw = [v.get_secret_value() for v in values]
        if any(len(v) < 32 or v.startswith("replace-") for v in raw):
            raise ValueError("Configure three independent random secrets of at least 32 characters")
        if len(set(raw)) != 3:
            raise ValueError("Admin, reporting and visitor keys must be different")
        for cidr in self.trusted_proxy_cidrs.split(","):
            if cidr.strip():
                network = ip_network(cidr.strip())
                if self.app_env != "development" and network.prefixlen == 0:
                    raise ValueError("Do not trust every proxy address")
        if self.app_env != "development":
            if self.database_url == type(self).model_fields["database_url"].default:
                raise ValueError("Deployment must configure its own database credential")
            hosts = [v.strip() for v in self.http_allowed_hosts.split(",") if v.strip()]
            if not hosts or any("*" in host for host in hosts):
                raise ValueError("Configure exact HTTP_ALLOWED_HOSTS")
            for origin in (self.public_base_url, self.dashboard_origin):
                parts = urlsplit(origin)
                if (
                    not parts.hostname
                    or parts.username
                    or parts.password
                    or parts.query
                    or parts.fragment
                    or parts.path not in {"", "/"}
                ):
                    raise ValueError(
                        "Configure public and dashboard origins without credentials or paths"
                    )
                if parts.scheme != ("https" if self.app_env == "production" else "http"):
                    raise ValueError("Production requires HTTPS; simulation requires HTTP")
                if self.app_env == "production" and (
                    parts.hostname.endswith((".localhost", ".example.com", ".invalid"))
                    or parts.hostname in {"localhost", "example.com"}
                ):
                    raise ValueError(
                        "Replace production example domains with configured real domains"
                    )
            if self.public_base_url.rstrip("/") == self.dashboard_origin.rstrip("/"):
                raise ValueError("Use a dedicated tracking origin separate from the dashboard")
        return self

    @property
    def allowed_hosts(self) -> set[str]:
        return {v.strip().lower() for v in self.destination_allowed_hosts.split(",") if v.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
