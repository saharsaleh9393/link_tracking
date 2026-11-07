import uuid
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class DashboardSession(Base):
    __tablename__ = "dashboard_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class DashboardLoginBucket(Base):
    __tablename__ = "dashboard_login_buckets"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer)
    resets_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class UTMMixin:
    utm_source: Mapped[str | None] = mapped_column(String(200))
    utm_medium: Mapped[str | None] = mapped_column(String(200))
    utm_campaign: Mapped[str | None] = mapped_column(String(200))
    utm_content: Mapped[str | None] = mapped_column(String(200))
    utm_term: Mapped[str | None] = mapped_column(String(200))


class Campaign(Base):
    __tablename__ = "campaigns"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        Index(
            "uq_campaigns_normalized_name",
            func.lower(
                func.btrim(
                    name,
                    " \t\n\r\v\f\u0085\u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000",
                )
            ),
            unique=True,
        ),
    )


class Link(UTMMixin, Base):
    __tablename__ = "links"
    __table_args__ = (
        CheckConstraint("status IN ('active','disabled','deleted')"),
        ForeignKeyConstraint(
            ["id", "active_destination_id"],
            ["link_destinations.link_id", "link_destinations.id"],
            name="links_active_destination_fk",
            deferrable=True,
            initially="DEFERRED",
            use_alter=True,
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    linkspace_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("linkspaces.id"), index=True)
    tracking_base_url: Mapped[str | None] = mapped_column(String(300))
    tracking_path_prefix: Mapped[str | None] = mapped_column(String(50))
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("campaigns.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="active")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active_destination_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    forward_utm: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    @property
    def tracking_url(self) -> str:
        from app.config import get_settings
        from app.linkspace_config import tracking_url

        return tracking_url(
            self.tracking_base_url or get_settings().public_base_url,
            self.tracking_path_prefix if self.tracking_path_prefix is not None else "r",
            self.slug,
        )


class Linkspace(Base):
    __tablename__ = "linkspaces"
    __table_args__ = (
        UniqueConstraint("base_url", "path_prefix", name="uq_linkspaces_configuration"),
        CheckConstraint("NOT is_default OR is_active", name="ck_linkspaces_active_default"),
        Index(
            "uq_linkspaces_default", "is_default", unique=True, postgresql_where=text("is_default")
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100))
    base_url: Mapped[str] = mapped_column(String(300))
    path_prefix: Mapped[str] = mapped_column(String(50), default="r")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Destination(Base):
    __tablename__ = "link_destinations"
    __table_args__ = (UniqueConstraint("link_id", "version"), UniqueConstraint("link_id", "id"))
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    link_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("links.id"), index=True)
    url: Mapped[str] = mapped_column(String(4096))
    version: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ClickEvent(UTMMixin, Base):
    __tablename__ = "click_events"
    __table_args__ = (
        Index("ix_click_link_time", "link_id", "occurred_at"),
        Index("ix_click_campaign_time", "campaign_id", "occurred_at"),
        Index("ix_click_time_brin", "occurred_at", postgresql_using="brin"),
        CheckConstraint("classification IN ('human','bot','unknown')"),
        {"postgresql_partition_by": "RANGE (occurred_at)"},
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    click_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Historical snapshots deliberately have no FKs on the high-volume event table.
    link_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    destination_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    link_version: Mapped[int] = mapped_column(Integer)
    device: Mapped[str] = mapped_column(String(20))
    os: Mapped[str] = mapped_column(String(100))
    browser: Mapped[str] = mapped_column(String(100))
    classification: Mapped[str] = mapped_column(String(10))
    bot_reason: Mapped[str | None] = mapped_column(String(100))
    ruleset: Mapped[str] = mapped_column(String(20), default="ua-v1")
    country: Mapped[str | None] = mapped_column(String(2))
    referrer_origin: Mapped[str | None] = mapped_column(String(300))
    visitor_digest: Mapped[str | None] = mapped_column(String(64))


class DailyStat(Base):
    __tablename__ = "daily_link_stats"
    day: Mapped[date] = mapped_column(primary_key=True)
    link_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    total_clicks: Mapped[int] = mapped_column(BigInteger)
    human_clicks: Mapped[int] = mapped_column(BigInteger)
    bot_clicks: Mapped[int] = mapped_column(BigInteger)
    unknown_clicks: Mapped[int] = mapped_column(BigInteger)
    estimated_unique_visitors: Mapped[int] = mapped_column(BigInteger)
    refreshed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DailyCampaignStat(Base):
    __tablename__ = "daily_campaign_stats"
    day: Mapped[date] = mapped_column(primary_key=True)
    # NULL campaign uses a reserved zero UUID in this aggregate only.
    campaign_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    total_clicks: Mapped[int] = mapped_column(BigInteger)
    human_clicks: Mapped[int] = mapped_column(BigInteger)
    bot_clicks: Mapped[int] = mapped_column(BigInteger)
    unknown_clicks: Mapped[int] = mapped_column(BigInteger)
    estimated_unique_visitors: Mapped[int] = mapped_column(BigInteger)
    refreshed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AggregationState(Base):
    __tablename__ = "aggregation_state"
    name: Mapped[str] = mapped_column(String(30), primary_key=True)
    next_day: Mapped[date] = mapped_column()
    refreshed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    action: Mapped[str] = mapped_column(String(50))
    resource_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    actor: Mapped[str] = mapped_column(String(20), default="admin-key")
    details: Mapped[dict] = mapped_column(JSON, default=dict)
