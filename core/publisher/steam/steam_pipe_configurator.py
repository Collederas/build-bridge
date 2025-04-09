import os
from jinja2 import Template

from models import SteamPublishProfile


class SteamPipeConfigurator:
    TEMPLATE_FILE = os.path.join(os.path.dirname(__file__), "app_build_template.vdf")

    def __init__(self, publish_profile: SteamPublishProfile):
        self.publish_profile = publish_profile

    def create_or_update_vdf_file(self, content_root: str):
        """
        Generate an app_build.vdf file based on the template and configuration.
        It will create or override the same app_build.vdf file inside the "builder path"
        configured in Settings.

        Args:
            content_root (str): The content root directory of the build to publish.
        """
        if not os.path.exists(self.TEMPLATE_FILE):
            raise FileNotFoundError(f"Template file not found: {self.TEMPLATE_FILE}")
        
        print(self.publish_profile)

        builder_path = self.publish_profile.builder_path

        app_id = self.publish_profile.app_id
        description = self.publish_profile.description
        depot_mappings = self.publish_profile.depots

        # Create necessary directories and files if don't exist
        # <UserDefinedPath>
        #   \_ Steam
        #       \_ BuildLogs
        #       \_ app_build.vdf
        #       \_ ...
         
        os.makedirs(builder_path, exist_ok=True)
        log_dir = os.path.join(builder_path, "BuildLogs")
        os.makedirs(log_dir, exist_ok=True)

        # Ensure folders are relative to builder_path
        content_root_rel = os.path.relpath(content_root, builder_path)
        log_dir_rel = os.path.relpath(log_dir, builder_path)

        # Read and render the template using Jinja2
        with open(self.TEMPLATE_FILE, "r", encoding="utf-8") as template_file:
            template_content = template_file.read()
            template = Template(template_content)
            vdf_content = template.render(
                app_id=app_id,
                description=description,
                content_root=content_root_rel,
                build_output=log_dir_rel,
                depot_mappings=depot_mappings,
            )

        # Write the rendered VDF content to the builder directory
        app_build_vdf_path = os.path.join(builder_path, "app_build.vdf")

        with open(app_build_vdf_path, "w", encoding="utf-8") as vdf_file:
            vdf_file.write(vdf_content)

        print(f"VDF file generated at: {app_build_vdf_path}")