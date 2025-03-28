# tests/test_unreal_builder.py
import pytest
from unittest.mock import patch, MagicMock
import json
from PyQt6.QtWidgets import QDialog
from PyQt6.QtCore import QProcess
from build.unreal_builder import UnrealBuilder


@pytest.fixture
def unreal_builder():
    return UnrealBuilder(parent=None)


def test_get_unreal_engine_version_success(unreal_builder):
    # Mock the file system to simulate a valid .uproject file
    mock_uproject_data = {"EngineAssociation": "5.5"}
    with patch("builtins.open", new=MagicMock()) as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(
            mock_uproject_data
        )
        with patch("os.path.exists", return_value=True):
            engine_version = unreal_builder.get_unreal_engine_version(
                "fake/path/MyGame.uproject"
            )
            assert engine_version == "5.5"


def test_get_unreal_engine_version_file_not_found(unreal_builder):
    # Simulate the .uproject file not existing
    with patch("os.path.exists", return_value=False):
        engine_version = unreal_builder.get_unreal_engine_version(
            "fake/path/MyGame.uproject"
        )
        assert engine_version is None


def test_get_unreal_engine_version_missing_engine_association(unreal_builder):
    # Simulate a .uproject file with no EngineAssociation
    mock_uproject_data = {}
    with patch("builtins.open", new=MagicMock()) as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(
            mock_uproject_data
        )
        with patch("os.path.exists", return_value=True):
            engine_version = unreal_builder.get_unreal_engine_version(
                "fake/path/MyGame.uproject"
            )
            assert engine_version is None


def test_get_unreal_engine_version_invalid_json(unreal_builder):
    # Simulate a .uproject file with invalid JSON
    with patch("builtins.open", new=MagicMock()) as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = "invalid json"
        with patch("os.path.exists", return_value=True):
            engine_version = unreal_builder.get_unreal_engine_version(
                "fake/path/MyGame.uproject"
            )
            assert engine_version is None


def test_check_unreal_engine_installed_version_exists(unreal_builder):
    # Simulate the Unreal Engine version being installed
    with patch("os.path.exists", return_value=True):
        result = unreal_builder.check_unreal_engine_installed("5.5")
        assert result is True


def test_check_unreal_engine_installed_version_missing(unreal_builder):
    # Simulate the Unreal Engine version not being installed
    with patch("os.path.exists", return_value=False):
        result = unreal_builder.check_unreal_engine_installed("5.5")
        assert result is False


def test_run_unreal_build_success(unreal_builder):
    with patch("os.path.exists", return_value=True):
        with patch("sys.platform", "win32"):

            mock_process = MagicMock(spec=QProcess)
            mock_process.exitCode.return_value = 0
            mock_process.state.return_value = QProcess.ProcessState.NotRunning

            # Patch QProcess to return our mock instance
            with patch("build.unreal_builder.QProcess", return_value=mock_process):
                # Mock the dialog
                mock_dialog = MagicMock()
                mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
                
                with patch("build.unreal_builder.BuildProgressDialog", return_value=mock_dialog):
                    success = unreal_builder.run_unreal_build(
                        "//MyGame/release_0.2.2",
                        "C:/P4Workspace/MyGame.uproject",
                        "5.5"
                    )
                    
                    mock_process.start.assert_called_once()
                    assert success is True


def test_run_unreal_build_uat_script_missing(unreal_builder):
    with patch("os.path.exists", return_value=False):
        success = unreal_builder.run_unreal_build(
            "//MyGame/release_0.2.2",
            "C:/P4Workspace/MyGame.uproject",
            "5.5"
        )
        assert success is False

def test_run_unreal_build_user_cancel(unreal_builder):
    with patch("os.path.exists", return_value=True):
        with patch("sys.platform", "win32"):
            # Create a mock process with a method to simulate state
            mock_process = MagicMock(spec=QProcess)
            
            # Explicitly set up the state method to return the actual enum value
            mock_process.state.return_value = QProcess.ProcessState.Running
            mock_process.exitCode.return_value = 0

            # Patch QProcess to return our mock instance
            with patch("build.unreal_builder.QProcess", return_value=mock_process) as mock_qprocess:
                mock_qprocess.ProcessState.Running = QProcess.ProcessState.Running
                # Mock the dialog
                mock_dialog = MagicMock()
                mock_dialog.exec.return_value = QDialog.DialogCode.Rejected

                with patch("build.unreal_builder.BuildProgressDialog", return_value=mock_dialog):
                    # Explicitly set the process on the unreal_builder
                    unreal_builder.process = mock_process

                    # Call the method
                    success = unreal_builder.run_unreal_build(
                        "//MyGame/release_0.2.2",
                        "C:/P4Workspace/MyGame.uproject",
                        "5.5"
                    )
                    
                    # Assert that kill was called and the return value is False
                    mock_process.kill.assert_called_once()
                    assert success is False
