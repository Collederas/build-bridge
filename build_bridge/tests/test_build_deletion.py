import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from build_bridge.core.builds import UnsafeBuildPathError, delete_build
from build_bridge.database import Base
from build_bridge.models import (
    Build,
    BuildStatusEnum,
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
        project = Project(
            name="TestGame",
            source_dir="/src",
            archive_directory="/builds",
        )
        sess.add(project)
        sess.flush()

        build_target = BuildTarget(
            project_id=project.id,
            name="Main",
            build_type=BuildTypeEnum.prod,
            target_platform=BuildTargetPlatformEnum.win_64,
        )
        sess.add(build_target)
        sess.commit()
        yield sess


def _add_build(session, output_path: str):
    build_target = session.query(BuildTarget).first()
    build = Build(
        build_target_id=build_target.id,
        version="1.2.3",
        output_path=output_path,
        status=BuildStatusEnum.success,
    )
    session.add(build)
    session.commit()
    return build


def test_delete_build_removes_database_record_only(session, tmp_path):
    build_dir = tmp_path / "Builds" / "TestGame" / "Main" / "1.2.3"
    build_dir.mkdir(parents=True)
    build = _add_build(session, str(build_dir))
    build_id = build.id

    result = delete_build(session, build, delete_from_disk=False)

    assert session.get(Build, build_id) is None
    assert build_dir.exists()
    assert result["disk_deleted"] is False


def test_delete_build_can_remove_directory_from_disk(session, tmp_path):
    build_dir = tmp_path / "Builds" / "TestGame" / "Main" / "1.2.3"
    build_dir.mkdir(parents=True)
    (build_dir / "Game.exe").touch()
    build = _add_build(session, str(build_dir))
    build_id = build.id

    result = delete_build(session, build, delete_from_disk=True)

    assert session.get(Build, build_id) is None
    assert not build_dir.exists()
    assert result["disk_deleted"] is True


def test_delete_build_keeps_record_when_disk_delete_is_unsafe(session, tmp_path):
    build_file = tmp_path / "not-a-build-folder.zip"
    build_file.touch()
    build = _add_build(session, str(build_file))
    build_id = build.id

    with pytest.raises(UnsafeBuildPathError):
        delete_build(session, build, delete_from_disk=True)

    assert session.get(Build, build_id) is not None
    assert build_file.exists()
