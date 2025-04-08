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

    build_targets = relationship("BuildTarget", back_populates="project", cascade="all, delete-orphan")

# BuildTarget model
class BuildTarget(Base):
    __tablename__ = "build_targets"
    
    id = Column(Integer, primary_key=True, autoincrement=True)

    project_id = Column(Integer, ForeignKey("project.id"), nullable=False)
    project = relationship("Project", back_populates="build_targets")

    vcs_config = relationship("VCSConfig", uselist=False, back_populates="build_target")
    target_branch = Column(String, nullable=False, default="")
    
    build_type = Column(Enum(BuildTypeEnum), nullable=False, default=BuildTypeEnum.prod)
    target_platform = Column(Enum(BuildTargetPlatformEnum), nullable=False, default=BuildTargetPlatformEnum.win_64)
    optimize_for_steam = Column(Boolean, nullable=False, default=True)

    auto_sync_branch = Column(Boolean, nullable=False, default=False)
    archive_directory = Column(String, nullable=False, default="")

    def __repr__(self):
        return f"{self.project.name} - {self.target_platform.value}"
    
    def get_builds_path(self):
        return Path(self.archive_directory) / self.project.name
    

class VCSConfig(Base):
    """Each build target can have its own vcs."""
    __tablename__ = "vcs_configs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    vcs_type = Column(Enum(VCSTypeEnum), nullable=False)
    build_target_id = Column(Integer, ForeignKey("build_targets.id"))
    build_target = relationship("BuildTarget", back_populates="vcs_config")
        
    __mapper_args__ = {
        'polymorphic_on': vcs_type,
        'polymorphic_identity': None
    }

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

    __mapper_args__ = {
        'polymorphic_identity': VCSTypeEnum.perforce
    }

class GitConfig(VCSConfig):
    __tablename__ = "gitconfig"
    id = Column(Integer, ForeignKey("vcs_configs.id"), primary_key=True)
    remote_url = Column(String, nullable=False)
    ssh_key_path = Column(String, nullable=False)
    
    __mapper_args__ = {
        'polymorphic_identity': VCSTypeEnum.git
    }

class SteamBuildPublishProfile(Base):
    __tablename__ = "steam_publish_profile"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    build_id = Column(String, unique=True, nullable=False)  # Normally, the version
    app_id = Column(Integer, nullable=False, default=480)
    depots = Column(JSON, nullable=False, default=dict)
    builder_path = Column(String, nullable=False)

    steam_auth_profile_id = Column(Integer, ForeignKey('steam_auth_profile.id'))
    steam_auth_profile = relationship("SteamAuthProfile", backref="publish_profiles")
    
    @validates('depots')
    def validate_depots(self, key, depot_mappings):
        """
        Validate depot mappings to ensure all paths exist.

        Raises:
            ValueError: If any depot path does not exist.
        """
        for depot_id, depot_path in depot_mappings.items():
            if not os.path.exists(depot_path):
                raise ValueError(f"Depot path {depot_path} for depot {depot_id} does not exist.")
        
        return depot_mappings
    
    @validates("builder_path")
    def validate_builder_path(self, key, builder_path):
        if not os.path.isdir(builder_path):
            raise ValueError("Builder path is not a valid directory.")
        

class SteamAuthProfile(Base):
    __tablename__ = "steam_auth_profile"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, nullable=False)
    _password = None  # Internal cache for password

    publish_profiles = relationship("SteamBuildPublishProfile", backref="steam_auth_profile")

    
    @property
    def _keyring_service_id(self):
        return f"BuildBridgeSteamAuth:{self.id}:{self.username}"

    @property
    def password(self):
        if self._p4password is None:
            self._p4password = keyring.get_password(self._keyring_service_id, self.user)
        return self._p4password

    @password.setter
    def password(self, value):
        try:
            keyring.set_password(self._keyring_service_id, self.user, value)
            self._p4password = value
        except keyring.errors.KeyringError as e:
            raise RuntimeError(f"Failed to store Steam password: {e}") from e
