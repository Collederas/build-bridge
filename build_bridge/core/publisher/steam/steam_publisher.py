from pathlib import Path

from build_bridge.models import SteamPublishProfile
from build_bridge.exceptions import InvalidConfigurationError
from build_bridge.core.publisher.base_publisher import BasePublisher
from build_bridge.core.publisher.steam.steam_pipe_configurator import (
    SteamPipeConfigurator,
)
from build_bridge.core.publisher.upload_spec import UploadSpec


def check_steam_success(exit_code: int, log_content: str) -> bool:
    log_lower = log_content.lower()
    login_ok = "to steam public...ok" in log_lower
    build_success = (
        "app build successful" in log_lower
        or "successfully finished" in log_lower
    )
    no_errors = not (
        "error" in log_lower.replace("stderr", "")
        or "failed" in log_lower
    )
    return exit_code == 0 and login_ok and build_success and no_errors


class SteamPublisher(BasePublisher):
    def __init__(self, publish_profile: SteamPublishProfile):
        self.publish_profile = publish_profile

    def validate_publish_profile(self):
        if not self.publish_profile:
            raise InvalidConfigurationError("Steam publishing is not configured.")

        steam_config = self.publish_profile.steam_config
        if not steam_config:
            raise InvalidConfigurationError(
                "Steam configuration is missing. Create one in Settings."
            )

        if not steam_config.steamcmd_path:
            raise InvalidConfigurationError("SteamCMD not set in Steam Settings.")

    def prepare(self, content_dir: str, version: str = "") -> UploadSpec:
        self.validate_publish_profile()

        steam_config = self.publish_profile.steam_config
        executable = steam_config.steamcmd_path
        steamcmd_dir = Path(executable).parent
        builder_log_dir = Path(self.publish_profile.builder_path) / "BuildLogs"

        configurator = SteamPipeConfigurator(publish_profile=self.publish_profile)
        # VDF path is deterministic from the configurator; precompute so the
        # arguments list is concrete before pre_run actually writes the file.
        vdf_path = configurator.get_vdf_path()

        arguments = [
            "+login",
            steam_config.username,
            steam_config.password or "",
            "+run_app_build",
            vdf_path,
            "+quit",
        ]

        project_name = (
            self.publish_profile.project.name if self.publish_profile.project else ""
        )
        display_info = {
            "Build ID": version,
            "App ID": str(self.publish_profile.app_id),
            "Target": f"Steam ({steam_config.username})",
        }
        title = f"Steam Upload: {project_name} - {version}"
        store_page_url = (
            f"https://store.steampowered.com/app/{self.publish_profile.app_id}/"
            if self.publish_profile.app_id
            else None
        )

        def pre_run():
            configurator.create_or_update_vdf_file(content_root=content_dir)

        from build_bridge.models import StoreEnum

        return UploadSpec(
            store=StoreEnum.steam,
            executable=executable,
            arguments=arguments,
            success_checker=check_steam_success,
            title=title,
            display_info=display_info,
            working_directory=str(steamcmd_dir),
            log_files=[
                str(steamcmd_dir / "logs" / "content_log.txt"),
                str(steamcmd_dir / "logs" / "stderr.txt"),
            ],
            log_directories=[str(builder_log_dir)],
            build_folder=content_dir,
            store_page_url=store_page_url,
            pre_run=pre_run,
        )
