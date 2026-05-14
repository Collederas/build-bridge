from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from build_bridge.core.publisher.itch.itch_publisher import (
    validate_itch_channel,
    validate_itch_target,
)
from build_bridge.exceptions import InvalidConfigurationError
from build_bridge.models import StoreEnum


@dataclass
class PreflightIssue:
    label: str
    detail: str = ""
    severity: str = "ok"


@dataclass
class PreflightResult:
    title: str
    issues: list[PreflightIssue] = field(default_factory=list)

    @property
    def has_blockers(self) -> bool:
        return any(issue.severity == "error" for issue in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(issue.severity == "warning" for issue in self.issues)

    def ok(self, label: str, detail: str = ""):
        self.issues.append(PreflightIssue(label=label, detail=detail, severity="ok"))

    def warning(self, label: str, detail: str = ""):
        self.issues.append(
            PreflightIssue(label=label, detail=detail, severity="warning")
        )

    def error(self, label: str, detail: str = ""):
        self.issues.append(PreflightIssue(label=label, detail=detail, severity="error"))


def _truthy(value) -> bool:
    return bool(str(value).strip()) if value is not None else False


def _find_uproject(source_dir: str, recurse_level: int = 1) -> str | None:
    if not source_dir:
        return None

    if os.path.isfile(source_dir) and source_dir.endswith(".uproject"):
        return source_dir

    if not os.path.isdir(source_dir):
        return None

    for root, _, files in os.walk(source_dir):
        if os.path.relpath(root, source_dir).count(os.sep) >= recurse_level:
            continue

        for filename in files:
            if filename.endswith(".uproject"):
                return os.path.join(root, filename)

    return None


def _has_windows_executable(build_root: str) -> bool:
    if not build_root or not os.path.isdir(build_root):
        return False

    try:
        if any(
            filename.lower().endswith(".exe")
            for filename in os.listdir(build_root)
            if os.path.isfile(os.path.join(build_root, filename))
        ):
            return True

        first_subfolder = None
        for item in os.listdir(build_root):
            full_path = os.path.join(build_root, item)
            if os.path.isdir(full_path):
                first_subfolder = full_path
                break

        if not first_subfolder:
            return False

        return any(
            filename.lower().endswith(".exe")
            for filename in os.listdir(first_subfolder)
            if os.path.isfile(os.path.join(first_subfolder, filename))
        )
    except OSError:
        return False


def _check_file(result: PreflightResult, label: str, path: str | None):
    if _truthy(path) and os.path.isfile(str(path)):
        result.ok(label, str(path))
    elif _truthy(path):
        result.error(label, f"File not found: {path}")
    else:
        result.error(label, "Path is not configured.")


def _check_directory(result: PreflightResult, label: str, path: str | None):
    if _truthy(path) and os.path.isdir(str(path)):
        result.ok(label, str(path))
    elif _truthy(path):
        result.error(label, f"Directory not found: {path}")
    else:
        result.error(label, "Path is not configured.")


def validate_build_preflight(build_target, release_name: str) -> PreflightResult:
    result = PreflightResult("Build Preflight")

    if not build_target:
        result.error("Build target", "No build target is selected.")
        return result

    project = getattr(build_target, "project", None)
    if not project:
        result.error("Project", "This build target is not linked to a project.")
        return result

    if _truthy(getattr(project, "name", None)):
        result.ok("Project name", project.name)
    else:
        result.error("Project name", "Project name is missing.")

    source_dir = getattr(project, "source_dir", None)
    _check_directory(result, "Project source", source_dir)

    uproject_path = _find_uproject(source_dir)
    if uproject_path:
        result.ok(".uproject file", uproject_path)
    else:
        result.error(
            ".uproject file",
            "No .uproject file was found in the project source directory.",
        )

    archive_directory = getattr(project, "archive_directory", None)
    _check_directory(result, "Build archive directory", archive_directory)

    if _truthy(release_name):
        result.ok("Build version", release_name)
    else:
        result.error("Build version", "Enter a release/build version.")

    if _truthy(release_name) and hasattr(build_target, "builds_path"):
        try:
            output_dir = build_target.builds_path / str(release_name)
        except Exception:
            output_dir = None

        if output_dir is None:
            result.warning("Output folder", "Could not determine output path.")
        elif output_dir.exists():
            result.warning(
                "Output folder",
                f"Build folder already exists and will require overwrite confirmation: {output_dir}",
            )
        else:
            result.ok("Output folder", str(output_dir))

    engine_path = getattr(build_target, "unreal_engine_base_path", None)
    _check_directory(result, "Unreal Engine path", engine_path)

    if _truthy(engine_path):
        uat_script = (
            Path(str(engine_path))
            / "Engine"
            / "Build"
            / "BatchFiles"
            / ("RunUAT.bat" if os.name == "nt" else "RunUAT.sh")
        )
        _check_file(result, "RunUAT script", str(uat_script))

    target = getattr(build_target, "target", None)
    _check_file(result, "Target file", target)

    build_type = getattr(build_target, "build_type", None)
    if build_type:
        result.ok("Build configuration", getattr(build_type, "value", str(build_type)))
    else:
        result.error("Build configuration", "Build type is not configured.")

    target_platform = getattr(build_target, "target_platform", None)
    if target_platform:
        result.ok("Target platform", getattr(target_platform, "value", str(target_platform)))
    else:
        result.error("Target platform", "Target platform is not configured.")

    maps = getattr(build_target, "maps", None) or {}
    if not maps:
        result.warning(
            "Maps",
            "No maps are explicitly included. Unreal may use project defaults.",
        )
    elif isinstance(maps, dict):
        for map_path in maps.keys():
            if os.path.isfile(str(map_path)) and str(map_path).endswith(".umap"):
                result.ok("Map", str(map_path))
            else:
                result.error("Map", f"Missing or invalid .umap path: {map_path}")
    else:
        result.error("Maps", "Saved map configuration is not valid.")

    return result


def validate_publish_preflight(
    build_root: str,
    publish_profile,
    selected_store: StoreEnum,
) -> PreflightResult:
    result = PreflightResult("Publish Preflight")

    if _truthy(build_root) and os.path.isdir(build_root):
        result.ok("Build folder", build_root)
    else:
        result.error("Build folder", f"Directory not found: {build_root}")

    if _has_windows_executable(build_root):
        result.ok("Build executable", "Found a Windows executable in the build folder.")
    else:
        result.warning(
            "Build executable",
            "No .exe was found in the build folder or its first subfolder.",
        )

    if not publish_profile:
        result.error("Publishing configuration", "Publishing is not configured.")
        return result

    if getattr(publish_profile, "id", None):
        result.ok("Publishing configuration", f"Configuration #{publish_profile.id}")
    else:
        result.error(
            "Publishing configuration",
            "This configuration has not been saved yet. Open Configure and save it first.",
        )

    project = getattr(publish_profile, "project", None)
    if project:
        result.ok("Project", getattr(project, "name", "Configured"))
    else:
        result.error("Project", "Publish profile is not linked to a project.")

    if selected_store == StoreEnum.itch:
        _validate_itch_publish_preflight(result, publish_profile)
    elif selected_store == StoreEnum.steam:
        _validate_steam_publish_preflight(result, publish_profile)
    else:
        result.error("Store", f"No preflight checks are available for {selected_store}.")

    return result


def _validate_itch_publish_preflight(result: PreflightResult, publish_profile):
    itch_config = getattr(publish_profile, "itch_config", None)
    if not itch_config:
        result.error("Itch settings", "Itch.io settings are missing.")
        return

    try:
        validate_itch_target(
            getattr(publish_profile, "itch_user_game_id", None),
            getattr(itch_config, "username", None),
        )
    except InvalidConfigurationError as exc:
        result.error("Itch target", str(exc))
    else:
        result.ok("Itch target", publish_profile.itch_user_game_id)

    try:
        validate_itch_channel(getattr(publish_profile, "itch_channel_name", None))
    except InvalidConfigurationError as exc:
        result.error("Itch channel", str(exc))
    else:
        result.ok("Itch channel", publish_profile.itch_channel_name)

    if _truthy(getattr(itch_config, "username", None)):
        result.ok("Itch username", itch_config.username)
    else:
        result.error("Itch username", "Username is not configured.")

    _check_file(result, "Butler executable", getattr(itch_config, "butler_path", None))

    try:
        api_key = itch_config.api_key
    except Exception as exc:
        result.error("Itch API key", f"Could not read keyring entry: {exc}")
    else:
        if api_key:
            result.ok("Itch API key", "Found in system keyring.")
        else:
            result.error("Itch API key", "API key was not found in system keyring.")


def _validate_steam_publish_preflight(result: PreflightResult, publish_profile):
    steam_config = getattr(publish_profile, "steam_config", None)
    if not steam_config:
        result.error("Steam settings", "Steam settings are missing.")
        return

    if _truthy(getattr(steam_config, "username", None)):
        result.ok("Steam username", steam_config.username)
    else:
        result.error("Steam username", "Username is not configured.")

    _check_file(result, "SteamCMD executable", getattr(steam_config, "steamcmd_path", None))

    try:
        password = steam_config.password
    except Exception as exc:
        result.warning("Steam password", f"Could not read keyring entry: {exc}")
    else:
        if password:
            result.ok("Steam password", "Found in system keyring.")
        else:
            result.warning(
                "Steam password",
                "No password found. SteamCMD may prompt or fail depending on account setup.",
            )

    app_id = getattr(publish_profile, "app_id", None)
    if app_id:
        result.ok("Steam app ID", str(app_id))
    else:
        result.error("Steam app ID", "App ID is not configured.")

    depots = getattr(publish_profile, "depots", None)
    _validate_depots(result, depots)

    builder_path = getattr(publish_profile, "builder_path", None)
    if _truthy(builder_path):
        result.ok("Steam build config folder", str(builder_path))
    else:
        result.error("Steam build config folder", "Could not determine builder path.")


def _validate_depots(result: PreflightResult, depots: Iterable | dict | None):
    if not depots:
        result.error("Steam depots", "No depot mappings are configured.")
        return

    if not isinstance(depots, dict):
        result.error("Steam depots", "Depot mappings are not stored in a valid format.")
        return

    for depot_id, depot_path in depots.items():
        if _truthy(depot_id) and _truthy(depot_path) and os.path.exists(str(depot_path)):
            result.ok(f"Steam depot {depot_id}", str(depot_path))
        elif _truthy(depot_id) and _truthy(depot_path):
            result.error(f"Steam depot {depot_id}", f"Path not found: {depot_path}")
        else:
            result.error("Steam depot", "Depot ID or path is missing.")
