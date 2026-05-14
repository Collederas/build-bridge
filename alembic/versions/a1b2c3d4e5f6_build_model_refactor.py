"""build model refactor: add Build entity, move publish profiles to BuildTarget

Revision ID: a1b2c3d4e5f6
Revises: 9ee7c83a755f
Create Date: 2026-05-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '9ee7c83a755f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add name column to build_targets (nullable first for backfill)
    with op.batch_alter_table('build_targets') as batch_op:
        batch_op.add_column(sa.Column('name', sa.String(), nullable=True))

    # 2. Backfill name with empty string
    op.execute("UPDATE build_targets SET name = ''")

    # 3. Make name non-nullable (batch required for SQLite)
    with op.batch_alter_table('build_targets') as batch_op:
        batch_op.alter_column('name', nullable=False, server_default='')

    # 4. Create builds table
    op.create_table(
        'builds',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('build_target_id', sa.Integer(), nullable=False),
        sa.Column('version', sa.String(), nullable=False),
        sa.Column('output_path', sa.String(), nullable=False),
        sa.Column('status', sa.Enum('in_progress', 'success', 'failed', name='buildstatusenum'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('vcs_commit', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['build_target_id'], ['build_targets.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )

    # 5. Add build_target_id to publish_profile (nullable first for backfill)
    with op.batch_alter_table('publish_profile') as batch_op:
        batch_op.add_column(sa.Column('build_target_id', sa.Integer(), nullable=True))

    # 6. Backfill build_target_id: assign each profile to the first build_target of its project
    op.execute("""
        UPDATE publish_profile
        SET build_target_id = (
            SELECT bt.id
            FROM build_targets bt
            WHERE bt.project_id = publish_profile.project_id
            ORDER BY bt.id ASC
            LIMIT 1
        )
    """)

    # 7. Make build_target_id non-nullable and create FK; drop old columns
    with op.batch_alter_table('publish_profile') as batch_op:
        batch_op.alter_column('build_target_id', nullable=False)
        batch_op.create_foreign_key(
            'fk_publish_profile_build_target_id',
            'build_targets',
            ['build_target_id'], ['id']
        )
        batch_op.drop_column('build_id')
        batch_op.drop_column('project_id')


def downgrade() -> None:
    # Restore project_id and build_id as nullable
    with op.batch_alter_table('publish_profile') as batch_op:
        batch_op.add_column(sa.Column('project_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('build_id', sa.String(), nullable=True))

    # Backfill project_id from build_target
    op.execute("""
        UPDATE publish_profile
        SET project_id = (
            SELECT bt.project_id
            FROM build_targets bt
            WHERE bt.id = publish_profile.build_target_id
        )
    """)

    # Drop build_target_id FK and column
    with op.batch_alter_table('publish_profile') as batch_op:
        batch_op.drop_constraint('fk_publish_profile_build_target_id', type_='foreignkey')
        batch_op.drop_column('build_target_id')

    # Drop builds table
    op.drop_table('builds')

    # Drop build_targets.name
    with op.batch_alter_table('build_targets') as batch_op:
        batch_op.drop_column('name')
