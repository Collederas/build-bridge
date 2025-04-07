import enum

from sqlalchemy import Boolean, Column, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from database import Base
from models.project import Project


class VCSTypeEnum(str, enum.Enum):
    git = "git"
    perforce = "perforce"

class BuildTypeEnum(str, enum.Enum):
    dev = "Development"
    prod = "Shipping"

class BuildTargetPlatformEnum(str, enum.Enum):
    win_64 = "Win64"
    win_32 = "Win32"
    mac_os = "MacOS"


# BuildTarget model
class BuildTarget(Base):
    __tablename__ = "build_targets"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    build_id = Column(Integer, nullable=False)

    project_id = Column(Integer, ForeignKey("project.id"), nullable=False)
    project = relationship("Project", back_populates="build_targets")

    vcs_type = Column(Enum(VCSTypeEnum), nullable=False, default=VCSTypeEnum.perforce)
    target_branch = Column(String, nullable=False, default="")
    build_type = Column(Enum(BuildTypeEnum), nullable=False, default=BuildTypeEnum.prod)
    target_platform = Column(Enum(BuildTargetPlatformEnum), nullable=False, default=BuildTargetPlatformEnum.win_64)
    optimize_for_steam = Column(Boolean, nullable=False, default=True)

    def __repr__(self):
        return f"<BuildTarget(build_id={self.build_id}, project_name={self.project.name})>"
