import os
import pytest
from unittest.mock import MagicMock, patch

from build_bridge.core.preflight import validate_build_preflight, validate_publish_preflight
from build_bridge.core.publisher.steam.steam_publisher import check_steam_success
from build_bridge.models import StoreEnum


def _make_build_target(tmp_path):
    uproject = tmp_path / "MyGame.uproject"
    uproject.write_text('{"EngineAssociation": "5.3"}')

    engine_dir = tmp_path / "UE_5.3"
    engine_dir.mkdir()
    (engine_dir / "Engine" / "Build" / "BatchFiles").mkdir(parents=True)
    (engine_dir / "Engine" / "Build" / "BatchFiles" / "RunUAT.bat").touch()
    (engine_dir / "Engine" / "Build" / "BatchFiles" / "RunUAT.sh").touch()

    target_file = tmp_path / "MyGame.Target.cs"
    target_file.touch()

    project = MagicMock()
    project.name = "MyGame"
    project.source_dir = str(tmp_path)
    project.archive_directory = str(tmp_path / "Builds")
    (tmp_path / "Builds").mkdir()

    bt = MagicMock()
    bt.project = project
    bt.name = "Main"
    bt.builds_path = tmp_path / "Builds" / "MyGame" / "Main"
    bt.unreal_engine_base_path = str(engine_dir)
    bt.target = str(target_file)
    bt.build_type = MagicMock(value="Shipping")
    bt.target_platform = MagicMock(value="Win64")
    bt.maps = {}
    return bt


class TestBuildPreflight:
    def test_valid_config_has_no_blockers(self, tmp_path):
        bt = _make_build_target(tmp_path)
        result = validate_build_preflight(bt, "1.0.0")
        assert not result.has_blockers

    def test_missing_release_name_is_blocker(self, tmp_path):
        bt = _make_build_target(tmp_path)
        result = validate_build_preflight(bt, "")
        assert result.has_blockers
        labels = [i.label for i in result.issues if i.severity == "error"]
        assert "Build version" in labels

    def test_missing_engine_path_is_blocker(self, tmp_path):
        bt = _make_build_target(tmp_path)
        bt.unreal_engine_base_path = str(tmp_path / "nonexistent_engine")
        result = validate_build_preflight(bt, "1.0.0")
        assert result.has_blockers

    def test_none_build_target_returns_single_blocker(self):
        result = validate_build_preflight(None, "1.0.0")
        assert result.has_blockers
        assert len(result.issues) == 1

    def test_existing_output_folder_is_warning_not_error(self, tmp_path):
        bt = _make_build_target(tmp_path)
        existing = tmp_path / "Builds" / "MyGame" / "Main" / "1.0.0"
        existing.mkdir(parents=True)
        result = validate_build_preflight(bt, "1.0.0")
        warning_labels = [i.label for i in result.issues if i.severity == "warning"]
        assert "Output folder" in warning_labels
        assert not result.has_blockers


class TestCheckSteamSuccess:
    def test_successful_upload_returns_true(self):
        log = "Logging in user '...' to Steam Public...OK\nApp build successful\n"
        assert check_steam_success(0, log) is True

    def test_nonzero_exit_code_returns_false(self):
        log = "Logging in user '...' to Steam Public...OK\nApp build successful\n"
        assert check_steam_success(1, log) is False

    def test_error_in_log_returns_false(self):
        log = "Logging in user '...' to Steam Public...OK\nApp build successful\nError: upload failed\n"
        assert check_steam_success(0, log) is False

    def test_missing_login_confirmation_returns_false(self):
        log = "App build successful\n"
        assert check_steam_success(0, log) is False
