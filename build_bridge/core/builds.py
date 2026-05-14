import shutil
from pathlib import Path

from build_bridge.models import Build, BuildStatusEnum


class BuildDeletionError(RuntimeError):
    pass


class UnsafeBuildPathError(BuildDeletionError):
    pass


def delete_build(session, build: Build, delete_from_disk: bool = False) -> dict:
    result = {
        "disk_path": build.output_path,
        "disk_deleted": False,
        "disk_missing": False,
    }

    if delete_from_disk:
        result["disk_missing"] = bool(
            not build.output_path or not Path(build.output_path).exists()
        )
        _delete_build_directory(build.output_path)
        result["disk_deleted"] = not result["disk_missing"]
    elif build.output_path and not Path(build.output_path).exists():
        result["disk_missing"] = True

    session.delete(build)
    session.commit()
    return result


def register_successful_build(
    session,
    build_target_id: int,
    version: str,
    output_path: str,
) -> Build:
    build = Build(
        build_target_id=build_target_id,
        version=version,
        output_path=output_path,
        status=BuildStatusEnum.success,
    )
    session.add(build)
    session.commit()
    return build


def _delete_build_directory(output_path: str):
    if not output_path:
        raise UnsafeBuildPathError("Build output path is empty.")

    build_path = Path(output_path).expanduser().resolve()

    if not build_path.exists():
        return

    if not build_path.is_dir():
        raise UnsafeBuildPathError(f"Build output path is not a directory: {build_path}")

    if _is_unsafe_delete_root(build_path):
        raise UnsafeBuildPathError(f"Refusing to delete unsafe path: {build_path}")

    shutil.rmtree(build_path)


def _is_unsafe_delete_root(path: Path) -> bool:
    return path == Path(path.anchor) or path == Path.home().resolve()
