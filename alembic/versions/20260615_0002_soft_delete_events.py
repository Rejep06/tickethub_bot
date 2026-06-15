"""soft delete events

Revision ID: 20260615_0002
Revises: 20260614_0001
Create Date: 2026-06-15
"""
from alembic import op
import sqlalchemy as sa

revision = "20260615_0002"
down_revision = "20260614_0001"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def upgrade() -> None:
    if not _table_exists("events"):
        return

    columns = _columns("events")
    if "is_active" not in columns:
        op.add_column(
            "events",
            sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=True),
        )
        op.execute("UPDATE events SET is_active = true WHERE is_active IS NULL")
        op.alter_column("events", "is_active", existing_type=sa.Boolean(), nullable=False)

    if "deleted_at" not in _columns("events"):
        op.add_column("events", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    if not _table_exists("events"):
        return

    columns = _columns("events")
    if "deleted_at" in columns:
        op.drop_column("events", "deleted_at")
    if "is_active" in columns:
        op.drop_column("events", "is_active")
