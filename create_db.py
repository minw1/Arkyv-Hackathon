from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Boolean, ForeignKey, Text
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()

class Checklist(Base):
    __tablename__ = "checklists"
    id = Column(Integer, primary_key=True)
    user_name = Column(String, nullable=False)
    pdf_name = Column(String, nullable=False)
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat(), nullable=False)
    updated_at = Column(String, default=lambda: datetime.utcnow().isoformat(), nullable=False)

    items = relationship("ChecklistItem", back_populates="checklist", cascade="all, delete-orphan")

class ChecklistItem(Base):
    __tablename__ = "checklist_items"
    id = Column(Integer, primary_key=True)
    checklist_id = Column(Integer, ForeignKey("checklists.id"), nullable=False)
    label = Column(Text, nullable=False)
    category = Column(String, nullable=False)
    is_done = Column(Boolean, default=False, nullable=False)
    bbr_sections = Column(Text)  # store JSON/string (easiest for weekend)
    bbr_texts = Column(Text)

    checklist = relationship("Checklist", back_populates="items")

engine = create_engine("sqlite:///checklists.db", echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base.metadata.create_all(engine)