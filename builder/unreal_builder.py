import os, sys, json
from typing import Optional
from PyQt6.QtWidgets import QMessageBox, QVBoxLayout, QTextEdit, QPushButton, QDialog
from PyQt6.QtCore import QProcess


class BuildError(Exception):
    """Base exception for build-related errors."""

    pass


class ProjectFileNotFoundError(BuildError):
    """Raised when the project file is not found."""

    pass


class EngineVersionError(BuildError):
    """Raised when the engine version cannot be determined or is invalid."""

    pass


class UnrealEngineNotInstalledError(BuildError):
    """Raised when the required Unreal Engine version is not installed."""

    pass


class UATScriptNotFoundError(BuildError):
    """Raised when the UAT script is not found."""

    pass


class CleanupError(BuildError):
    """Raised when cleanup of build artifacts fails."""

    pass


# TODO: decouple this ui layer stuff from this module
class BuildProgressDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Build Progress")
        self.setGeometry(100, 100, 600, 400)
        layout = QVBoxLayout(self)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        layout.addWidget(self.cancel_button)

    def append_log(self, text: str):
        self.log_output.append(text)
        self.log_output.ensureCursorVisible()


class UnrealBuilder:
    def __init__(
        self,
        project_name: str,
        project_path: str,
        target_ue_version: Optional[str] = None,
        ue_base_path: str = "C:/Program Files/Epic Games",
    ):
        self.ue_base_path = ue_base_path
        self.project_name = project_name
        self.project_path = project_path
        self.process = None
        self.build_in_progress = False  # Lock to prevent concurrent builds

        # Move build_dir and archive_dir to __init__
        self.build_dir = "C:/Builds"  # TODO: Move to config
        self.archive_dir = os.path.join(self.build_dir, project_name)

        # Determine engine version
        self.target_ue_version = (
            target_ue_version or self.get_engine_version_from_uproj()
        )

    def get_engine_version_from_uproj(self) -> Optional[str]:
        """
        Reads the .uproject file to determine the required Unreal Engine version.

        Returns:
            The Unreal Engine version (e.g., "5.3"), or None if detection fails.

        Raises:
            ProjectFileNotFoundError: If the project file does not exist.
            EngineVersionError: If the engine version cannot be read or is missing.
        """
        if not os.path.exists(self.project_path):
            raise ProjectFileNotFoundError(
                f"Project file not found: {self.project_path}"
            )

        try:
            with open(self.project_path, "r") as f:
                uproject_data = json.load(f)
                engine_version = uproject_data.get("EngineAssociation")
                if not engine_version:
                    raise EngineVersionError(
                        "Engine version not specified in .uproject file."
                    )
                return engine_version
        except Exception as e:
            raise EngineVersionError(f"Failed to read .uproject file: {str(e)}")

    def check_unreal_engine_installed(self) -> bool:
        """
        Checks if the specified Unreal Engine version is installed on the system.

        Returns:
            True if the version is installed, False otherwise.

        Raises:
            UnrealEngineNotInstalledError: If the engine is not installed (optional handling).
        """
        ue_version_path = os.path.join(
            self.ue_base_path, f"UE_{self.target_ue_version}"
        )
        if os.path.exists(ue_version_path):
            return True
        else:
            raise UnrealEngineNotInstalledError(
                f"Unreal Engine {self.target_ue_version} is not installed at {ue_version_path}."
            )

    def _cleanup_build_artifacts(self):
        """
        Cleans up temporary build artifacts in the archive directory after cancellation.

        Raises:
            CleanupError: If cleanup fails.
        """
        if os.path.exists(self.archive_dir):
            try:
                for root, dirs, files in os.walk(self.archive_dir, topdown=False):
                    for name in files:
                        os.remove(os.path.join(root, name))
                    for name in dirs:
                        os.rmdir(os.path.join(root, name))
                os.rmdir(self.archive_dir)
            except Exception as e:
                raise CleanupError(
                    f"Failed to clean up build artifacts: {str(e)}. "
                    f"You may need to manually delete {self.archive_dir}."
                )

    def run_unreal_build(self, branch: str) -> bool:
        """
        Runs the Unreal build using UAT for the specified branch and project.

        Args:
            branch: The branch being built (e.g., "//MyGame/release_0.2.2").

        Returns:
            True if the build succeeds, False otherwise.

        Raises:
            BuildError: If a build is already in progress.
        """

        self.build_in_progress = True
        ue_version_path = os.path.join(
            self.ue_base_path, f"UE_{self.target_ue_version}"
        )
        uat_script = os.path.join(
            ue_version_path,
            (
                "Engine/Build/BatchFiles/RunUAT.bat"
                if sys.platform == "win32"
                else "Engine/Build/BatchFiles/RunUAT.sh"
            ),
        )

        if not os.path.exists(uat_script):
            self.build_in_progress = False
            raise UATScriptNotFoundError(
                f"UAT script not found at {uat_script}. "
                f"Ensure Unreal Engine {self.target_ue_version} is installed correctly."
            )

        uat_args = [
            uat_script,
            "BuildCookRun",
            f"-project={self.project_path}",
            "-noP4",
            "-platform=Win64",
            "-clientconfig=Development",
            "-build",
            "-cook",
            "-stage",
            "-pak",
            "-archive",
            f"-archivedirectory={self.archive_dir}",
        ]

        dialog = BuildProgressDialog()  # Mock dialog for logging
        self.process = QProcess()
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)

        self.process.readyReadStandardOutput.connect(
            lambda: self.process
            and dialog.append_log(
                self.process.readAllStandardOutput().data().decode("utf-8")
            )
        )
        self.process.finished.connect(
            lambda: None
        )  # Placeholder; UI layer can handle this

        dialog.append_log(f"Starting build for {branch}...\n")
        dialog.append_log(f"UAT Command: {' '.join(uat_args)}\n\n")
        self.process.start(uat_args[0], uat_args[1:])

        # Simulate dialog.exec() behavior (this would be handled by UI)
        # For now, we'll assume the process runs to completion or is canceled externally
        self.process.waitForFinished(-1)  # Blocking wait; UI layer would handle async

        if self.process.state() == QProcess.ProcessState.Running:
            dialog.append_log("\nAttempting to gracefully stop the build...")
            self.end_build_process(canceled=True)
            return False

        exit_code = self.process.exitCode()
        if exit_code == 0:
            dialog.append_log("\nBuild completed successfully!")
            self.end_build_process()
            return True
        else:
            dialog.append_log(f"\nBuild failed with exit code {exit_code}.")
            self.end_build_process()
            return False

    def end_build_process(self, canceled=False):
        """Terminates the build process and manages cleanup if it was canceled."""
        if self.process:
            self.process.readyReadStandardOutput.disconnect()
            self.process.finished.disconnect()
            if canceled:
                self.process.terminate()
                if not self.process.waitForFinished(2000):  # Wait up to 2 seconds
                    self.process.kill()
                self._cleanup_build_artifacts()
            self.process = None
        self.build_in_progress = False
