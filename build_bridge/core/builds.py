import re
import shutil
from pathlib import Path

from build_bridge.models import Build, BuildStatusEnum


class BuildDeletionError(RuntimeError):
    pass


class BuildExistsError(RuntimeError):
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


def latest_build_for_target(session, build_target_id: int):
    """The most recent build recorded for a target, or None."""
    return (
        session.query(Build)
        .filter(Build.build_target_id == build_target_id)
        .order_by(Build.created_at.desc(), Build.id.desc())
        .first()
    )


def bump_version(version: str) -> str:
    """Increment the trailing integer of a version string.

    "0.3" -> "0.4", "1.0.2" -> "1.0.3". A version whose tail isn't numeric
    ("0.2-beta") is returned unchanged for the user to edit by hand.
    """
    version = version.strip()
    match = re.search(r"\d+$", version)
    if not match:
        return version
    return f"{version[: match.start()]}{int(match.group()) + 1}"


def suggest_next_version(session, build_target_id: int, seed: str = "0.1") -> str:
    """Version to prefill for the next build: the last build's version bumped,
    or a seed when the target has no builds yet."""
    latest = latest_build_for_target(session, build_target_id)
    if latest and latest.version:
        return bump_version(latest.version)
    return seed


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


def prepare_build_output_directory(output_path: str, overwrite: bool = False):
    build_path = Path(output_path).expanduser().resolve()

    if build_path.exists():
        if not overwrite:
            raise BuildExistsError(f"Build output path already exists: {build_path}")
        _clear_build_directory_contents(build_path)


def _clear_build_directory_contents(build_path: Path):
    if not build_path.is_dir():
        raise UnsafeBuildPathError(f"Build output path is not a directory: {build_path}")

    if _is_unsafe_delete_root(build_path):
        raise UnsafeBuildPathError(f"Refusing to clear unsafe path: {build_path}")

    try:
        for child in build_path.iterdir():
            if child.is_dir() and not child.is_symlink():
                shutil.rmtree(child)
            else:
                child.unlink()
    except OSError as exc:
        raise BuildDeletionError(f"Failed to clear build output path: {exc}") from exc


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

    try:
        shutil.rmtree(build_path)
    except OSError as exc:
        raise BuildDeletionError(f"Failed to delete build output path: {exc}") from exc


def _is_unsafe_delete_root(path: Path) -> bool:
    return path == Path(path.anchor) or path == Path.home().resolve()
