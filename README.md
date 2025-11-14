# Arkyv Workflows – Egenkontroll Projects

Streamlit-based workflow that turns Swedish *egenkontroll* (self-inspection) checklists into an interactive project tracker.  
The app ingests PDFs/JSON files, enriches each inspection item with BBR paragraph references via LangChain + OpenAI, optionally assigns employees, and persists everything in a local SQLite database that is surfaced through a richer UI.

- Upload egenkontroll PDFs/JSON exports and (optionally) a PDF with employee capabilities
- Auto-tag every inspection item with categories such as `energihushållning`, `fuktskydd`, etc.
- Retrieve the most relevant BBR sections using a Chroma vector store and GPT-4.1
- Track completion status per item, filter by category/assignee/status, and store results in `checklists.db`

---

## Prerequisites

- macOS / Linux (tested on macOS 14+)
- Python 3.13 (required by the pinned wheels in `requirements.txt`)
- OpenAI API access (for GPT-4.1 and `text-embedding-3-large`)
- Optional: LangSmith/LangChain keys if you want tracing or different model providers

Environment variables are loaded from a `.env` file by `agent.py`. At minimum set:

```bash
OPENAI_API_KEY=<your key>
```

---

## Local Setup


```bash
# 1. Create a clean virtual environment (called `venv`)
python3 -m venv venv

# 2. Activate it for your shell
source venv/bin/activate            # fish: source venv/bin/activate.fish

# 3. Install every dependency (LangChain, Streamlit, Chroma, OpenTelemetry, etc.)
pip install -r requirements.txt
```

> Tip: the dependency set is large (~1.5 GB of wheels). First install can take a few minutes; reruns will hit pip’s cache.

---

## Running the Streamlit demo

```bash
source venv/bin/activate
python3 text_extract.py   # updates parsed egenkontroll content feeding the agent
python3 make_db.py        # seeds or resets the local chroma DB with starter rows
streamlit run app.py
```

What happens on startup:

1. `db.init_db()` automatically creates/updates `checklists.db` in the repo root (even if you skip `make_db.py`).
2. The sidebar lists every stored project (if fresh, use “Create New” to import one).
3. Upload either:
   - An egenkontroll PDF/JSON to seed checklist items, and/or
   - An employee capability PDF so `agent.get_assignment()` can name a responsible colleague.
4. Items appear with badges, BBR cross-references, assignments, and status toggles.

The UI state (filters, active checklist, dialogs) lives in Streamlit session state, so page reloads maintain context.

---

## Data & Supporting Scripts

- `checklists.db` – SQLite file generated on demand. Delete it to reset state.
- `chroma_langchain_db/` – persisted vector store that backs `agent.get_sections`.
- `egenkontroll_extract.py` – parses PDF egenkontroll documents into structured inspection items.
- `make_db.py`, `create_db.py`, `db_tests.py` – utilities for experimenting with the persistence layer.
- `employee-descriptions.pdf`, `egenkontroll-*.json/pdf` – sample corpora you can use for demos.

---

Happy building! Run `streamlit run app.py`, upload a spec, and start closing out those inspection items. 💥

