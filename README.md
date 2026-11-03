# Marketing Link Tracking

بک‌اند قابل اجرای رهگیری لینک‌های بازاریابی با Python 3.12، FastAPI، SQLAlchemy و PostgreSQL 17.
این پروژه API است؛ مدیریت و آزمایش تعاملی از Swagger انجام می‌شود و رابط داشبورد گرافیکی جداگانه ندارد.

## اجرا روی ویندوز

دستورات زیر را در PowerShell و داخل پوشه پروژه اجرا کنید. ابتدا Python 3.12 یا جدیدتر و PostgreSQL 17 را نصب کنید.
Laragon به‌تنهایی تضمین نمی‌کند PostgreSQL نصب باشد؛ MySQL آن برای این پروژه استفاده نمی‌شود.

برای ساخت محیط مجازی و نصب نسخه‌های قفل‌شده وابستگی‌ها:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install --require-hashes -r requirements-dev.lock
```

برای ساخت تنظیمات محلی با سه کلید تصادفی مستقل؛ این دستور فایل موجود را بازنویسی نمی‌کند:

```powershell
.\.venv\Scripts\python scripts/init_env.py
```

برای پایگاه داده یکی از دو روش را انتخاب کنید:

1. در PostgreSQL محلی با pgAdmin یک نقش ورود `tracker` و یک دیتابیس `tracker` با مالکیت همان نقش بسازید؛ رمز انتخابی خود را در `DATABASE_URL` فایل `.env` وارد کنید. کاراکترهای ویژه رمز باید در URL درصدگذاری شوند. این نقش برای migration به مجوز ساخت جدول نیاز دارد.
2. اگر Docker Desktop دارید، دستور زیر PostgreSQL محلی را روی پورت 5432 با volume پایدار بالا می‌آورد. اگر PostgreSQL دیگری این پورت را گرفته، ابتدا پورت آزاد را در Compose و `.env` هماهنگ کنید:

```powershell
docker compose up -d db
```

برای ساخت schema، پارتیشن‌ها و اجرای اولین نوبت نگهداری:

```powershell
.\.venv\Scripts\alembic upgrade head
.\.venv\Scripts\python -m app.worker --once
```

برای اجرای API محلی:

```powershell
.\.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log --no-proxy-headers
```

در یک ترمینال دیگر worker را اجرا کنید؛ این فرایند باید هنگام استفاده از پروژه فعال بماند:

```powershell
.\.venv\Scripts\python -m app.worker
```

Swagger در مسیر `/docs` سرویس در دسترس است. در دکمه **Authorize** مقدار `ADMIN_API_KEY` را از فایل محلی خود وارد کنید. کلید را در چت، Git یا URL قرار ندهید.
با `POST /api/v1/links` یک لینک بسازید و مسیر `/r/{slug}` را باز کنید. آدرس عمومی لینک از `PUBLIC_BASE_URL` و همین مسیر تشکیل می‌شود؛ این متغیر برای اسکریپت smoke هم استفاده می‌شود.

نمونه بدنه ساخت لینک:

```json
{
  "slug": "instagram-launch",
  "destination_url": "https://www.instagram.com/example/?igsh=abc",
  "utm_source": "instagram",
  "utm_medium": "social",
  "utm_campaign": "launch"
}
```

`forward_utm` پیش‌فرض خاموش است تا مقصد دقیقاً حفظ شود. در حالت روشن، UTMها فقط وقتی در مقصد وجود ندارند به انتهای query اضافه می‌شوند.

برای بررسی end-to-end سرویسِ روشن، اسکریپت زیر یک لینک آزمایشی می‌سازد، ریدایرکت و ثبت کلیک را بررسی می‌کند و لینک را soft-delete می‌کند:

```powershell
.\.venv\Scripts\python scripts/smoke.py
```

## Linux/macOS development

The same workflow uses `.venv/bin/python`, `.venv/bin/alembic` and `.venv/bin/uvicorn`:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements-dev.lock
.venv/bin/python scripts/init_env.py
docker compose up -d db
.venv/bin/alembic upgrade head
.venv/bin/python -m app.worker --once
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log --no-proxy-headers
# Separate terminal:
.venv/bin/python -m app.worker
```

Alternatively use `uv sync --frozen` with the checked-in `uv.lock`. After intentional dependency changes, regenerate both exports with the commands in [development](docs/development.md).

## قابلیت‌ها و حدود فعلی

- کمپین، لینک با slug یکتا، چند مقصد ذخیره‌شده، انتخاب مقصد فعال، ویرایش با کنترل نسخه، غیرفعال‌سازی و حذف نرم.
- ثبت UUID کلیک، زمان UTC، UTM تاریخی، دستگاه، سیستم‌عامل، مرورگر، referrer پاک‌سازی‌شده و طبقه‌بندی اولیه bot/human/unknown.
- HMAC روزانه بدون ذخیره IP خام. شاخص یکتای چند روز برابر تعداد افراد یکتا نیست؛ API آن را `estimated_visitor_days` می‌نامد.
- کشور فقط از هدر یک reverse proxy مشخص و مورد اعتماد خوانده می‌شود؛ در اجرای عادی محلی مقدار آن `null` است.
- گزارش‌ها، روند روزانه/ساعتی، مقایسه لینک و خروجی صفحه‌بندی‌شده Power BI.
- پارتیشن ماهانه، worker تجمیع تکرارپذیر، نگهداری داده خام و شاخص‌های Prometheus.
- Redis، Kafka و Kubernetes لازم نیستند و استفاده نشده‌اند.

این نسخه روی PostgreSQL و درخواست‌های هم‌زمان تست می‌شود؛ ظرفیت میلیون‌ها کلیک در واحد زمان، تشخیص قطعی ربات و استقرار production تأییدشده نیستند. برای انتشار واقعی باید روی سرور مقصد load test، TLS، محدودیت درخواست، backup/restore و نظارت تنظیم شوند. هیچ تغییری روی سرور SSH انجام نشده است.

## مستندات

- [معماری، schema، حریم خصوصی و محدودیت‌ها](docs/architecture.md)
- [تست و توسعه](docs/development.md)
- [API و Power BI](docs/power-bi.md)
- [عملیات، backup و آمادگی استقرار](docs/operations.md)
- [نتایج اجرای واقعی و محدودیت‌های اعتبارسنجی](docs/validation.md)
