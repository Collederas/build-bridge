"""add app state active project

Revision ID: e3f4a5b6c7d8
Revises: c7a8d9e0f1a2
Create Date: 2026-05-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e3f4a5b6c7d8"
down_revision: Union[str, None] = "c7a8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_state",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("active_project_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["active_project_id"], ["project.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.execute(
        """
        INSERT INTO app_state (active_project_id)
        SELECT id FROM project ORDER BY id ASC LIMIT 1
        """
    )

    op.execute(
        """
        INSERT INTO app_state (active_project_id)
        SELECT NULL
        WHERE NOT EXISTS (SELECT 1 FROM app_state)
        """
    )


def downgrade() -> None:
    op.drop_table("app_state")

