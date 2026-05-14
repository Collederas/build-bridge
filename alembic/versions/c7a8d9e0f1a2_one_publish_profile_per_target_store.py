"""one publish profile per target and store

Revision ID: c7a8d9e0f1a2
Revises: a1b2c3d4e5f6
Create Date: 2026-05-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "c7a8d9e0f1a2"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    duplicate_ids = """
        SELECT pp.id
        FROM publish_profile pp
        WHERE pp.id NOT IN (
            SELECT MIN(kept.id)
            FROM publish_profile kept
            GROUP BY kept.build_target_id, kept.store_type
        )
    """

    op.execute(f"DELETE FROM steam_publish_profile WHERE id IN ({duplicate_ids})")
    op.execute(f"DELETE FROM itch_publish_profile WHERE id IN ({duplicate_ids})")
    op.execute(f"DELETE FROM publish_profile WHERE id IN ({duplicate_ids})")

    with op.batch_alter_table("publish_profile") as batch_op:
        batch_op.create_unique_constraint(
            "uq_publish_profile_target_store",
            ["build_target_id", "store_type"],
        )


def downgrade() -> None:
    with op.batch_alter_table("publish_profile") as batch_op:
        batch_op.drop_constraint(
            "uq_publish_profile_target_store",
            type_="unique",
        )
