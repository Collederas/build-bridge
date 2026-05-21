from __future__ import annotations

import logging
import re
from pathlib import Path

from build_bridge.core.publisher.base_publisher import BasePublisher
from build_bridge.core.publisher.upload_spec import UploadSpec
from build_bridge.exceptions import InvalidConfigurationError
from build_bridge.models import PublishProfile, StoreEnum

ITCH_TARGET_PATTERN = re.compile(r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$")
ITCH_CHANNEL_PATTERN = re.compile(r"^[a-zA-Z0-9_.-]+$")


def check_itch_success(exit_code: int, log_content: str) -> bool:
    log_lower = log_content.lower()
    success_indicators = ["build is processed", "patch applied", "tasks ended."]
    error_indicators = ["error:", "failed", "panic:", "invalid api key", "denied"]
    return (
        exit_code == 0
        and any(ind in log_lower for ind in success_indicators)
        and not any(err in log_lower for err in error_indicators)
    )


def validate_itch_target(target: str, expected_username: str | None = None):
    target = (target or "").strip()
    if not target:
        raise InvalidConfigurationError("Itch.io User/Game ID is not configured.")

    if not ITCH_TARGET_PATTERN.match(target):
        raise InvalidConfigurationError(
            "Itch.io User/Game ID must use the format 'username/game-slug' and only "
            "letters, numbers, dots, dashes, or underscores."
        )

    target_username = target.split("/", 1)[0]
    if expected_username and target_username.lower() != expected_username.lower():
        raise InvalidConfigurationError(
            "Itch.io User/Game ID username must match the selected Itch.io auth "
            f"profile. Expected '{expected_username}/...', got '{target}'."
        )


def validate_itch_channel(channel: str):
    channel = (channel or "").strip()
    if not channel:
        raise InvalidConfigurationError("Itch.io channel name is not configured.")

    if not ITCH_CHANNEL_PATTERN.match(channel):
        raise InvalidConfigurationError(
            "Itch.io channel name can only contain letters, numbers, dots, dashes, "
            "or underscores."
        )


class ItchPublisher(BasePublisher):
    def __init__(self, publish_profile: PublishProfile):
        self.publish_profile = publish_profile

    def validate_publish_profile(self):
        if not self.publish_profile:
            raise InvalidConfigurationError("Itch.io publishing is not configured.")

        if not self.publish_profile.itch_config:
            raise InvalidConfigurationError(
                "Itch.io auth profile is not configured."
            )

        validate_itch_target(
            self.publish_profile.itch_user_game_id,
            self.publish_profile.itch_config.username,
        )
        validate_itch_channel(self.publish_profile.itch_channel_name)

        if not self.publish_profile.itch_config.api_key:
            raise InvalidConfigurationError(
                "Itch.io API Key not found or configured. Please set it in Settings."
            )

        if not self.publish_profile.itch_config.butler_path:
            raise InvalidConfigurationError(
                "Butler not found. Please set it in Settings."
            )

    def prepare(self, content_dir: str, version: str = "") -> UploadSpec:
        self.validate_publish_profile()

        itch_target = self.publish_profile.itch_user_game_id
        butler_exe = self.publish_profile.itch_config.butler_path
        channel = self.publish_profile.itch_channel_name

        arguments = [
            "push",
            str(Path(content_dir).resolve()),
            f"{itch_target}:{channel}",
            "--userversion",
            version,
        ]

        logging.info(f"Itch publish prepared: {butler_exe} {' '.join(arguments)}")

        project_name = (
            self.publish_profile.project.name if self.publish_profile.project else ""
        )
        display_info = {
            "Build ID": version,
            "Target": itch_target,
            "Channel": channel,
        }
        title = f"Itch.io Upload: {project_name} - {version}"

        user, game = itch_target.split("/", 1)
        store_page_url = f"https://{user}.itch.io/{game}"

        return UploadSpec(
            store=StoreEnum.itch,
            executable=butler_exe,
            arguments=arguments,
            environment={
                "BUTLER_API_KEY": str(self.publish_profile.itch_config.api_key),
                "BUTLER_NO_TTY": "1",
            },
            success_checker=check_itch_success,
            title=title,
            display_info=display_info,
            build_folder=content_dir,
            store_page_url=store_page_url,
        )
