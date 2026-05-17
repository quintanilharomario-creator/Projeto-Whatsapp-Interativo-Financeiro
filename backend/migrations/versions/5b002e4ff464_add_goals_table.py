"""add_goals_table

Revision ID: 5b002e4ff464
Revises: b7e3f1a2c894
Create Date: 2026-05-16 22:39:18.332265

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "5b002e4ff464"
down_revision: Union[str, None] = "b7e3f1a2c894"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "goals",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("target_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_goals_user_id"), "goals", ["user_id"], unique=False)
    op.create_index(
        "ix_goals_user_id_active", "goals", ["user_id", "is_active"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_goals_user_id_active", table_name="goals")
    op.drop_index(op.f("ix_goals_user_id"), table_name="goals")
    op.drop_table("goals")
