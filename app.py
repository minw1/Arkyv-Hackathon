# app.py
import json
import streamlit as st
from contextlib import contextmanager
from agent import get_sections, get_category
import time
from egenkontroll_extract import process_egenkontroll_document


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
all_categories = ["beständighet", "hälsa och inomhusklimat", "ljusinsläpp","miljöppåverkan", "resurshållning", "bullerskydd", "energihushållning", "fuktskydd", "trafik och kommunikation", "annat"]
CATEGORY_STYLES = {
    "beständighet": {"color": "#2563EB", "emoji": "🧱"},   # blue
    "hälsa och inomhusklimat": {"color": "#16A34A", "emoji": "🌿"},  # green
    "ljusinsläpp": {"color": "#EAB308", "emoji": "☀️"},  # toned down amber
    "miljöppåverkan": {"color": "#22C55E", "emoji": "🌍"},  # light green
    "resurshållning": {"color": "#0EA5E9", "emoji": "♻️"},  # cyan
    "bullerskydd": {"color": "#8B5CF6", "emoji": "🔇"},  # violet
    "energihushållning": {"color": "#F97316", "emoji": "⚡"},  # orange
    "fuktskydd": {"color": "#06B6D4", "emoji": "💧"},  # teal
    "trafik och kommunikation": {"color": "#EC4899", "emoji": "🚦"},  # pink
    "annat": {"color": "#6B7280", "emoji": "📁"},  # gray
}

def category_badge(category: str):
    """Render a consistent-width, outlined, left-aligned category badge."""
    style = CATEGORY_STYLES.get(category, {"color": "#6B7280", "emoji": "❓"})
    main_color = style["color"]

    html = f"""
    <div style="
        display:inline-flex;
        align-items:center;
        justify-content:flex-start;
        gap:0.4rem;
        padding:0.25rem 0.6rem;
        border-radius:999px;
        background-color:{main_color}20;  /* subtle fill */
        border:2px solid {main_color};    /* bright outline */
        font-size:0.8rem;
        font-family:system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
        color:var(--text-color);
        font-weight:500;
        white-space:nowrap;
        min-width:8.5rem;
        max-width:8.5rem;
        overflow:hidden;
        text-overflow:ellipsis;
    ">
        <span style="flex-shrink:0;">{style['emoji']}</span>
        <span style="overflow:hidden;text-overflow:ellipsis;">{category}</span>
    </div>
    """
    return html


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
if "filter_category" not in st.session_state:
    st.session_state.filter_category = "All"
if "filter_status" not in st.session_state:
    st.session_state.filter_status = "All"

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

    ek_items, sections, section_texts, categories = content

    # Safety: lengths must align 1:1
    if not (
        isinstance(ek_items, list)
        and isinstance(sections, list)
        and isinstance(section_texts, list)
        and isinstance(categories, list)
        and len(ek_items) == len(sections) == len(section_texts) == len(categories)
    ):
        # You can replace this with st.error(...) if you prefer UI feedback
        raise ValueError("Checklist generation produced misaligned data.")

    with get_db() as db:
        checklist = create_checklist(db, user_name=user_name, checklist_name=checklist_name)
        checklist_id = checklist.id

        for ek_item, bbr_sections_json, bbr_texts_json, category in zip(
            ek_items, sections, section_texts, categories
        ):

            label = str(ek_item)

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
    st.session_state.active_checklist_id = checklist_id



def generate_checklist(uploaded_file, user_name, checklist_name, progress_bar):
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
        ek_items = list(process_egenkontroll_document(uploaded_file))
        #st.write(ek_items)

    elif uploaded_file.name.endswith(".json"):
        ek_items = json.load(uploaded_file) # the list of inspection points
    else:
        raise Exception("Must be pdf or json")

    sections = []
    section_texts = []
    categories = []
    counter = 0
    def get_text(x):
        if x < .3:
            return "Analyzing conditions..."
        if x < .6:
            return "Referencing building codes..."
        return "Generating checklist..."
    for item in ek_items:
        counter += 1
        done_prop = float(counter/len(ek_items))
        progress_bar.progress(done_prop,text=get_text(done_prop))
        message, doc_dict = get_sections(item)
        category = get_category(item)
        st.write(category)
        if not category in all_categories:
            category = "annat"
        categories.append(category)
        try:
            codes = json.loads(message)
            code_texts = []
            for code in codes:
                code_texts.append(doc_dict[code])
            sections.append(message)
            section_texts.append(json.dumps(code_texts))
        except:
            sections.append(json.dumps([]))
            section_texts.append(json.dumps([]))

   
    return (ek_items, sections, section_texts, categories)





    
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
            progress_bar = st.progress(0.0, text="Reading egenkontroll document")
            content = generate_checklist(uploaded_file, user_name, checklist_name, progress_bar)
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
        time.sleep(.5)
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

        # --- Progress bar + completed count ---
        total_items = len(items)
        completed_items = sum(1 for it in items if it.is_done) if total_items else 0
        progress = completed_items / total_items if total_items else 0.0

        p_left, p_middle, p_right = st.columns([2, 1, 4])
        with p_left:
            st.progress(progress)
        with p_middle:
            st.markdown(f"**{completed_items}/{total_items} completed**")
        # p_right stays empty to push everything left

        if not items:
            st.info("No items yet. Add one below.")
        else:
            # NEW CODE:
            st.markdown("### Items")

            # --- Filters ---
            # Get unique categories from items
            all_categories = sorted(list(set(item.category for item in items if item.category)))
            categories_options = ["All"] + all_categories
            
            filter_col1, filter_col2, filter_col3 = st.columns([2, 2, 6])
            with filter_col1:
                filter_category = st.selectbox(
                    "Filter by Category",
                    options=categories_options,
                    index=categories_options.index(st.session_state.filter_category) if st.session_state.filter_category in categories_options else 0,
                    key="filter_category_select"
                )
                st.session_state.filter_category = filter_category
            
            with filter_col2:
                filter_status = st.selectbox(
                    "Filter by Status",
                    options=["All", "Completed", "Pending"],
                    index=["All", "Completed", "Pending"].index(st.session_state.filter_status),
                    key="filter_status_select"
                )
                st.session_state.filter_status = filter_status

            # Apply filters
            filtered_items = items
            if filter_category != "All":
                filtered_items = [item for item in filtered_items if item.category == filter_category]
            if filter_status == "Completed":
                filtered_items = [item for item in filtered_items if item.is_done]
            elif filter_status == "Pending":
                filtered_items = [item for item in filtered_items if not item.is_done]

            # Show filtered count
            if len(filtered_items) < len(items):
                st.caption(f"Showing {len(filtered_items)} of {len(items)} items")

            # Header row for the columns
            hdr_done, hdr_label, hdr_cat, hdr_bbr, hdr_status = st.columns(
                [0.5, 3.5, 2, 4, 1.5]
            )

            with hdr_done:
                st.write("")  # empty header for the checkbox column
            with hdr_label:
                st.markdown("**Control point**")
            with hdr_cat:
                st.markdown("**Category**")
            with hdr_bbr:
                st.markdown("**BBR Sections**")
            with hdr_status:
                st.markdown("**Status**")

            for item in filtered_items:
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
                    st.html(category_badge(item.category))
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
        with st.expander("Add new item"):
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
