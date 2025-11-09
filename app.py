# app.py
import json
import streamlit as st
from contextlib import contextmanager
from agent import get_sections
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

st.set_page_config(page_title="Egenkontroll Lists", layout="wide")
st.title("Egenkontroll Lists")

# ---------- DB session management ----------
@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Initialize DB schema
init_db()

# ---------- Session state ----------
if "active_checklist_id" not in st.session_state:
    st.session_state.active_checklist_id = None
if "bbr_dialog_section" not in st.session_state:
    st.session_state.bbr_dialog_section = None
if "bbr_dialog_text" not in st.session_state:
    st.session_state.bbr_dialog_text = None

def set_active_checklist(checklist_id: int):
    st.session_state.active_checklist_id = checklist_id

# ---------- BBR dialog ----------
@st.dialog("BBR Text")
def bbr_dialog():
    section = st.session_state.get("bbr_dialog_section")
    text = st.session_state.get("bbr_dialog_text")
    if section:
        st.markdown(f"### {section}")
    if text:
        st.write(text)
    else:
        st.write("No BBR text available for this section.")


# ---------- Checklist creation (from upload) ----------
def create_from_upload(uploaded_file, user_name: str, checklist_name: str, content):
    """
    Use the output from generate_checklist(...) to create DB rows.

    content: (ek_items, sections, section_texts)
    """
    if not user_name or not checklist_name or not uploaded_file or not content:
        return

    ek_items, sections, section_texts = content

    # Safety: lengths must align 1:1
    if not (
        isinstance(ek_items, list)
        and isinstance(sections, list)
        and isinstance(section_texts, list)
        and len(ek_items) == len(sections) == len(section_texts)
    ):
        # You can replace this with st.error(...) if you prefer UI feedback
        raise ValueError("Checklist generation produced misaligned data.")

    with get_db() as db:
        checklist = create_checklist(db, user_name=user_name, checklist_name=checklist_name)
        checklist_id = checklist.id

        for ek_item, bbr_sections_json, bbr_texts_json in zip(
            ek_items, sections, section_texts
        ):
            # Heuristic: pull label/category from the original ek_item
            if isinstance(ek_item, dict):
                label = (
                    ek_item.get("label")
                    or ek_item.get("text")
                    or ek_item.get("name")
                    or str(ek_item)
                )
                category = ek_item.get("category") or "General"
            else:
                label = str(ek_item)
                category = "General"

            if not label:
                label = "Untitled item"

            add_item(
                db,
                checklist_id=checklist_id,
                label=label,
                category=category,
                bbr_sections=bbr_sections_json,
                bbr_texts=bbr_texts_json,
            )



def generate_checklist(uploaded_file, user_name, checklist_name):
    """
    From an uploaded JSON file of EK_items, call get_sections(ek_item_text) for each.

    Returns:
        ek_items:      original list from JSON
        sections:      list of JSON strings, e.g. ['["8:41","8:42"]', '["7:41"]', ...]
        section_texts: list of JSON strings, e.g.
                       ['["text for 8:41","text for 8:42"]', '["text for 7:41"]', ...]
    """

    # ---- Basic file-type handling ----
    if uploaded_file.name.endswith(".pdf"):
        # matches upload_dialog's NotImplementedError branch
        raise NotImplementedError("PDF checklists not supported yet.")
    if uploaded_file.name.endswith(".json"):
        ek_items = json.load(uploaded_file) # the list of inspection points
        sections = []
        section_texts = []
        for item in ek_items:
            message, doc_dict = get_sections(item)
            st.write(message)
            codes = json.loads(message)
            code_texts = []
            for code in codes:
                code_texts.append(doc_dict[code])
            sections.append(message)
            section_texts.append(json.dumps(code_texts))

   
        return (ek_items, sections, section_texts)





    
@st.dialog("Create checklist from file")
def upload_dialog():
    left, right = st.columns(2)
    checklist_name = left.text_input("Checklist Name")
    user_name = right.text_input("User Name")
    uploaded_file = st.file_uploader("Egenkontroll File", type=["pdf", "json"])

    create_clicked = st.button("Create")

    if create_clicked:
        if not checklist_name.strip():
            st.error("Please enter a checklist name.")
            return
        if not user_name.strip():
            st.error("Please enter a user name.")
            return
        if not uploaded_file:
            st.error("Please upload a PDF or JSON file.")
            return

        try:
            content = generate_checklist(uploaded_file, user_name, checklist_name)
        except NotImplementedError:
            st.error("PDF parsing is not implemented yet.")
            return
        except Exception as e:
            st.error("We could not generate a checklist from this file.")
            # Uncomment if you want debugging info during hackathon:
            st.exception(e)
            return

        if not content:
            st.error("Checklist generation returned no content.")
            return

        create_from_upload(uploaded_file, user_name, checklist_name, content)
        st.success(f"Checklist '{checklist_name}' created successfully.")
        st.rerun()


# ---------- Load all checklists ----------
with get_db() as db:
    checklists = get_all_checklists(db)

# ---------- Sidebar ----------
with st.sidebar:
    st.title("Checklists")
    if not checklists:
        st.info("No checklists yet.")
    else:
        for cl in checklists:
            label = cl.checklist_name
            if st.session_state.active_checklist_id == cl.id:
                label = f"▶ {label}"
            st.button(
                label,
                key=f"cl_btn_{cl.id}",
                on_click=set_active_checklist,
                args=(cl.id,),
                use_container_width=True,
            )
    st.markdown("---")
    if st.button("Create New", use_container_width=True):
        upload_dialog()

# ---------- Main content ----------
active_id = st.session_state.active_checklist_id
if active_id is None and checklists:
    active_id = checklists[0].id
    st.session_state.active_checklist_id = active_id

if not checklists:
    st.write("👉 Create a checklist from the sidebar to get started.")
elif active_id is None:
    st.write("👉 Select a checklist from the sidebar.")
else:
    with get_db() as db:
        checklist = get_checklist(db, active_id)
        items = get_items_for_checklist(db, active_id)

    if not checklist:
        st.error("Selected checklist not found.")
    else:
        c1, c2, c3 = st.columns([3, 2, 2])
        with c1:
            st.subheader(checklist.checklist_name)
        with c2:
            st.markdown(f"**User:** {checklist.user_name}")
        with c3:
            st.markdown(f"**Last updated:** {checklist.updated_at}")
        st.markdown("---")

        if not items:
            st.info("No items yet. Add one below.")
        else:
            st.markdown("### Items")
            for item in items:
                col_done, col_label, col_cat, col_bbr, col_status = st.columns(
                    [0.5, 3.5, 2, 4, 1.5]
                )
                # --- Done checkbox ---
                with col_done:
                    new_done = st.checkbox("", value=bool(item.is_done), key=f"item_done_{item.id}")
                if new_done != item.is_done:
                    with get_db() as db:
                        set_item_done(db, item.id, new_done)
                    st.rerun()
                # --- Label ---
                with col_label:
                    label_text = f"~~{item.label}~~" if new_done else item.label
                    st.markdown(label_text)
                # --- Category ---
                with col_cat:
                    st.caption(item.category)
                # --- BBR sections (max 5 consistent-width buttons) ---
                with col_bbr:
                    try:
                        sections = json.loads(item.bbr_sections) if item.bbr_sections else []
                    except json.JSONDecodeError:
                        sections = []
                    try:
                        texts = json.loads(item.bbr_texts) if item.bbr_texts else []
                    except json.JSONDecodeError:
                        texts = []
                    if not isinstance(sections, list):
                        sections = []
                    if not isinstance(texts, list):
                        texts = []
                    max_buttons = 5
                    bbr_cols = st.columns(max_buttons, gap="small")
                    for i in range(max_buttons):
                        with bbr_cols[i]:
                            if i < len(sections):
                                section_label = str(sections[i])
                                key = f"bbr_btn_{item.id}_{i}"
                                if st.button(section_label, key=key, use_container_width=True):
                                    text = texts[i] if i < len(texts) else ""
                                    st.session_state["bbr_dialog_section"] = section_label
                                    st.session_state["bbr_dialog_text"] = text
                                    bbr_dialog()

                # --- Status ---
                with col_status:
                    st.caption("✅" if new_done else "⏳")

        st.markdown("---")
        st.markdown("### Add new item")
        with st.form(f"add_item_form_{checklist.id}", clear_on_submit=True):
            label = st.text_input("Label", key=f"label_{checklist.id}")
            category = st.text_input("Category", key=f"category_{checklist.id}")
            bbr_sections = st.text_input(
                'BBR sections JSON (e.g. ["5:12","5:251"])',
                key=f"bbr_sections_{checklist.id}",
            )
            bbr_texts = st.text_area(
                'BBR texts JSON (e.g. ["text for 5:12", "text for 5:251"])',
                key=f"bbr_texts_{checklist.id}",
            )
            submitted = st.form_submit_button("Add item")
            if submitted:
                if not label or not category:
                    st.error("Label and category are required.")
                else:
                    with get_db() as db:
                        add_item(
                            db,
                            checklist_id=checklist.id,
                            label=label,
                            category=category,
                            bbr_sections=bbr_sections,
                            bbr_texts=bbr_texts,
                        )
                    st.success("Item added.")
                    st.rerun()
