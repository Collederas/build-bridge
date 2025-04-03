import json
import os
import sys
import logging
from typing import Callable, Optional

from app_config import ConfigManager

logger = logging.getLogger(__name__)


class MultipleUprojectFoundError(Exception):
    """Custom exception raised when multiple .uproject files are found."""

    pass


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


class UnrealBuilder:
    def __init__(
        self,
        root_directory: str, # project dir, actually
        config_name: str = "build"
    ):
        self.config_manager = ConfigManager(config_name)
        
        self.build_config = self.config_manager.get("unreal", {})
        
        # Project path validation
        self.project_path = self.find_unreal_project_root(root_directory)
        self.uproj_path = self.get_uproject_path()

        self.ue_base_path = self.build_config.get(
            "engine_path", 
        )

        # Determine engine version and validate
        self.target_ue_version = self.get_engine_version_from_uproj()
        self.check_unreal_engine_installed()

        self.build_dir = self.build_config.get("archive_directory", "C:/Builds")

    @staticmethod
    def find_unreal_project_root(workspace_root):
        """
        Finds the Unreal Engine project root (containing the .uproject file)
        within a given workspace root.

        Args:
            workspace_root (str): The path to the Perforce workspace root.

        Returns:
            str: The normalized path to the Unreal Engine project root
                if exactly one .uproject file is found.

        Raises:
            NoUprojectFoundError: If no .uproject file is found.
            MultipleUprojectFoundError: If more than one .uproject file is found.
        """
        project_file_paths = []
        for root, _, files in os.walk(workspace_root):
            for file in files:
                if file.endswith(".uproject"):
                    project_file_paths.append(root)

        if len(project_file_paths) == 1:
            return os.path.normpath(project_file_paths[0])
        elif len(project_file_paths) > 1:
            raise MultipleUprojectFoundError(
                f"Found multiple .uproject files in '{workspace_root}': {project_file_paths}. Please specify which project to use."
            )
        else:
            raise ProjectFileNotFoundError(
                f"No .uproject file found in '{workspace_root}'."
            )

    def get_uproject_path(self) -> str:
        # If self.project_path is a directory, look for a .uproject file
        if os.path.isdir(self.project_path):
            # Find all .uproject files in the directory
            uproject_files = [
                f for f in os.listdir(self.project_path) if f.endswith(".uproject")
            ]

            if not uproject_files:
                raise ProjectFileNotFoundError(
                    f"No .uproject file found in: {self.project_path}"
                )

            # Use the first .uproject file found
            uproj_path = os.path.join(self.project_path, uproject_files[0])
        else:
            # Assume self.project_path is already the path to the .uproject file
            uproj_path = self.project_path

        return uproj_path

    def get_engine_version_from_uproj(self) -> Optional[str]:
        """
        Reads the .uproject file to determine the required Unreal Engine version.

        Returns:
            The Unreal Engine version (e.g., "5.5"), or None if detection fails.

        Raises:
            ProjectFileNotFoundError: If the project file does not exist.
            EngineVersionError: If the engine version cannot be read or is missing.
        """
        if not os.path.exists(self.project_path):
            raise ProjectFileNotFoundError(
                f"Project file not found: {self.project_path}"
            )
        try:
            with open(self.uproj_path, "r") as f:
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

    def get_build_command(self):
        """Returns the UAT command as a list for QProcess using config settings."""
        ue_version_path = os.path.join(self.ue_base_path, f"UE_{self.target_ue_version}")
        uat_script = os.path.join(
            ue_version_path,
            "Engine/Build/BatchFiles/RunUAT.bat" if sys.platform == "win32" else "Engine/Build/BatchFiles/RunUAT.sh"
        )

        if not os.path.exists(uat_script):
            raise UATScriptNotFoundError(f"UAT script not found at {uat_script}")

        # Base command
        command = [
            f'"{uat_script}"',
            "BuildCookRun",
            f'-project="{self.uproj_path}"',
            "-noP4",
        ]

        # Add platform from config
        target_platforms = self.build_config.get("target_platforms", ["Win64"])
        command.append(f"-platform={target_platforms[0]}")

        # Add configuration from config
        target_config = self.build_config.get("target_config", "Development")
        command.append(f"-clientconfig={target_config}")

        # Add standard build options
        command.extend(["-build", "-cook", "-stage", "-pak"])

        # Add clean build if specified
        if self.build_config.get("clean_build", False):
            command.append("-clean")

        # Add archive settings
        command.extend([
            "-archive",
            f'-archivedirectory="{self.build_dir}"'
        ])

        return command

    def cleanup_build_artifacts(self):
        """Cleans up build artifacts."""
        if os.path.exists(self.build_dir):
            try:
                for root, dirs, files in os.walk(self.build_dir, topdown=False):
                    for name in files:
                        os.remove(os.path.join(root, name))
                    for name in dirs:
                        os.rmdir(os.path.join(root, name))
                os.rmdir(self.build_dir)
                logger.info(f"Cleaned up artifacts at {self.build_dir}")
            except Exception as e:
                logger.error(f"Cleanup failed: {str(e)}", exc_info=True)
                raise CleanupError(f"Failed to clean up build artifacts: {str(e)}")
