"""de-conflate build target: project-level engine/target, project-scoped publish profiles

Revision ID: b7c1d2e3f4a5
Revises: f1a2b3c4d5e6
Create Date: 2026-06-09 00:00:00.000000

Moves the engine path and the .Target.cs off BuildTarget onto Project (a .uproject
has exactly one of each), and re-parents PublishProfile from a build target to the
project (one profile per store per game). Where a project's targets disagree on the
moved values, the most-recent target (highest id) wins; conflicts are logged. Also enforces
recipe uniqueness on build targets: (project, name, platform, build_type).
"""
from typing import Sequence, Union
import logging

from alembic import op
import sqlalchemy as sa


revision: str = "b7c1d2e3f4a5"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

log = logging.getLogger("alembic.runtime.migration")


def _log_field_conflicts(bind) -> None:
    """Warn where a project's build targets disagree on a moved field."""
    rows = bind.exec_driver_sql(
        """
        SELECT project_id,
               COUNT(DISTINCT IFNULL(unreal_engine_base_path, '')) AS engines,
               COUNT(DISTINCT IFNULL(target, '')) AS targets
        FROM build_targets
        GROUP BY project_id
        HAVING engines > 1 OR targets > 1
        """
    ).fetchall()
    for project_id, engines, targets in rows:
        log.warning(
            "Project %s has build targets disagreeing on %s%s%s; keeping the "
            "most-recent target's value.",
            project_id,
            "engine path" if engines > 1 else "",
            " and " if engines > 1 and targets > 1 else "",
            "target.cs" if targets > 1 else "",
        )


def upgrade() -> None:
    bind = op.get_bind()

    # --- 1. Engine path + target.cs: BuildTarget -> Project ------------------
    with op.batch_alter_table("project") as batch_op:
        batch_op.add_column(sa.Column("unreal_engine_base_path", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("target", sa.String(), nullable=True))

    _log_field_conflicts(bind)

    # Backfill from the most-recent (highest id) build target per project.
    op.execute(
        """
        UPDATE project SET
            unreal_engine_base_path = (
                SELECT bt.unreal_engine_base_path FROM build_targets bt
                WHERE bt.project_id = project.id
                ORDER BY bt.id DESC LIMIT 1
            ),
            target = (
                SELECT bt.target FROM build_targets bt
                WHERE bt.project_id = project.id
                ORDER BY bt.id DESC LIMIT 1
            )
        WHERE EXISTS (SELECT 1 FROM build_targets bt WHERE bt.project_id = project.id)
        """
    )

    # --- 2. PublishProfile: build_target_id -> project_id --------------------
    with op.batch_alter_table("publish_profile") as batch_op:
        batch_op.add_column(sa.Column("project_id", sa.Integer(), nullable=True))

    op.execute(
        """
        UPDATE publish_profile SET project_id = (
            SELECT bt.project_id FROM build_targets bt
            WHERE bt.id = publish_profile.build_target_id
        )
        """
    )

    # Collapsing many targets -> one project can make two profiles collide on
    # (project, store). Keep the one on the most-recent target; drop the rest.
    duplicate_ids = """
        SELECT pp.id FROM publish_profile pp
        WHERE pp.id <> (
            SELECT pp2.id FROM publish_profile pp2
            JOIN build_targets bt2 ON bt2.id = pp2.build_target_id
            WHERE pp2.project_id = pp.project_id AND pp2.store_type = pp.store_type
            ORDER BY bt2.id DESC, pp2.id DESC LIMIT 1
        )
    """
    op.execute(f"DELETE FROM steam_publish_profile WHERE id IN ({duplicate_ids})")
    op.execute(f"DELETE FROM itch_publish_profile WHERE id IN ({duplicate_ids})")
    op.execute(f"DELETE FROM publish_profile WHERE id IN ({duplicate_ids})")

    # Any profile with no resolvable project is orphaned data; remove it so the
    # NOT NULL + FK can be enforced.
    op.execute("DELETE FROM steam_publish_profile WHERE id IN (SELECT id FROM publish_profile WHERE project_id IS NULL)")
    op.execute("DELETE FROM itch_publish_profile WHERE id IN (SELECT id FROM publish_profile WHERE project_id IS NULL)")
    op.execute("DELETE FROM publish_profile WHERE project_id IS NULL")

    with op.batch_alter_table("publish_profile") as batch_op:
        batch_op.drop_constraint("uq_publish_profile_target_store", type_="unique")
        batch_op.drop_column("build_target_id")
        batch_op.alter_column("project_id", existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key(
            "fk_publish_profile_project", "project", ["project_id"], ["id"]
        )
        batch_op.create_unique_constraint(
            "uq_publish_profile_project_store", ["project_id", "store_type"]
        )

    # --- 3. Build targets: drop moved columns, enforce recipe uniqueness ----
    # A recipe is (project, name, platform, build_type). Collapse any duplicates
    # onto the most-recent target (reassigning its builds) before adding the
    # constraint, so existing data can't block the upgrade.
    survivors = """
        SELECT MAX(id) FROM build_targets
        GROUP BY project_id, name, target_platform, build_type
    """
    op.execute(
        f"""
        UPDATE builds SET build_target_id = (
            SELECT MAX(bt2.id)
            FROM build_targets bt2, build_targets bt1
            WHERE bt1.id = builds.build_target_id
              AND bt2.project_id = bt1.project_id
              AND bt2.name = bt1.name
              AND bt2.target_platform = bt1.target_platform
              AND bt2.build_type = bt1.build_type
        )
        WHERE build_target_id NOT IN ({survivors})
        """
    )
    op.execute(f"DELETE FROM build_targets WHERE id NOT IN ({survivors})")

    with op.batch_alter_table("build_targets") as batch_op:
        batch_op.drop_column("unreal_engine_base_path")
        batch_op.drop_column("target")
        batch_op.create_unique_constraint(
            "uq_build_target_recipe",
            ["project_id", "name", "target_platform", "build_type"],
        )


def downgrade() -> None:
    # Restore the moved columns on build_targets (values are re-seeded from the
    # project where possible).
    with op.batch_alter_table("build_targets") as batch_op:
        batch_op.drop_constraint("uq_build_target_recipe", type_="unique")
        batch_op.add_column(sa.Column("unreal_engine_base_path", sa.String(), nullable=True))
        batch_op.add_column(
            sa.Column("target", sa.String(), nullable=True, server_default="MyTarget.Target.cs")
        )

    op.execute(
        """
        UPDATE build_targets SET
            unreal_engine_base_path = (
                SELECT p.unreal_engine_base_path FROM project p WHERE p.id = build_targets.project_id
            ),
            target = (
                SELECT p.target FROM project p WHERE p.id = build_targets.project_id
            )
        """
    )

    # Re-parent publish profiles back to a build target (the most-recent one for
    # the project, matching the upgrade's collapse rule).
    with op.batch_alter_table("publish_profile") as batch_op:
        batch_op.add_column(sa.Column("build_target_id", sa.Integer(), nullable=True))

    op.execute(
        """
        UPDATE publish_profile SET build_target_id = (
            SELECT bt.id FROM build_targets bt
            WHERE bt.project_id = publish_profile.project_id
            ORDER BY bt.id DESC LIMIT 1
        )
        """
    )
    op.execute("DELETE FROM steam_publish_profile WHERE id IN (SELECT id FROM publish_profile WHERE build_target_id IS NULL)")
    op.execute("DELETE FROM itch_publish_profile WHERE id IN (SELECT id FROM publish_profile WHERE build_target_id IS NULL)")
    op.execute("DELETE FROM publish_profile WHERE build_target_id IS NULL")

    with op.batch_alter_table("publish_profile") as batch_op:
        batch_op.drop_constraint("uq_publish_profile_project_store", type_="unique")
        batch_op.drop_constraint("fk_publish_profile_project", type_="foreignkey")
        batch_op.drop_column("project_id")
        batch_op.alter_column("build_target_id", existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key(
            "fk_publish_profile_build_target", "build_targets", ["build_target_id"], ["id"]
        )
        batch_op.create_unique_constraint(
            "uq_publish_profile_target_store", ["build_target_id", "store_type"]
        )

    with op.batch_alter_table("project") as batch_op:
        batch_op.drop_column("target")
        batch_op.drop_column("unreal_engine_base_path")
