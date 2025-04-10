import json
import os
import sys
from typing import Optional

from build_bridge.models import BuildTargetPlatformEnum, BuildTypeEnum



class BuildAlreadyExistsError(Exception):
    """Raised when a build with the same name/version exists."""

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


class UnrealBuilder:
    def __init__(
        self,
        source_dir: str,
        engine_path: str,
        target_platform: BuildTargetPlatformEnum,
        target_config: BuildTypeEnum,
        output_dir: str,
        clean: bool = False,
        valve_package_pad: bool = False
    ):

        self.source_dir = source_dir
        self.engine_path = engine_path
        self.target_platform = target_platform
        self.target_config = target_config
        self.clean = clean
        self.valve_package_pad = valve_package_pad

        # Check if a build already exist for this release id
        if os.path.exists(output_dir):
            raise BuildAlreadyExistsError(f"{output_dir} already exists")
        
        self.output_dir = output_dir
        
        # Project path validation
        self.uproj_path = self.get_uproject_path()
        

        # Determine engine version and validate
        self.target_ue_version = self.get_engine_version_from_uproj()
        self.check_unreal_engine_installed()

    def get_uproject_path(self, recurse_level: int = 1) -> str:
        """
        Finds the .uproject file in the source directory or its subdirectories.

        Args:
            recurse_level (int): The depth of subdirectories to search. Default is 1.

        Returns:
            str: The path to the .uproject file.

        Raises:
            ProjectFileNotFoundError: If no .uproject file is found.
        """
        if not os.path.isdir(self.source_dir):
            # Assume self.source_dir is already the path to the .uproject file
            return self.source_dir

        uproject_files = []
        for root, _, files in os.walk(self.source_dir):
            if os.path.relpath(root, self.source_dir).count(os.sep) >= recurse_level:
                continue
            uproject_files.extend(
                os.path.join(root, f) for f in files if f.endswith(".uproject")
            )

        if not uproject_files:
            raise ProjectFileNotFoundError(
                f"No .uproject file found in: {self.source_dir} (recurse_level={recurse_level})"
            )

        # Use the first .uproject file found
        return uproject_files[0]

    def get_engine_version_from_uproj(self) -> Optional[str]:
        """
        Reads the .uproject file to determine the required Unreal Engine version.

        Returns:
            The Unreal Engine version (e.g., "5.5"), or None if detection fails.

        Raises:
            ProjectFileNotFoundError: If the project file does not exist.
            EngineVersionError: If the engine version cannot be read or is missing.
        """
        if not os.path.exists(self.uproj_path):
            raise ProjectFileNotFoundError(
                f"Project file not found: {self.uproj_path}"
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
            self.engine_path, f"UE_{self.target_ue_version}"
        )
        if os.path.exists(ue_version_path):
            return True
        else:
            raise UnrealEngineNotInstalledError(
                f"Unreal Engine {self.target_ue_version} is not installed at {ue_version_path}."
            )

    def get_build_command(self):
        """Returns the UAT command as a list for QProcess using config settings."""
        ue_version_path = os.path.join(self.engine_path, f"UE_{self.target_ue_version}")
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
        command.append(f"-platform={self.target_platform}")

        # Add configuration from config
        command.append(f"-clientconfig={self.target_config}")

        # Add standard build options
        command.extend(["-build", "-cook", "-stage", "-pak", "-prereqs"])

        # Add clean build if specified
        if self.clean:
            command.append("-clean")

        # Add archive settings
        command.extend([
            "-archive",
            f'-archivedirectory="{self.output_dir}"'
        ])

        if self.valve_package_pad:
            command.extend(["-patchpaddingalign=1048576", "-blocksize=1048576"])

        return command