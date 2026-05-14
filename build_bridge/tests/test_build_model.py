import os
import pytest
from pathlib import Path
from sqlalchemy.exc import IntegrityError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from build_bridge.database import Base
from build_bridge.models import (
    Build,
    BuildStatusEnum,
    BuildTarget,
    BuildTargetPlatformEnum,
    BuildTypeEnum,
    ItchConfig,
    ItchPublishProfile,
    Project,
    StoreEnum,
)


@pytest.fixture
def engine(tmp_path):
    db_path = tmp_path / "test.db"
    eng = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)


@pytest.fixture
def session(engine):
    with Session(engine) as sess:
        project = Project(
            name="TestGame",
            source_dir="/src",
            archive_directory="/builds",
        )
        sess.add(project)
        sess.flush()

        bt = BuildTarget(
            project_id=project.id,
            name="Main",
            build_type=BuildTypeEnum.prod,
            target_platform=BuildTargetPlatformEnum.win_64,
        )
        sess.add(bt)
        sess.commit()
        yield sess


class TestBuildModel:
    def test_build_creation_default_status(self, session):
        bt = session.query(BuildTarget).first()
        build = Build(
            build_target_id=bt.id,
            version="1.0.0",
            output_path="/builds/TestGame/Main/1.0.0",
        )
        session.add(build)
        session.commit()

        fetched = session.get(Build, build.id)
        assert fetched is not None
        assert fetched.version == "1.0.0"
        assert fetched.status == BuildStatusEnum.in_progress
        assert fetched.created_at is not None

    def test_build_status_transitions(self, session):
        bt = session.query(BuildTarget).first()
        build = Build(
            build_target_id=bt.id,
            version="1.1.0",
            output_path="/builds/TestGame/Main/1.1.0",
        )
        session.add(build)
        session.commit()

        build.status = BuildStatusEnum.success
        session.commit()
        assert session.get(Build, build.id).status == BuildStatusEnum.success

        build.status = BuildStatusEnum.failed
        session.commit()
        assert session.get(Build, build.id).status == BuildStatusEnum.failed

    def test_cascade_delete_builds_with_target(self, session):
        bt = session.query(BuildTarget).first()
        build = Build(
            build_target_id=bt.id,
            version="2.0.0",
            output_path="/builds/TestGame/Main/2.0.0",
        )
        session.add(build)
        session.commit()
        build_id = build.id

        session.delete(bt)
        session.commit()

        assert session.get(Build, build_id) is None

    def test_builds_path_structure(self, tmp_path):
        project = Project(
            name="MyGame",
            source_dir=str(tmp_path),
            archive_directory=str(tmp_path / "Builds"),
        )
        bt = BuildTarget(
            project=project,
            name="Demo",
            build_type=BuildTypeEnum.prod,
            target_platform=BuildTargetPlatformEnum.win_64,
        )

        expected = Path(str(tmp_path / "Builds")) / "MyGame" / "Demo"
        assert bt.builds_path == expected

    def test_build_target_name_in_repr(self, session):
        bt = session.query(BuildTarget).first()
        assert "Main" in repr(bt)
        assert "Win64" in repr(bt)

    def test_build_target_has_one_publish_profile_per_store(self, session):
        bt = session.query(BuildTarget).first()
        auth = ItchConfig(username="tester")
        session.add(auth)
        session.flush()

        first = ItchPublishProfile(
            build_target_id=bt.id,
            store_type=StoreEnum.itch,
            description="Main",
            itch_user_game_id="tester/game",
            itch_channel_name="windows",
            itch_config_id=auth.id,
        )
        second = ItchPublishProfile(
            build_target_id=bt.id,
            store_type=StoreEnum.itch,
            description="Duplicate",
            itch_user_game_id="tester/game",
            itch_channel_name="windows-beta",
            itch_config_id=auth.id,
        )
        session.add_all([first, second])

        with pytest.raises(IntegrityError):
            session.commit()
