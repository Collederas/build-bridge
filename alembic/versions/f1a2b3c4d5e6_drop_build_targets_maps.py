"""drop build_targets.maps

Revision ID: f1a2b3c4d5e6
Revises: e3f4a5b6c7d8
Create Date: 2026-06-09 00:00:00.000000

The maps field never restricted what Unreal cooked (-map is additive; the
cook is governed by ProjectPackagingSettings), so the per-target map list was
removed. This drops the now-unused column.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'e3f4a5b6c7d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("build_targets") as batch_op:
        batch_op.drop_column("maps")


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("build_targets") as batch_op:
        batch_op.add_column(sa.Column("maps", sa.JSON(), nullable=True))
