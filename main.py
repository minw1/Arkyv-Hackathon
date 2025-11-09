import streamlit as st
from contextlib import contextmanager
from db import (
    SessionLocal,
    init_db,
    get_all_checklists,
    get_checklist,
    get_items_for_checklist,
    create_checklist,
    add_item,
    set_item_done,
)

st.title("Egenkontroll Lists")


@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

init_db()


def create(file, user_name, checklist_name):
    with get_db() as db:
        create_checklist(db,user_name,checklist_name)

@st.dialog("Upload")
def upload():
    left, right = st.columns(2)
    checklist_name = left.text_input("Checklist Name")
    user_name = right.text_input("User Name")
    uploaded_file = st.file_uploader("Egenkontroll File")
    if st.button("Create"):
        create(uploaded_file, user_name, checklist_name)
        st.rerun()


with st.sidebar:
    st.title("Checklists")
    with get_db() as db:
        checklists = get_all_checklists(db)
    if checklists:
        for checklist in checklists:
            st.button(checklist.checklist_name)
    if st.button("Create New"):
        upload()
        