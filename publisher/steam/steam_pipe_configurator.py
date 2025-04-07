import os
from jinja2 import Template
from conf.config_manager import ConfigManager


class SteamPipeConfigurator:
    TEMPLATE_FILE = os.path.join(os.path.dirname(__file__), "app_build_template.vdf")

    def __init__(self):
        self.config_manager = ConfigManager("stores")

    def validate_configuration(self):
        """
        Validate the configuration to ensure all required settings and paths are valid.

        Raises:
            ValueError: If any configuration or path is invalid.
        """
        builder_path = self.config_manager.get("steam.builder_path", "")
        if not builder_path:
            raise ValueError("Builder path is not configured in settings.")

        if not os.path.exists(self.TEMPLATE_FILE):
            raise FileNotFoundError(f"Template file not found: {self.TEMPLATE_FILE}")

        self.validate_depot_mappings()
    
    def validate_depot_mappings(self):
        """
        Validate depot mappings to ensure all paths exist.

        Raises:
            ValueError: If any depot path does not exist.
        """
        depot_mappings = self.config_manager.get("steam.depot_mappings", {})
        for depot_id, depot_path in depot_mappings.items():
            if not os.path.exists(depot_path):
                raise ValueError(f"Depot path {depot_path} for depot {depot_id} does not exist.")

    def create_or_update_vdf_file(self, content_root: str):
        """
        Generate an app_build.vdf file based on the template and configuration.
        It will create or override the same app_build.vdf file inside the "builder path"
        configured in Settings.

        Args:
            content_root (str): The content root directory of the build to publish.
        """
        # Perform validation as a guard step
        self.validate_configuration()

        # Get conf
        builder_path = self.config_manager.get("steam.builder_path", "")

        # Append store name to the user provided path (..meh)
        steam_builder_path = os.path.join(builder_path, "Steam")
        app_id = self.config_manager.get("steam.app_id", "1000")
        description = self.config_manager.get("steam.description", "")
        depot_mappings = self.config_manager.get("steam.depot_mappings", {})

        # Create necessary directories and files if don't exist
        # <UserDefinedPath>
        #   \_ Steam
        #       \_ BuildLogs
        #       \_ app_build.vdf
        #       \_ ...
         
        os.makedirs(steam_builder_path, exist_ok=True)
        log_dir = os.path.join(steam_builder_path, "BuildLogs")
        os.makedirs(log_dir, exist_ok=True)

        # Ensure folders are relative to builder_path
        content_root_rel = os.path.relpath(content_root, steam_builder_path)
        log_dir_rel = os.path.relpath(log_dir, steam_builder_path)

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
        app_build_vdf_path = os.path.join(steam_builder_path, "app_build.vdf")

        with open(app_build_vdf_path, "w", encoding="utf-8") as vdf_file:
            vdf_file.write(vdf_content)

        print(f"VDF file generated at: {app_build_vdf_path}")