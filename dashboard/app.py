from datetime import UTC, datetime, timedelta

import streamlit as st
from pydantic import ValidationError

from dashboard.api import ApiClient, ApiError, DashboardSettings
from dashboard.presentation import (
    CLASSIFICATION,
    DEVICE,
    STATUS,
    TEHRAN,
    UTMS,
    chart,
    date_params,
    display_time,
    effective_status,
)

CSS = """
<style>
.stApp, [data-testid="stSidebar"] {font-family: Tahoma, Arial, sans-serif; direction:rtl;}
[data-testid="stMainBlockContainer"] {max-width:1400px; padding-top:2rem; padding-bottom:3rem;}
h1,h2,h3,p,label,[data-testid="stMarkdownContainer"], [data-testid="stMetric"] {text-align:right;}
h1 {font-size:2.1rem!important; letter-spacing:-.04em;}
[data-testid="stSidebar"] {border-left:1px solid #e7eaf3;}
[data-testid="stMetric"] {background:white; border:1px solid #e7eaf3; border-radius:16px; padding:1.1rem;}
[data-testid="stMetricValue"] {color:#4e40bc; font-weight:700;}
[data-testid="stVerticalBlockBorderWrapper"] {border-radius:16px;}
[data-testid="stTextInput"] input,[data-testid="stTextArea"] textarea {text-align:right;}
pre,code,[data-testid="stCode"],input[type="url"] {direction:ltr!important; text-align:left!important;}
[data-testid="stDateInput"] input,[data-testid="stTimeInput"] input,
input[aria-label="آدرس مقصد"],input[aria-label="آدرس مقصد جدید"] {direction:ltr!important; text-align:left!important;}
[data-testid="stAlert"] {border-radius:12px;}
[data-testid="stAppDeployButton"] {display:none;}
@media(max-width:768px) {
  [data-testid="stMainBlockContainer"] {padding:1rem;}
  h1 {font-size:1.6rem!important;}
  [data-testid="stSidebar"][data-collapsed="true"] {visibility:hidden; pointer-events:none; overflow:hidden;}
  [data-testid="stSidebar"][data-collapsed="false"] {
    position:fixed!important; right:0!important; left:auto!important;
    width:min(300px,85vw)!important; transform:none!important; z-index:1000;
  }
}
</style>
"""


@st.cache_resource(show_spinner=False)
def get_client():
    return ApiClient(DashboardSettings())


def notice():
    message = st.session_state.pop("flash", None)
    if message:
        st.success(message)


def done(message):
    st.session_state["flash"] = message
    st.rerun()


def table(rows):
    if not rows:
        st.info("هنوز موردی برای نمایش وجود ندارد.")
        return
    st.dataframe(rows, hide_index=True, width="stretch")
    st.caption(
        "برای مرتب‌سازی، روی عنوان ستون کلیک کنید. مرتب‌سازی جدول فقط روی صفحه فعلی اعمال می‌شود."
    )


def campaign_catalog(api, key):
    search = st.text_input("جست‌وجوی کمپین", key=f"{key}_campaign_search", placeholder="نام کمپین…")
    page = api.page("campaigns", q=search, limit=500)
    if page.total > len(page.items):
        st.caption("۵۰۰ نتیجه اول نمایش داده می‌شود؛ جست‌وجو را دقیق‌تر کنید.")
    return page.items


def campaign_select(campaigns, key, *, selected=None, active_only=False, all_option=False):
    candidates = [
        c for c in campaigns if not active_only or not c["archived"] or c["id"] == selected
    ]
    labels = {c["id"]: c["name"] + (" · بایگانی‌شده" if c["archived"] else "") for c in candidates}
    if selected and selected not in labels:
        labels[selected] = "کمپین فعلی (خارج از نتایج جست‌وجو)"
    options = [None, *labels]
    return st.selectbox(
        "کمپین",
        options,
        index=options.index(selected) if selected in options else 0,
        format_func=lambda value: labels.get(value, "همه کمپین‌ها" if all_option else "بدون کمپین"),
        key=key,
    )


def tracking_url(api, slug):
    st.caption("لینک رهگیری — برای کپی از دکمه کنار کادر استفاده کنید")
    st.code(api.tracking_url(slug), language=None)


def utm_inputs(prefix, values=None):
    values = values or {}
    result = {}
    for key, label in UTMS.items():
        result[key] = (
            st.text_input(
                label, value=values.get(key) or "", max_chars=200, key=f"{prefix}_{key}"
            ).strip()
            or None
        )
    return result


def expiry_input(prefix, value=None):
    enabled = st.checkbox("محدودیت تاریخ اعتبار", value=bool(value), key=f"{prefix}_expires")
    initial = (
        datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(TEHRAN)
        if value
        else (datetime.now(TEHRAN) + timedelta(days=30)).replace(
            hour=23, minute=59, second=0, microsecond=0
        )
    )
    day = st.date_input(
        "تاریخ پایان اعتبار (میلادی)", value=initial.date(), key=f"{prefix}_expiry_date"
    )
    clock = st.time_input(
        "ساعت پایان اعتبار (تهران)",
        value=initial.time().replace(second=0, microsecond=0),
        key=f"{prefix}_expiry_time",
    )
    if not enabled:
        return None
    if value and day == initial.date() and clock == initial.time().replace(second=0, microsecond=0):
        return value
    return datetime.combine(day, clock, TEHRAN).astimezone(UTC).isoformat()


def overview(api):
    st.title("نمای کلی")
    st.caption("نبض کمپین‌ها و لینک‌های بازاریابی، در یک نگاه")
    info = api.get("/api/v1/management/overview")
    today = datetime.now(TEHRAN).date()
    stats = api.get("/api/v1/analytics/summary", **date_params(today - timedelta(days=6), today))
    columns = st.columns(4)
    for column, label, value in zip(
        columns,
        ("لینک‌های موجود", "کلیک‌های ۷ روز اخیر", "کمپین‌های فعال", "کلیک انسانی ۷ روز اخیر"),
        (
            info["total_links"],
            stats["total_clicks"],
            info["active_campaigns"],
            stats["human_clicks"],
        ),
        strict=True,
    ):
        column.metric(label, f"{value:,}")
    st.subheader("روند کلیک‌ها")
    series = api.get(
        "/api/v1/analytics/trends",
        **date_params(today - timedelta(days=6), today),
        granularity="day",
    )
    if series["items"]:
        st.plotly_chart(chart(series["items"], trend=True), width="stretch", key="overview_trend")
    else:
        st.info("هنوز کلیکی ثبت نشده است. از بخش «لینک‌ها» اولین لینک را بسازید و آن را منتشر کنید.")
    st.subheader("فعالیت‌های اخیر مدیریت")
    actions = {
        "link.create": "ساخت لینک",
        "link.update": "ویرایش لینک",
        "link.delete": "حذف لینک",
        "campaign.create": "ساخت کمپین",
        "campaign.update": "ویرایش کمپین",
        "destination.create": "افزودن مقصد",
    }
    table(
        [
            {
                "فعالیت": actions.get(row["action"], "به‌روزرسانی"),
                "زمان تهران": display_time(row["occurred_at"]),
            }
            for row in info["recent_activity"]
        ]
    )


def create_link_form(api, campaigns):
    with st.expander("ساخت لینک جدید", expanded=not st.session_state.get("has_links", False)):
        with st.form("new_link", clear_on_submit=False):
            st.caption("آدرس Instagram، WhatsApp، Telegram یا یک وب‌سایت عمومی را وارد کنید.")
            destination = st.text_input(
                "آدرس مقصد",
                placeholder="https://wa.me/989123456789",
                key="new_destination",
                max_chars=4096,
            )
            slug = st.text_input(
                "نام کوتاه دلخواه (اختیاری)",
                help="۳ تا ۸۰ حرف انگلیسی، عدد، خط تیره یا زیرخط؛ خالی بماند خودکار ساخته می‌شود.",
                key="new_slug",
                max_chars=80,
            )
            campaign_id = campaign_select(campaigns, "new_campaign", active_only=True)
            cols = st.columns(2)
            with cols[0]:
                utms = utm_inputs("new")
            with cols[1]:
                expires_at = expiry_input("new")
                forward = st.checkbox(
                    "افزودن UTM به آدرس مقصد",
                    help="پیش‌فرض خاموش است تا پارامترهای مقصد حفظ شوند.",
                    key="new_forward",
                )
            submitted = st.form_submit_button("ساخت لینک", type="primary")
        if submitted:
            if not destination.strip():
                st.warning("آدرس مقصد را وارد کنید.")
                return
            with st.spinner("در حال ساخت لینک…"):
                link = api.create(
                    "links",
                    {
                        "destination_url": destination.strip(),
                        "slug": slug.strip() or None,
                        "campaign_id": campaign_id,
                        "expires_at": expires_at,
                        "forward_utm": forward,
                        **utms,
                    },
                )
            st.session_state["created_slug"] = link["slug"]
            done("لینک با موفقیت ساخته شد.")


def edit_link(api, link, campaigns):
    tracking_url(api, link["slug"])
    st.caption(f"وضعیت: {effective_status(link)} · نسخه: {link['version']}")
    if link["status"] == "deleted":
        st.info("لینک حذف شده است و نام کوتاه آن برای حفظ امنیت رزرو می‌ماند.")
        return
    # Versioned widget keys reset stale form values after a successful edit.
    prefix = f"edit_{link['id']}_{link['version']}"
    with st.form(prefix):
        campaign_id = campaign_select(
            campaigns, f"{prefix}_campaign", selected=link["campaign_id"], active_only=True
        )
        active = st.checkbox(
            "لینک فعال باشد", value=link["status"] == "active", key=f"{prefix}_active"
        )
        utms = utm_inputs(prefix, link)
        expires_at = expiry_input(prefix, link.get("expires_at"))
        forward = st.checkbox(
            "افزودن UTM به مقصد", value=link["forward_utm"], key=f"{prefix}_forward"
        )
        save = st.form_submit_button("ذخیره تغییرات", type="primary")
    if save:
        body = {
            "expected_version": link["version"],
            "status": "active" if active else "disabled",
            "expires_at": expires_at,
            "forward_utm": forward,
            **utms,
        }
        if campaign_id != link["campaign_id"]:
            body["campaign_id"] = campaign_id
        api.update("links", link["id"], body)
        done("تغییرات لینک ذخیره شد.")
    st.subheader("مقصدهای لینک")
    st.caption("مقصدها نسخه‌بندی می‌شوند؛ برای تغییر آدرس، یک مقصد جدید اضافه و سپس آن را فعال کنید.")
    destinations = api.get(f"/api/v1/links/{link['id']}/destinations", limit=500)
    table(
        [
            {
                "نسخه": row["version"],
                "آدرس": row["url"],
                "فعال": "بله" if row["id"] == link["active_destination_id"] else "خیر",
            }
            for row in destinations
        ]
    )
    if len(destinations) == 500:
        st.caption("۵۰۰ نسخه اول نمایش داده می‌شود؛ نسخه‌های بیشتر از API قابل دریافت‌اند.")
    if destinations:
        labels = {row["id"]: f"نسخه {row['version']} · {row['url']}" for row in destinations}
        options = list(labels)
        selected = st.selectbox(
            "انتخاب مقصد فعال",
            options,
            index=options.index(link["active_destination_id"])
            if link["active_destination_id"] in options
            else 0,
            format_func=labels.get,
            key=f"{prefix}_destination",
        )
        if st.button("فعال‌کردن مقصد انتخاب‌شده", key=f"{prefix}_activate_destination"):
            api.update(
                "links",
                link["id"],
                {"expected_version": link["version"], "active_destination_id": selected},
            )
            done("مقصد فعال به‌روزرسانی شد.")
    with st.form(f"{prefix}_add_destination"):
        url = st.text_input("آدرس مقصد جدید", max_chars=4096)
        add = st.form_submit_button("افزودن مقصد")
    if add:
        if not url.strip():
            st.warning("آدرس مقصد را وارد کنید.")
        else:
            api.create(f"links/{link['id']}/destinations", {"url": url.strip()})
            done("مقصد اضافه شد؛ برای استفاده، آن را به‌عنوان مقصد فعال انتخاب کنید.")
    with st.expander("حذف لینک"):
        confirm = st.checkbox(
            "حذف لینک را تأیید می‌کنم؛ آمار قبلی حفظ می‌شود.", key=f"{prefix}_confirm"
        )
        if st.button("حذف لینک", disabled=not confirm, key=f"{prefix}_delete"):
            api.delete_link(link["id"])
            done("لینک حذف شد؛ آمار تاریخی حفظ شده است.")


def links_page(api):
    st.title("لینک‌ها")
    st.caption("ساخت، انتشار و مدیریت لینک‌های بازاریابی")
    campaigns = campaign_catalog(api, "links")
    create_link_form(api, campaigns)
    if st.session_state.get("created_slug"):
        tracking_url(api, st.session_state["created_slug"])
    st.subheader("فهرست لینک‌ها")
    cols = st.columns(3)
    with cols[0]:
        search = st.text_input("جست‌وجوی نام کوتاه", key="links_search")
    with cols[1]:
        status = st.selectbox(
            "وضعیت",
            [None, *STATUS],
            format_func=lambda key: STATUS.get(key, "همه"),
            key="links_status",
        )
    with cols[2]:
        campaign_id = campaign_select(campaigns, "links_filter_campaign", all_option=True)
    sort_labels = {
        "created_at": "زمان ساخت",
        "updated_at": "آخرین ویرایش",
        "slug": "نام کوتاه",
        "status": "وضعیت",
    }
    sorting = st.selectbox("مرتب‌سازی فهرست", list(sort_labels), format_func=sort_labels.get)
    descending = st.checkbox("ترتیب نزولی", value=True)
    signature = (search, status, campaign_id, sorting, descending)
    if st.session_state.get("links_signature") != signature:
        st.session_state["links_page"] = 1
        st.session_state["links_signature"] = signature
    page_number = st.number_input(
        "صفحه فهرست لینک‌ها", min_value=1, max_value=4001, step=1, key="links_page"
    )
    page = api.page(
        "links",
        q=search,
        status=status,
        campaign_id=campaign_id,
        sort_by=sorting,
        descending=descending,
        offset=(page_number - 1) * 25,
        limit=25,
    )
    st.session_state["has_links"] = page.total > 0
    st.caption(f"{page.total:,} نتیجه · صفحه {page_number} از {max(1, (page.total + 24) // 25)}")
    if page.total > 100025:
        st.info(
            "برای دسترسی به نتایج بیشتر، جست‌وجو و فیلترها را محدودتر کنید؛ فهرست عمومی سقف صفحه‌بندی دارد."
        )
    campaign_names = {row["id"]: row["name"] for row in campaigns}
    table(
        [
            {
                "نام کوتاه": row["slug"],
                "وضعیت": effective_status(row),
                "کمپین": campaign_names.get(row["campaign_id"], "—"),
                "زمان ساخت": display_time(row["created_at"]),
            }
            for row in page.items
        ]
    )
    if page.items:
        st.subheader("مدیریت لینک انتخاب‌شده")
        options = {row["id"]: row["slug"] for row in page.items}
        selected = st.selectbox(
            "انتخاب لینک", list(options), format_func=options.get, key="managed_link"
        )
        edit_link(api, api.get(f"/api/v1/links/{selected}"), campaigns)


def campaigns_page(api):
    st.title("کمپین‌ها")
    st.caption("لینک‌ها را در کمپین‌های قابل مدیریت سازمان‌دهی کنید")
    with st.form("new_campaign"):
        name = st.text_input("نام کمپین جدید", max_chars=200)
        submit = st.form_submit_button("ساخت کمپین", type="primary")
    if submit:
        if not name.strip():
            st.warning("نام کمپین را وارد کنید.")
        else:
            api.create("campaigns", {"name": name.strip()})
            done("کمپین ساخته شد.")
    search = st.text_input("جست‌وجوی نام کمپین", key="campaign_search")
    status = st.selectbox(
        "وضعیت کمپین",
        [None, False, True],
        format_func=lambda v: "همه" if v is None else "بایگانی‌شده" if v else "فعال",
    )
    signature = (search, status)
    if st.session_state.get("campaign_signature") != signature:
        st.session_state["campaign_page"] = 1
        st.session_state["campaign_signature"] = signature
    number = st.number_input(
        "صفحه فهرست کمپین‌ها", min_value=1, max_value=4001, step=1, key="campaign_page"
    )
    page = api.page("campaigns", q=search, archived=status, limit=25, offset=(number - 1) * 25)
    st.caption(f"{page.total:,} نتیجه")
    table(
        [
            {
                "نام": row["name"],
                "وضعیت": "بایگانی‌شده" if row["archived"] else "فعال",
                "زمان ساخت": display_time(row["created_at"]),
            }
            for row in page.items
        ]
    )
    if page.items:
        labels = {row["id"]: row["name"] for row in page.items}
        selected = st.selectbox("کمپین برای ویرایش", list(labels), format_func=labels.get)
        campaign = next(row for row in page.items if row["id"] == selected)
        with st.form(f"campaign_edit_{selected}"):
            edited_name = st.text_input("نام کمپین", value=campaign["name"], max_chars=200)
            archived = st.checkbox("کمپین بایگانی شود", value=campaign["archived"])
            save = st.form_submit_button("ذخیره کمپین", type="primary")
        if save:
            if not edited_name.strip():
                st.warning("نام کمپین را وارد کنید.")
            else:
                api.update(
                    "campaigns", selected, {"name": edited_name.strip(), "archived": archived}
                )
                done("کمپین به‌روزرسانی شد.")
        st.caption(
            "بایگانی کمپین لینک‌های موجود را غیرفعال نمی‌کند؛ وضعیت لینک‌ها را از بخش لینک‌ها مدیریت کنید."
        )


def report_filters(api, prefix):
    today = datetime.now(TEHRAN).date()
    dates = st.date_input(
        "بازه گزارش (میلادی، روزهای تهران)",
        value=(today - timedelta(days=6), today),
        max_value=today,
        key=f"{prefix}_dates",
    )
    if not isinstance(dates, (tuple, list)) or len(dates) != 2:
        st.info("ابتدا روز شروع و پایان بازه را انتخاب کنید.")
        return None
    try:
        params = date_params(*dates)
    except ValueError as exc:
        st.warning(str(exc))
        return None
    campaigns = campaign_catalog(api, prefix)
    campaign_id = campaign_select(campaigns, f"{prefix}_campaign", all_option=True)
    search = st.text_input("جست‌وجوی لینک برای گزارش", key=f"{prefix}_link_search")
    # Reporting uses historical campaign snapshots; do not restrict choices by current ownership.
    links = api.page("links", q=search, limit=500)
    if links.total > len(links.items):
        st.caption("۵۰۰ لینک اول در انتخابگر موجود است؛ جست‌وجوی نام کوتاه را دقیق‌تر کنید.")
    labels = {row["id"]: row["slug"] for row in links.items}
    link_id = st.selectbox(
        "لینک گزارش",
        [None, *labels],
        format_func=lambda value: labels.get(value, "همه لینک‌ها"),
        key=f"{prefix}_link",
    )
    st.caption(
        "تاریخ‌ها میلادی‌اند. مرز فیلتر بر اساس تهران است؛ سبدهای نمودار روزانه/ساعتی بر مبنای UTC و زمان نمایشی تهران هستند."
    )
    return {**params, "campaign_id": campaign_id, "link_id": link_id}, campaigns, links.items


def analytics_page(api):
    st.title("تحلیل ترافیک")
    selected = report_filters(api, "analytics")
    if selected is None:
        return
    params, campaigns, links = selected
    summary = api.get("/api/v1/analytics/summary", **params)
    columns = st.columns(4)
    for column, label, key in zip(
        columns,
        ("همه کلیک‌ها", "انسان (تخمینی)", "ربات", "بازدیدکننده‌ـروز"),
        ("total_clicks", "human_clicks", "bot_clicks", "estimated_visitor_days"),
        strict=True,
    ):
        column.metric(label, f"{summary[key]:,}")
    st.caption(
        "بازدیدکننده‌ـروز، جمع برآورد بازدیدکنندگان روزانه UTC است؛ تعداد افراد یکتای کل دوره نیست. تشخیص انسان/ربات تخمینی است."
    )
    if summary.get("partial_history"):
        st.warning(
            "بخشی از این بازه ممکن است خارج از مدت نگهداری رویدادهای خام باشد؛ گزارش می‌تواند ناقص باشد."
        )
    if not summary["total_clicks"]:
        st.info("در این بازه و با فیلترهای انتخابی، کلیکی ثبت نشده است.")
        return
    granularity = st.radio(
        "دقت روند",
        ["day", "hour"],
        format_func=lambda v: "روزانه" if v == "day" else "ساعتی",
        horizontal=True,
    )
    series = api.get("/api/v1/analytics/trends", **params, granularity=granularity, limit=1000)
    st.plotly_chart(
        chart(series["items"], trend=True, title="روند کلیک‌ها"),
        width="stretch",
        key="traffic_trend",
    )
    if series.get("next_offset") is not None:
        st.info(
            "۱۰۰۰ سبد اول نمایش داده می‌شود. برای دیدن ادامه، بازه را کوتاه‌تر یا دقت روزانه را انتخاب کنید."
        )
    dimensions = {
        "campaign": "عملکرد کمپین‌ها",
        "source": "منبع ترافیک",
        "medium": "رسانه",
        "device": "دستگاه",
        "browser": "مرورگر",
        "country": "کشور",
        "utm_campaign": "کمپین UTM",
        "utm_content": "محتوای UTM",
        "utm_term": "عبارت UTM",
    }
    left, right = st.columns(2)
    for index, (dimension, title) in enumerate(dimensions.items()):
        with left if index % 2 == 0 else right:
            data = api.get("/api/v1/analytics/breakdowns", **params, dimension=dimension, limit=20)
            names = (
                {c["id"]: c["name"] for c in campaigns}
                if dimension == "campaign"
                else DEVICE
                if dimension == "device"
                else {}
            )
            st.plotly_chart(
                chart(data["items"], labels=names, title=title),
                width="stretch",
                key=f"chart_{dimension}",
            )
            if data.get("next_offset") is not None:
                st.caption("۲۰ گروه اول بر اساس تعداد کلیک نمایش داده می‌شود.")
    st.subheader("مقایسه لینک‌ها")
    labels = {row["id"]: row["slug"] for row in links}
    ids = st.multiselect(
        "لینک‌های مقایسه (حداکثر ۱۰ مورد)", list(labels), format_func=labels.get, max_selections=10
    )
    if ids:
        comparison = api.get(
            "/api/v1/analytics/link-comparison", **{**params, "link_id": None}, link_ids=ids
        )
        rows = comparison["items"]
        st.plotly_chart(
            chart(
                [{**row, "value": row["link_id"]} for row in rows],
                labels=labels,
                title="مقایسه تعداد کلیک",
            ),
            width="stretch",
            key="comparison",
        )
        table(
            [
                {
                    "لینک": labels[row["link_id"]],
                    "کلیک": row["total_clicks"],
                    "انسان": row["human_clicks"],
                    "ربات": row["bot_clicks"],
                }
                for row in rows
            ]
        )


def click_reports(api):
    st.title("گزارش کلیک‌ها")
    st.caption("مرور جزئیات با صفحه‌بندی؛ بدون نمایش IP یا شناسه مستعار بازدیدکننده")
    selected = report_filters(api, "clicks")
    if selected is None:
        return
    params, _, links = selected
    signature = tuple(params.items())
    if st.session_state.get("click_signature") != signature:
        st.session_state["click_signature"] = signature
        st.session_state["click_cursors"] = [None]
        st.session_state["click_index"] = 0
    index = st.session_state["click_index"]
    data = api.get(
        "/api/v1/exports/clicks",
        **params,
        cursor=st.session_state["click_cursors"][index],
        limit=100,
    )
    if data.get("partial_history"):
        st.warning("بخشی از بازه ممکن است خارج از مدت نگهداری رویدادهای خام باشد.")
    labels = {row["id"]: row["slug"] for row in links}
    records = [
        {
            "زمان تهران": display_time(row["occurred_at"]),
            "لینک": labels.get(row["link_id"], row["link_id"]),
            "نوع": CLASSIFICATION.get(row["classification"], "نامشخص"),
            "دستگاه": DEVICE.get(row["device"], row["device"]),
            "مرورگر": row["browser"],
            "کشور": row.get("country") or "نامشخص",
            **{label: row.get(key) or "—" for key, label in UTMS.items()},
        }
        for row in data["items"]
    ]
    table(records)
    st.caption(f"صفحه {index + 1} · ترتیب زمانی از قدیمی به جدید · حداکثر ۱۰۰ کلیک در صفحه")
    cols = st.columns(2)
    if cols[0].button("صفحه قبل", disabled=index == 0):
        st.session_state["click_index"] -= 1
        st.rerun()
    if cols[1].button("صفحه بعد", disabled=not data.get("next_cursor")):
        cursors = st.session_state["click_cursors"][: index + 1]
        cursors.append(data["next_cursor"])
        st.session_state["click_cursors"] = cursors
        st.session_state["click_index"] += 1
        st.rerun()
    st.caption("تازه‌سازی، صفحه‌بندی گزارش را از ابتدا و با داده جدید آغاز می‌کند.")


PAGES = {
    "نمای کلی": overview,
    "لینک‌ها": links_page,
    "کمپین‌ها": campaigns_page,
    "تحلیل ترافیک": analytics_page,
    "گزارش کلیک‌ها": click_reports,
}


def main():
    st.set_page_config(page_title="مدیریت لینک‌های بازاریابی", page_icon="🔗", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)  # Static CSS only; never interpolate API/user data.
    with st.sidebar:
        st.title("پیوند | بازاریابی")
        st.caption("مدیریت هوشمند لینک و تحلیل ترافیک")
        page = st.radio("بخش‌های برنامه", list(PAGES), label_visibility="collapsed")
        if st.button("تازه‌سازی اطلاعات", use_container_width=True):
            for key in ("click_signature", "click_cursors", "click_index"):
                st.session_state.pop(key, None)
            st.rerun()
        st.divider()
        st.caption("زمان نمایش: تهران · تاریخ میلادی")
        st.caption("مدیریت محلی؛ دسترسی مرورگر به کلید API نیاز ندارد.")
    notice()
    try:
        api = get_client()
    except (ValidationError, ValueError):
        st.error("تنظیمات برنامه کامل نیست. فایل تنظیمات سمت سرور را طبق راهنمای نصب آماده کنید.")
        return
    try:
        with st.spinner("در حال دریافت اطلاعات…"):
            PAGES[page](api)
    except ApiError as exc:
        st.error(str(exc))
        st.info(
            "داده‌ای برای این بخش نمایش داده نشد. پس از رفع مشکل از «تازه‌سازی اطلاعات» استفاده کنید."
        )
