"""add client profile fields and event city

Revision ID: 20260614_0001
Revises:
Create Date: 2026-06-14
"""
from alembic import op
import sqlalchemy as sa

revision = "20260614_0001"
down_revision = None
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _indexes(table_name: str) -> set[str]:
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def _create_users_table() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("phone_number", sa.String(length=64), nullable=True),
        sa.Column("first_name", sa.String(length=255), nullable=True),
        sa.Column("last_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_telegram_id"), "users", ["telegram_id"], unique=True)


def _create_events_table() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("city", sa.String(length=120), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("event_time", sa.Time(), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_events_city"), "events", ["city"], unique=False)


def _create_managers_table() -> None:
    op.create_table(
        "managers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_managers_telegram_id"), "managers", ["telegram_id"], unique=True)


def _create_orders_table() -> None:
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("customer_location", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.Enum("NEW", "ACCEPTED", "IN_WORK", "DONE", "CANCELLED", native_enum=False),
            nullable=False,
        ),
        sa.Column("manager_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
        sa.ForeignKeyConstraint(["manager_id"], ["managers.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def upgrade() -> None:
    if not _table_exists("users"):
        _create_users_table()
    else:
        columns = _columns("users")
        if "first_name" not in columns:
            op.add_column("users", sa.Column("first_name", sa.String(length=255), nullable=True))
        if "last_name" not in columns:
            op.add_column("users", sa.Column("last_name", sa.String(length=255), nullable=True))
        if "updated_at" not in columns:
            op.add_column(
                "users",
                sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
            )
        if "updated_at" in _columns("users"):
            op.execute("UPDATE users SET updated_at = COALESCE(created_at, now()) WHERE updated_at IS NULL")
            op.alter_column("users", "updated_at", existing_type=sa.DateTime(timezone=True), nullable=False)

    if not _table_exists("events"):
        _create_events_table()
    else:
        columns = _columns("events")
        if "city" not in columns:
            op.add_column("events", sa.Column("city", sa.String(length=120), nullable=True))
        if "city" in _columns("events"):
            op.execute(
                "UPDATE events "
                "SET city = COALESCE(NULLIF(TRIM(location), ''), 'Не указан') "
                "WHERE city IS NULL OR TRIM(city) = ''"
            )
            op.alter_column("events", "city", existing_type=sa.String(length=120), nullable=False)
        if op.f("ix_events_city") not in _indexes("events"):
            op.create_index(op.f("ix_events_city"), "events", ["city"], unique=False)

    if not _table_exists("managers"):
        _create_managers_table()

    if not _table_exists("orders"):
        _create_orders_table()


def downgrade() -> None:
    if _table_exists("events"):
        indexes = _indexes("events")
        if op.f("ix_events_city") in indexes:
            op.drop_index(op.f("ix_events_city"), table_name="events")
        columns = _columns("events")
        if "city" in columns:
            op.drop_column("events", "city")

    if _table_exists("users"):
        columns = _columns("users")
        if "updated_at" in columns:
            op.drop_column("users", "updated_at")
        if "last_name" in columns:
            op.drop_column("users", "last_name")
        if "first_name" in columns:
            op.drop_column("users", "first_name")
