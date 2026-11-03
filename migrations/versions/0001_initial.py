"""Initial schema; partitioned event store and daily aggregates.

Schema SQL is frozen here so future model changes cannot alter this migration.
"""

from datetime import UTC, datetime

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    statements = [
        """CREATE TABLE campaigns (
            id uuid PRIMARY KEY, name varchar(200) NOT NULL, archived boolean NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now())""",
        """CREATE TABLE links (
            id uuid PRIMARY KEY, slug varchar(80) NOT NULL UNIQUE,
            campaign_id uuid REFERENCES campaigns(id), status varchar(16) NOT NULL,
            expires_at timestamptz, active_destination_id uuid NOT NULL,
            forward_utm boolean NOT NULL, version integer NOT NULL,
            utm_source varchar(200), utm_medium varchar(200), utm_campaign varchar(200),
            utm_content varchar(200), utm_term varchar(200),
            created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT links_status_check CHECK (status IN ('active','disabled','deleted')))""",
        "CREATE INDEX ix_links_campaign_id ON links(campaign_id)",
        """CREATE TABLE link_destinations (
            id uuid PRIMARY KEY, link_id uuid NOT NULL REFERENCES links(id), url varchar(4096) NOT NULL,
            version integer NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (link_id, version), UNIQUE (link_id, id))""",
        "CREATE INDEX ix_link_destinations_link_id ON link_destinations(link_id)",
        # A deferred composite FK enforces that the active destination belongs to its link.
        """ALTER TABLE links ADD CONSTRAINT links_active_destination_fk
            FOREIGN KEY (id, active_destination_id) REFERENCES link_destinations(link_id, id)
            DEFERRABLE INITIALLY DEFERRED""",
        """CREATE TABLE click_events (
            occurred_at timestamptz NOT NULL, click_id uuid NOT NULL,
            link_id uuid NOT NULL, campaign_id uuid, destination_id uuid NOT NULL, link_version integer NOT NULL,
            utm_source varchar(200), utm_medium varchar(200), utm_campaign varchar(200),
            utm_content varchar(200), utm_term varchar(200),
            device varchar(20) NOT NULL, os varchar(100) NOT NULL, browser varchar(100) NOT NULL,
            classification varchar(10) NOT NULL CHECK (classification IN ('human','bot','unknown')),
            bot_reason varchar(100), ruleset varchar(20) NOT NULL, country varchar(2),
            referrer_origin varchar(300), visitor_digest varchar(64),
            PRIMARY KEY (occurred_at, click_id)) PARTITION BY RANGE (occurred_at)""",
        "CREATE INDEX ix_click_link_time ON click_events(link_id, occurred_at)",
        "CREATE INDEX ix_click_campaign_time ON click_events(campaign_id, occurred_at)",
        "CREATE INDEX ix_click_time_brin ON click_events USING brin(occurred_at)",
        """CREATE TABLE daily_link_stats (
            day date NOT NULL, link_id uuid NOT NULL, total_clicks bigint NOT NULL,
            human_clicks bigint NOT NULL, bot_clicks bigint NOT NULL, unknown_clicks bigint NOT NULL,
            estimated_unique_visitors bigint NOT NULL, refreshed_at timestamptz NOT NULL,
            PRIMARY KEY (day, link_id))""",
        """CREATE TABLE aggregation_state (
            name varchar(30) PRIMARY KEY, next_day date NOT NULL, refreshed_at timestamptz NOT NULL)""",
        """CREATE TABLE daily_campaign_stats (
            day date NOT NULL, campaign_id uuid NOT NULL, total_clicks bigint NOT NULL,
            human_clicks bigint NOT NULL, bot_clicks bigint NOT NULL, unknown_clicks bigint NOT NULL,
            estimated_unique_visitors bigint NOT NULL, refreshed_at timestamptz NOT NULL,
            PRIMARY KEY (day, campaign_id))""",
        """CREATE TABLE audit_events (
            id uuid PRIMARY KEY, occurred_at timestamptz NOT NULL DEFAULT now(),
            action varchar(50) NOT NULL, resource_id uuid NOT NULL, actor varchar(20) NOT NULL,
            details json NOT NULL)""",
    ]
    for statement in statements:
        op.execute(statement)
    now = datetime.now(UTC)
    month_index = now.year * 12 + now.month - 1
    for offset in (-1, 0, 1, 2):
        year, month = divmod(month_index + offset, 12)
        next_year, next_month = divmod(month_index + offset + 1, 12)
        month += 1
        next_month += 1
        op.execute(
            f"CREATE TABLE click_events_{year}_{month:02d} PARTITION OF click_events "
            f"FOR VALUES FROM ('{year}-{month:02d}-01') TO ('{next_year}-{next_month:02d}-01')"
        )


def downgrade():
    for table in (
        "audit_events",
        "aggregation_state",
        "daily_campaign_stats",
        "daily_link_stats",
        "click_events",
    ):
        op.execute(f"DROP TABLE {table} CASCADE")
    op.execute("ALTER TABLE links DROP CONSTRAINT links_active_destination_fk")
    for table in ("link_destinations", "links", "campaigns"):
        op.execute(f"DROP TABLE {table}")
