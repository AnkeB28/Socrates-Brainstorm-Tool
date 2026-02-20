import json
import pandas as pd
import streamlit as st
from openai import OpenAI

st.set_page_config(page_title="Socrates Brainstorm Tool", layout="centered")

# -----------------------------
# Files in repo
# -----------------------------
QUESTIONS_FILE = "Sheet 1 - Questions ULTRAKORTE VERSIE DEF.csv"
SUMMARY_FILE = "Sheet 2 - Summary Mappings ULTRAKORTE VERSIE DEF.csv"

# -----------------------------
# Helpers
# -----------------------------
def _read_csv(path: str) -> pd.DataFrame:
    # utf-8-sig handles BOM if present
    return pd.read_csv(path, encoding="utf-8-sig").fillna("")

@st.cache_data(show_spinner=False)
def load_data():
    qdf = _read_csv(QUESTIONS_FILE)
    sdf = _read_csv(SUMMARY_FILE)

    # Normalize columns (strip spaces from colnames)
    qdf.columns = [c.strip() for c in qdf.columns]
    sdf.columns = [c.strip() for c in sdf.columns]

    # Build dicts of plain Python dict rows (no pandas Series in session!)
    questions = {}
    for _, row in qdf.iterrows():
        sid = str(row.get("StepID", "")).strip()
        if sid:
            questions[sid] = {k: (str(v).strip() if v is not None else "") for k, v in row.to_dict().items()}

    summaries = {}
    for _, row in sdf.iterrows():
        sid = str(row.get("SummaryID", "")).strip()
        if sid:
            summaries[sid] = {k: (str(v).strip() if v is not None else "") for k, v in row.to_dict().items()}

    if "G1" not in questions:
        raise ValueError("Kan StepID 'G1' niet vinden in Questions CSV.")

    return questions, summaries

def get_secret(name: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(name, default)).strip()
    except Exception:
        return default

def start_new_session(project_name: str):
    st.session_state.project_name = project_name.strip()
    st.session_state.current_step = "G1"
    st.session_state.answers = {}
    st.session_state.generated_summaries = {}  # {SummaryID: text}
    st.session_state.started = True
    st.session_state.intro_shown = False

def session_payload() -> dict:
    return {
        "project_name": st.session_state.get("project_name", ""),
        "current_step": st.session_state.get("current_step", "G1"),
        "answers": st.session_state.get("answers", {}),
        "generated_summaries": st.session_state.get("generated_summaries", {}),
    }

def restore_session(payload: dict):
    st.session_state.project_name = str(payload.get("project_name", "")).strip() or "Onbenoemd project"
    st.session_state.current_step = str(payload.get("current_step", "G1")).strip() or "G1"
    st.session_state.answers = payload.get("answers", {}) or {}
    st.session_state.generated_summaries = payload.get("generated_summaries", {}) or {}
    st.session_state.started = True
    st.session_state.intro_shown = False

def call_summary_openai(client: OpenAI, model: str, hint: str, qa_text: str) -> str:
    instructions = (
        "Je bent een neutrale samenvatter voor brainstorm-antwoorden van studenten.\n"
        "Verzin niets, interpreteer niet, en leg geen nieuwe verbanden.\n\n"
        "Gebruik exact dit format:\n"
        "**Samenvatting (lens: <PromptCategoryHint>)**\n\n"
        "1) **Kern** (2–4 zinnen, feitelijk)\n"
        "2) **Wat kristalliseert** (max 3 bullets)\n"
        "3) **Open plekken** (max 3 bullets)\n\n"
        "Regels:\n"
        "- Geen oordeel.\n"
        "- Geen coaching-taal.\n"
        "- Alleen gebruiken wat letterlijk in de antwoorden staat.\n"
    )

    resp = client.responses.create(
        model=model,
        instructions=instructions,
        input=f"PromptCategoryHint: {hint}\n\nTe gebruiken Q/A:\n{qa_text}",
        temperature=0,
    )
    # SDK provides output_text convenience
    return (resp.output_text or "").strip()

# -----------------------------
# Load data
# -----------------------------
try:
    QUESTIONS, SUMMARIES = load_data()
except Exception as e:
    st.error(f"Data laden mislukt: {e}")
    st.stop()

# -----------------------------
# Initialize session state
# -----------------------------
if "started" not in st.session_state:
    st.session_state.started = False
if "project_name" not in st.session_state:
    st.session_state.project_name = ""
if "current_step" not in st.session_state:
    st.session_state.current_step = "G1"
if "answers" not in st.session_state:
    st.session_state.answers = {}
if "generated_summaries" not in st.session_state:
    st.session_state.generated_summaries = {}
if "intro_shown" not in st.session_state:
    st.session_state.intro_shown = False

# -----------------------------
# Sidebar: controls + export/resume
# -----------------------------
with st.sidebar:
    st.header("Sessie")
    st.caption("Deze tool volgt strikt jouw CSV-flow. Vragen worden nooit door AI bedacht.")

    # Model selection (optional)
    default_model = get_secret("OPENAI_MODEL", "gpt-4.1")
    model = st.text_input("Model (voor samenvattingen)", value=default_model)

    st.divider()
    st.subheader("Opslaan / hervatten")
    st.caption("Streamlit bewaart niet automatisch na tab sluiten. Gebruik checkpoint om later verder te gaan.")

    checkpoint = json.dumps(session_payload(), ensure_ascii=False, indent=2)
    st.download_button(
        "Download checkpoint (JSON)",
        data=checkpoint,
        file_name=f"{(st.session_state.project_name or 'project').replace(' ', '_')}_checkpoint.json",
        mime="application/json",
        use_container_width=True,
    )

    uploaded = st.file_uploader("Hervat: upload checkpoint (JSON)", type=["json"])
    if uploaded is not None:
        try:
            payload = json.load(uploaded)
            restore_session(payload)
            st.success("Checkpoint geladen. Je kunt verder.")
            st.rerun()
        except Exception as e:
            st.error(f"Kon checkpoint niet laden: {e}")

    st.divider()
    if st.button("Reset (nieuw project)", use_container_width=True):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

# -----------------------------
# Start screen
# -----------------------------
if not st.session_state.started:
    st.title("Socrates Brainstorm Tool")

    col1, col2 = st.columns(2)
    with col1:
        project = st.text_input("Projectnaam (of je eigen naam)")
        if st.button("Start nieuw", use_container_width=True):
            if project.strip():
                start_new_session(project)
                st.rerun()
            else:
                st.warning("Vul eerst een projectnaam in.")

    with col2:
        st.info("Wil je later verder? Gebruik straks ‘Download checkpoint (JSON)’ in de sidebar.")

    st.stop()

# -----------------------------
# Main flow
# -----------------------------
st.title(f"Project: {st.session_state.project_name}")

# Intro line only once per session start
if not st.session_state.intro_shown:
    st.info("Ik stel je één vraag per keer. Af en toe vat ik samen en ga ik door.")
    st.session_state.intro_shown = True

step_id = str(st.session_state.current_step).strip()
step = QUESTIONS.get(step_id)

if step is None:
    st.error(f"Onbekende stap: {step_id}")
    st.stop()

step_type = str(step.get("StepType", "")).strip().lower()
next_step = str(step.get("NextStepID", "")).strip()

# -----------------------------
# QUESTION STEP (deterministic)
# -----------------------------
if step_type == "question":
    question_text = str(step.get("QuestionText", "")).strip()

    st.markdown("### Vraag")
    st.write(question_text)

    # Prefill prior answer if present
    existing = st.session_state.answers.get(step_id, "")
    answer = st.text_area("Jouw antwoord", value=existing, height=180, key=f"answer_{step_id}")

    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("Volgende", use_container_width=True):
            st.session_state.answers[step_id] = answer.strip()
            st.session_state.current_step = next_step
            st.rerun()

    with c2:
        if st.button("Download checkpoint nu", use_container_width=True):
            # just triggers sidebar download button usability reminder
            st.toast("Gebruik de downloadknop in de sidebar om je checkpoint te bewaren.", icon="💾")

# -----------------------------
# SUMMARY STEP
# -----------------------------
elif step_type == "summary":
    summary_id = str(step.get("TriggerSummaryID", "")).strip()

    st.markdown("### Samenvatting")

    if not summary_id:
        st.warning("Deze summary-stap heeft geen TriggerSummaryID. Ga verder.")
        if st.button("Ga verder", use_container_width=True):
            st.session_state.current_step = next_step
            st.rerun()
        st.stop()

    mapping = SUMMARIES.get(summary_id)
    if mapping is None:
        st.error(f"Geen mapping gevonden voor SummaryID: {summary_id}")
        if st.button("Ga verder", use_container_width=True):
            st.session_state.current_step = next_step
            st.rerun()
        st.stop()

    # If already generated, show cached summary (no extra API calls)
    if summary_id in st.session_state.generated_summaries:
        st.markdown(st.session_state.generated_summaries[summary_id])
    else:
        included_raw = str(mapping.get("QuestionIDsIncluded", "")).strip()
        included_ids = [x.strip() for x in included_raw.split("|") if x.strip()]
        hint = str(mapping.get("PromptCategoryHint", "")).strip()

        # Build Q/A bundle deterministically from stored answers
        qa_lines = []
        for qid in included_ids:
            qrow = QUESTIONS.get(qid)
            qtext = str(qrow.get("QuestionText", "")).strip() if qrow else "(onbekende vraag)"
            ans = st.session_state.answers.get(qid, "")
            ans = ans.strip() if isinstance(ans, str) and ans.strip() else "(geen antwoord)"
            qa_lines.append(f"{qid} — {qtext}\nAntwoord: {ans}\n")

        qa_text = "\n".join(qa_lines)

        # Call OpenAI only when user clicks (prevents surprise costs on rerun)
        st.caption("Klik op ‘Genereer samenvatting’ om de AI-samenvatting te maken.")
        if st.button("Genereer samenvatting", use_container_width=True):
            api_key = get_secret("OPENAI_API_KEY", "")
            if not api_key:
                st.error("OPENAI_API_KEY ontbreekt in Streamlit Secrets.")
                st.stop()

            client = OpenAI(api_key=api_key)
            with st.spinner("Samenvatting maken…"):
                summary_text = call_summary_openai(client, model=model, hint=hint, qa_text=qa_text)

            st.session_state.generated_summaries[summary_id] = summary_text
            st.rerun()

    if st.button("Ga verder", use_container_width=True):
        st.session_state.current_step = next_step
        st.rerun()

# -----------------------------
# Unknown StepType
# -----------------------------
else:
    st.error(f"Onbekende StepType '{step_type}' bij StepID '{step_id}'.")
    st.stop()
