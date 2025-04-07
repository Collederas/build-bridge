from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from database import Base

class Project(Base):
    __tablename__ = "project"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, default="My Project")
    source_dir = Column(String, nullable=False, default="")
    dest_dir = Column(String, nullable=False, default="")

    build_targets = relationship("BuildTarget", back_populates="project", cascade="all, delete-orphan")