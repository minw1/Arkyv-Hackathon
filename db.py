# db.py
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Boolean, ForeignKey, Text
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()


def now_iso():
    return datetime.utcnow().isoformat(timespec="seconds")


class Checklist(Base):
    __tablename__ = "checklists"

    id = Column(Integer, primary_key=True)
    user_name = Column(String, nullable=False)
    checklist_name = Column(String, nullable=False)
    created_at = Column(String, default=now_iso, nullable=False)
    updated_at = Column(String, default=now_iso, nullable=False)

    items = relationship(
        "ChecklistItem",
        back_populates="checklist",
        cascade="all, delete-orphan",
    )


class ChecklistItem(Base):
    __tablename__ = "checklist_items"

    id = Column(Integer, primary_key=True)
    checklist_id = Column(Integer, ForeignKey("checklists.id"), nullable=False)
    label = Column(Text, nullable=False)
    category = Column(String, nullable=False)
    is_done = Column(Boolean, default=False, nullable=False)
    # store JSON / delimited text for hackathon speed
    bbr_sections = Column(Text)   # e.g. '["5:12","5:251"]' or "5:12;5:251"
    bbr_texts = Column(Text)      # e.g. '["text1","text2"]' or joined text

    checklist = relationship("Checklist", back_populates="items")


# SQLite file in project root
engine = create_engine(
    "sqlite:///checklists.db",
    connect_args={"check_same_thread": False},  # needed for Streamlit
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
)


def init_db():
    Base.metadata.create_all(engine)


# ---------- Helper functions ----------

def get_all_checklists(db):
    return (
        db.query(Checklist)
        .order_by(Checklist.created_at.desc())
        .all()
    )


def get_checklist(db, checklist_id: int):
    return (
        db.query(Checklist)
        .filter(Checklist.id == checklist_id)
        .first()
    )


def get_items_for_checklist(db, checklist_id: int):
    return (
        db.query(ChecklistItem)
        .filter(ChecklistItem.checklist_id == checklist_id)
        .order_by(ChecklistItem.id.asc())
        .all()
    )


def create_checklist(db, user_name: str, checklist_name: str):
    cl = Checklist(user_name=user_name, checklist_name=checklist_name)
    db.add(cl)
    db.commit()
    db.refresh(cl)
    return cl


def add_item(
    db,
    checklist_id: int,
    label: str,
    category: str,
    bbr_sections: str = "",
    bbr_texts: str = "",
):
    item = ChecklistItem(
        checklist_id=checklist_id,
        label=label,
        category=category,
        bbr_sections=bbr_sections,
        bbr_texts=bbr_texts,
    )
    db.add(item)

    checklist = get_checklist(db, checklist_id)
    if checklist:
        checklist.updated_at = now_iso()

    db.commit()
    db.refresh(item)
    return item


def set_item_done(db, item_id: int, done: bool):
    item = (
        db.query(ChecklistItem)
        .filter(ChecklistItem.id == item_id)
        .first()
    )
    if not item:
        return

    if item.is_done != done:
        item.is_done = done
        if item.checklist:
            item.checklist.updated_at = now_iso()
        db.commit()
