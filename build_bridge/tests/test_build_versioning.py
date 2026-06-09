import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from build_bridge.core.builds import (
    bump_version,
    register_successful_build,
    suggest_next_version,
)
from build_bridge.database import Base
from build_bridge.models import (
    BuildTarget,
    BuildTargetPlatformEnum,
    BuildTypeEnum,
    Project,
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
        project = Project(name="TestGame", source_dir="/src", archive_directory="/builds")
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


class TestBumpVersion:
    @pytest.mark.parametrize(
        "version,expected",
        [
            ("0.3", "0.4"),
            ("1.0.2", "1.0.3"),
            ("9", "10"),
            ("1.0.9", "1.0.10"),
            (" 0.3 ", "0.4"),
        ],
    )
    def test_numeric_tail_is_incremented(self, version, expected):
        assert bump_version(version) == expected

    @pytest.mark.parametrize("version", ["0.2-beta", "rc", ""])
    def test_non_numeric_tail_is_left_for_manual_edit(self, version):
        assert bump_version(version) == version.strip()


class TestSuggestNextVersion:
    def test_seed_when_target_has_no_builds(self, session):
        bt = session.query(BuildTarget).first()
        assert suggest_next_version(session, bt.id) == "0.1"
        assert suggest_next_version(session, bt.id, seed="1.0") == "1.0"

    def test_bumps_the_most_recent_build(self, session):
        bt = session.query(BuildTarget).first()
        register_successful_build(session, bt.id, "0.3", "/builds/0.3")
        register_successful_build(session, bt.id, "0.4", "/builds/0.4")

        assert suggest_next_version(session, bt.id) == "0.5"
