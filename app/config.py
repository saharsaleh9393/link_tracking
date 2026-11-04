from functools import lru_cache
from ipaddress import ip_network

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://tracker:tracker_local_only@127.0.0.1:5432/tracker"
    admin_api_key: SecretStr
    report_api_key: SecretStr
    visitor_hmac_key: SecretStr
    public_base_url: str = "http://127.0.0.1:8000"
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
                ip_network(cidr.strip())
        return self

    @property
    def allowed_hosts(self) -> set[str]:
        return {v.strip().lower() for v in self.destination_allowed_hosts.split(",") if v.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
