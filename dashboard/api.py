"""Server-only HTTP adapter. Never return backend error bodies or authentication headers to UI."""

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]


class DashboardSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    admin_api_key: SecretStr
    report_api_key: SecretStr | None = None
    dashboard_api_url: str = "http://127.0.0.1:8000"
    public_base_url: str = "http://127.0.0.1:8000"

    @field_validator("dashboard_api_url", "public_base_url")
    @classmethod
    def safe_base_url(cls, value):
        parts = urlsplit(value)
        if (
            parts.scheme not in {"http", "https"}
            or not parts.hostname
            or parts.username
            or parts.password
            or parts.query
            or parts.fragment
        ):
            raise ValueError("Use an HTTP(S) base URL without credentials, query or fragment")
        return value.rstrip("/")


class ApiError(Exception):
    """A deliberately sanitized Persian message safe to display."""


@dataclass
class Page:
    items: list[dict]
    total: int


class ApiClient:
    def __init__(self, settings: DashboardSettings, transport=None):
        self._settings = settings
        self._http = httpx.Client(
            base_url=settings.dashboard_api_url,
            timeout=httpx.Timeout(12, connect=3),
            follow_redirects=False,
            transport=transport,
        )

    def request(self, method, path, *, params=None, body=None, reporting=False):
        key = self._settings.report_api_key if reporting else None
        key = key or self._settings.admin_api_key
        try:
            response = self._http.request(
                method,
                path,
                params={k: v for k, v in (params or {}).items() if v is not None},
                json=body,
                headers={"Authorization": "Bearer " + key.get_secret_value()},
            )
        except httpx.HTTPError:
            raise ApiError(
                "ارتباط با سرویس برقرار نشد. روشن بودن API و اتصال شبکه را بررسی کنید؛ برای عملیات ثبت، پیش از تلاش دوباره فهرست را تازه کنید."
            ) from None
        messages = {
            401: "دسترسی تأیید نشد. تنظیمات دسترسی برنامه باید در سمت سرور بررسی شود.",
            403: "اجازه انجام این عملیات را ندارید.",
            404: "مورد انتخاب‌شده پیدا نشد؛ فهرست را تازه کنید.",
            409: "نام کوتاه تکراری است یا اطلاعات قبلاً تغییر کرده؛ صفحه را تازه کنید و دوباره بررسی کنید.",
            410: "این لینک حذف شده یا دیگر در دسترس نیست.",
            422: "اطلاعات فرم معتبر نیست. آدرس مقصد، نام کوتاه، کمپین و بازه تاریخ را بررسی کنید.",
            429: "تعداد درخواست‌ها زیاد است؛ کمی بعد دوباره تلاش کنید.",
        }
        if not response.is_success:
            raise ApiError(
                messages.get(
                    response.status_code, "سرویس فعلاً پاسخ‌گو نیست؛ کمی بعد صفحه را تازه کنید."
                )
            )
        return response

    def get(self, path, **params):
        return self.json(
            self.request(
                "GET",
                path,
                params=params,
                reporting=path.startswith(("/api/v1/analytics", "/api/v1/exports")),
            )
        )

    @staticmethod
    def json(response):
        try:
            return response.json()
        except ValueError:
            raise ApiError(
                "پاسخ سرویس قابل خواندن نیست؛ آدرس سرویس و وضعیت آن باید بررسی شود."
            ) from None

    def page(self, resource, **params):
        response = self.request(
            "GET", f"/api/v1/{resource}", params={**params, "include_total": True}
        )
        items = self.json(response)
        return Page(items=items, total=int(response.headers.get("X-Total-Count", len(items))))

    def create(self, resource, body):
        return self.json(self.request("POST", f"/api/v1/{resource}", body=body))

    def update(self, resource, resource_id, body):
        return self.json(self.request("PATCH", f"/api/v1/{resource}/{resource_id}", body=body))

    def delete_link(self, link_id):
        self.request("DELETE", f"/api/v1/links/{link_id}")

    def tracking_url(self, slug):
        from urllib.parse import quote

        return f"{self._settings.public_base_url}/r/{quote(slug, safe='')}"

    def close(self):
        self._http.close()
