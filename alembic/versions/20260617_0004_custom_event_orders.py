"""allow custom event orders

Revision ID: 20260617_0004
Revises: 20260617_0003
Create Date: 2026-06-17
"""
from alembic import op
import sqlalchemy as sa

revision = "20260617_0004"
down_revision = "20260617_0003"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def upgrade() -> None:
    if not _table_exists("orders"):
        return

    columns = _columns("orders")

    if "event_id" in columns:
        op.alter_column("orders", "event_id", existing_type=sa.Integer(), nullable=True)

    if "requested_event_title" not in columns:
        op.add_column("orders", sa.Column("requested_event_title", sa.String(length=500), nullable=True))
    if "requested_city" not in _columns("orders"):
        op.add_column("orders", sa.Column("requested_city", sa.String(length=120), nullable=True))
    if "requested_event_type" not in _columns("orders"):
        op.add_column("orders", sa.Column("requested_event_type", sa.String(length=50), nullable=True))
    if "requested_sport_type" not in _columns("orders"):
        op.add_column("orders", sa.Column("requested_sport_type", sa.String(length=50), nullable=True))


def downgrade() -> None:
    if not _table_exists("orders"):
        return

    columns = _columns("orders")
    for column_name in (
        "requested_sport_type",
        "requested_event_type",
        "requested_city",
        "requested_event_title",
    ):
        if column_name in columns:
            op.drop_column("orders", column_name)

    if "event_id" in _columns("orders"):
        op.execute("DELETE FROM orders WHERE event_id IS NULL")
        op.alter_column("orders", "event_id", existing_type=sa.Integer(), nullable=False)
