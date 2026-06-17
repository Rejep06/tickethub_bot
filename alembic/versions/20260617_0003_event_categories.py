"""add event categories

Revision ID: 20260617_0003
Revises: 20260615_0002
Create Date: 2026-06-17
"""
from alembic import op
import sqlalchemy as sa

revision = "20260617_0003"
down_revision = "20260615_0002"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _indexes(table_name: str) -> set[str]:
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def upgrade() -> None:
    if not _table_exists("events"):
        return

    columns = _columns("events")

    if "event_type" not in columns:
        op.add_column(
            "events",
            sa.Column("event_type", sa.String(length=50), server_default="sport", nullable=True),
        )
        op.execute("UPDATE events SET event_type = 'sport' WHERE event_type IS NULL OR TRIM(event_type) = ''")
        op.alter_column("events", "event_type", existing_type=sa.String(length=50), nullable=False)

    if "sport_type" not in _columns("events"):
        op.add_column("events", sa.Column("sport_type", sa.String(length=50), nullable=True))
        op.execute(
            "UPDATE events SET sport_type = 'football' "
            "WHERE event_type = 'sport' AND (sport_type IS NULL OR TRIM(sport_type) = '')"
        )

    indexes = _indexes("events")
    if op.f("ix_events_event_type") not in indexes:
        op.create_index(op.f("ix_events_event_type"), "events", ["event_type"], unique=False)
    if op.f("ix_events_sport_type") not in _indexes("events"):
        op.create_index(op.f("ix_events_sport_type"), "events", ["sport_type"], unique=False)


def downgrade() -> None:
    if not _table_exists("events"):
        return

    indexes = _indexes("events")
    if op.f("ix_events_sport_type") in indexes:
        op.drop_index(op.f("ix_events_sport_type"), table_name="events")
    if op.f("ix_events_event_type") in indexes:
        op.drop_index(op.f("ix_events_event_type"), table_name="events")

    columns = _columns("events")
    if "sport_type" in columns:
        op.drop_column("events", "sport_type")
    if "event_type" in columns:
        op.drop_column("events", "event_type")
