from db import *
from contextlib import contextmanager

@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

with get_db() as db:
    #create_checklist(db, "William", "First Checklist")
    print(get_all_checklists(db))