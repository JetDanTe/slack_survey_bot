"""Add survey reminder fields

Revision ID: a1b2c3d4e5f6
Revises: f15d956d1043
Create Date: 2026-02-17 03:24:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "f15d956d1043"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add reminder columns to surveys table."""
    op.add_column(
        "surveys",
        sa.Column(
            "reminder_interval_hours", sa.Float(), nullable=False, server_default="0"
        ),
    )
    op.add_column(
        "surveys",
        sa.Column("last_reminder_sent_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "surveys",
        sa.Column(
            "reminders_sent_count", sa.Integer(), nullable=False, server_default="0"
        ),
    )


def downgrade() -> None:
    """Remove reminder columns from surveys table."""
    op.drop_column("surveys", "reminders_sent_count")
    op.drop_column("surveys", "last_reminder_sent_at")
    op.drop_column("surveys", "reminder_interval_hours")
