import enum
import os

from anyio import Path
from sqlalchemy import JSON, Boolean, Column, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship, validates
import keyring

from database import Base


class VCSTypeEnum(str, enum.Enum):
    perforce = "perforce"
    git = "git"


class BuildTypeEnum(str, enum.Enum):
    dev = "Development"
    prod = "Shipping"


class BuildTargetPlatformEnum(str, enum.Enum):
    win_64 = "Win64"
    win_32 = "Win32"
    mac_os = "MacOS"


class StoreEnum(str, enum.Enum):
    itch = "Itch.io"
    steam = "Steam"


class Project(Base):
    __tablename__ = "project"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, default="My Project")

    source_dir = Column(String, nullable=False, default="")
    archive_directory = Column(String, nullable=False, default="")

    build_targets = relationship(
        "BuildTarget", back_populates="project", cascade="all, delete-orphan"
    )
    publish_profiles = relationship(
        "PublishProfile", back_populates="project", cascade="all, delete-orphan"
    )

    @property
    def builds_path(self):
        return Path(self.archive_directory) / self.name


class BuildTarget(Base):
    __tablename__ = "build_targets"

    id = Column(Integer, primary_key=True, autoincrement=True)

    project_id = Column(Integer, ForeignKey("project.id"), nullable=False)
    project = relationship("Project", back_populates="build_targets")

    vcs_config = relationship("VCSConfig", uselist=False, back_populates="build_target")
    target_branch = Column(String, nullable=False, default="")

    build_type = Column(Enum(BuildTypeEnum), nullable=False, default=BuildTypeEnum.prod)
    target_platform = Column(
        Enum(BuildTargetPlatformEnum),
        nullable=False,
        default=BuildTargetPlatformEnum.win_64,
    )
    optimize_for_steam = Column(Boolean, nullable=False, default=True)

    auto_sync_branch = Column(Boolean, nullable=False, default=False)

    def __repr__(self):
        return f"{self.project.name} - {self.target_platform.value}"


class PublishProfile(Base):
    __tablename__ = "publish_profile"

    id = Column(Integer, primary_key=True, autoincrement=True)
    store_type = Column(Enum(StoreEnum), nullable=False)

    project_id = Column(Integer, ForeignKey("project.id"), nullable=False)
    project = relationship("Project", back_populates="publish_profiles")

    build_id = Column(String, nullable=False)
    description = Column(String, nullable=True)

    __mapper_args__ = {"polymorphic_on": store_type, "polymorphic_identity": None}


class SteamPublishProfile(PublishProfile):
    __tablename__ = "steam_publish_profile"

    id = Column(Integer, ForeignKey("publish_profile.id"), primary_key=True)
    app_id = Column(Integer, nullable=False, default=480)

    depots = Column(JSON, nullable=False, default=dict)

    steam_config_id = Column(Integer, ForeignKey("steam_config.id"), nullable=False)
    steam_config = relationship("SteamConfig", back_populates="publish_profiles")

    __mapper_args__ = {"polymorphic_identity": StoreEnum.steam}

    @validates("depots")
    def validate_depots(self, key, depots):
        """
        Validate depot mappings to ensure all paths exist.

        Raises:
            ValueError: If any depot path does not exist.
        """
        for depot_id, depot_path in depots.items():
            if not os.path.exists(depot_path):
                raise ValueError(
                    f"Depot path {depot_path} for depot {depot_id} does not exist."
                )

        return depots

    @property
    def builder_path(self):
        """This is built dynamically based on project"""
        if self.project:
            return str(Path(self.project.builds_path) / "Steam")


class SteamConfig(Base):
    __tablename__ = "steam_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, nullable=False, default="itch-username")
    _password = None  # Internal cache for password

    steamcmd_path = Column(String, nullable=True)

    publish_profiles = relationship(
        "SteamPublishProfile", back_populates="steam_config"
    )

    @property
    def _keyring_service_id(self):
        return f"BuildBridgeSteamAuth:{self.id}:{self.username}"

    @property
    def password(self):
        if self._password is None:
            self._password = keyring.get_password(
                self._keyring_service_id, self.username
            )
        return self._password

    @password.setter
    def password(self, value):
        try:
            keyring.set_password(self._keyring_service_id, self.username, value)
            self._password = value
        except keyring.errors.KeyringError as e:
            raise RuntimeError(f"Failed to store Steam password: {e}") from e

    @validates("builder_path")
    def validate_builder_path(self, key, builder_path):
        if not os.path.exists(builder_path):
            raise ValueError("Builder path is not valid or does not exist.")
        return builder_path

    @validates("steamcmd_path")
    def validate_steamcmd_path(self, key, steamcmd_path):
        if not os.path.exists(steamcmd_path):
            raise ValueError("SteamCMD path is not valid or does not exist.")
        return steamcmd_path


class ItchPublishProfile(PublishProfile):
    __tablename__ = "itch_publish_profile"

    id = Column(Integer, ForeignKey("publish_profile.id"), primary_key=True)

    itch_user_game_id = Column(
        String, nullable=False
    )  # e.g., "myusername/my-cool-game"
    itch_channel_name = Column(
        String, nullable=False, default="default-channel"
    )  # e.g., "windows-beta"

    itch_config_id = Column(Integer, ForeignKey("itch_config.id"), nullable=False)
    itch_config = relationship("ItchConfig", back_populates="publish_profiles")

    __mapper_args__ = {"polymorphic_identity": StoreEnum.itch}

    @validates("itch_user_game_id")
    def validate_user_game_id(self, key, value):
        if value and "/" not in value:
            raise ValueError(
                "Itch.io User/Game ID must be in the format 'username/game-name'."
            )
        return value


class ItchConfig(Base):
    __tablename__ = "itch_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, nullable=False, unique=True)  # Itch.io username
    butler_path = Column(String, nullable=True)
    _api_key = None  # Internal cache

    publish_profiles = relationship("ItchPublishProfile", back_populates="itch_config")

    @property
    def _keyring_service_id(self):
        """Generates the keyring service ID using the Itch.io username."""
        if not self.username:
            return None
        return f"BuildBridgeItchAuth:{self.username}"  # Service tied to the username

    @property
    def api_key(self):
        """Retrieves the Itch.io API key from keyring for this config's username."""
        if self._api_key is None:
            service_id = self._keyring_service_id
            key_name = self.username

            if not service_id:
                print("Cannot retrieve API key: ItchConfig username not set.")
                return None

            try:
                self._api_key = keyring.get_password(service_id, key_name)
            except keyring.errors.PasswordNotFoundError:
                print(f"No Itch API key found in keyring for {service_id}/{key_name}.")
                self._api_key = None
            except keyring.errors.KeyringError as e:
                print(
                    f"Keyring error retrieving Itch API key for {service_id}/{key_name}: {e}"
                )
                self._api_key = None
            except Exception as e:
                print(
                    f"Unexpected error retrieving Itch API key for {service_id}/{key_name}: {e}"
                )
                self._api_key = None
        return self._api_key

    @api_key.setter
    def api_key(self, value):
        """Stores the Itch.io API key in keyring for this config's username."""
        service_id = self._keyring_service_id
        key_name = self.username

        if not service_id:
            raise ValueError("Cannot store API key: ItchConfig username is not set.")

        if not value:
            try:
                keyring.delete_password(service_id, key_name)
                self._api_key = None
                print(f"Itch API key cleared from keyring for {service_id}/{key_name}.")
            except keyring.errors.PasswordDeleteError:
                print(
                    f"Itch API key not found in keyring to delete for {service_id}/{key_name}."
                )
            except Exception as e:
                print(
                    f"Failed to delete Itch API key from keyring for {service_id}/{key_name}: {e}"
                )
        else:
            try:
                keyring.set_password(service_id, key_name, value)
                self._api_key = value
                print(
                    f"Itch API key stored securely in keyring for {service_id}/{key_name}."
                )
            except keyring.errors.KeyringError as e:
                print(
                    f"Keyring error storing Itch API key for {service_id}/{key_name}: {e}"
                )
                raise RuntimeError(f"Failed to store Itch API key: {e}") from e
            except Exception as e:
                print(
                    f"Unexpected error storing Itch API key for {service_id}/{key_name}: {e}"
                )
                raise RuntimeError(
                    f"An unexpected error occurred storing Itch API key: {e}"
                ) from e

    @validates("butler_path")
    def validate_butler_path(self, key, path):
        if path and not os.path.exists(path):
            raise ValueError(f"Butler path '{path}' is not valid or does not exist.")
        return path


class VCSConfig(Base):
    """Each build target can have its own vcs."""

    __tablename__ = "vcs_configs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    vcs_type = Column(Enum(VCSTypeEnum), nullable=False)
    build_target_id = Column(Integer, ForeignKey("build_targets.id"))
    build_target = relationship("BuildTarget", back_populates="vcs_config")

    __mapper_args__ = {"polymorphic_on": vcs_type, "polymorphic_identity": None}


class PerforceConfig(VCSConfig):
    __tablename__ = "p4config"
    id = Column(Integer, ForeignKey("vcs_configs.id"), primary_key=True)
    user = Column(String, nullable=False, default="")
    server_address = Column(String, nullable=False, default="")
    client = Column(String, nullable=False, default="")
    _p4password = None  # Internal cache for password

    @property
    def _keyring_service_id(self):
        return f"BuildBridgeP4:{self.server_address}:{self.client}"

    @property
    def p4password(self):
        if self._p4password is None:
            self._p4password = keyring.get_password(self._keyring_service_id, self.user)
        return self._p4password

    @p4password.setter
    def p4password(self, value):
        try:
            keyring.set_password(self._keyring_service_id, self.user, value)
            self._p4password = value
        except keyring.errors.KeyringError as e:
            raise RuntimeError(f"Failed to store Perforce password: {e}") from e

    __mapper_args__ = {"polymorphic_identity": VCSTypeEnum.perforce}


class GitConfig(VCSConfig):
    __tablename__ = "gitconfig"
    id = Column(Integer, ForeignKey("vcs_configs.id"), primary_key=True)
    remote_url = Column(String, nullable=False)
    ssh_key_path = Column(String, nullable=False)

    __mapper_args__ = {"polymorphic_identity": VCSTypeEnum.git}
