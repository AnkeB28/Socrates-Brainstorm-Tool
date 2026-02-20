import streamlit as st
import pandas as pd
import json
import os
from openai import OpenAI

st.set_page_config(page_title="Socrates Brainstorm Tool", layout="centered")

# =============================
# Load CSV files
# =============================

QUESTIONS_FILE = "Sheet 1 - Questions ULTRAKORTE VERSIE DEF.csv"
SUMMARY_FILE = "Sheet 2 - Summary Mappings ULTRAKORTE VERSIE DEF.csv"

questions_df = pd.read_csv(QUESTIONS_FILE).fillna("")
summary_df = pd.read_csv(SUMMARY_FILE).fillna("")

questions = {
    str(row["StepID"]).strip(): row.to_dict()
    for _, row in questions_df.iterrows()
    if str(row["StepID"]).strip() != ""
}

summaries = {
    str(row["SummaryID"]).strip(): row.to_dict()
    for _, row in summary_df.iterrows()
    if str(row["SummaryID"]).strip() != ""
}

# =============================
# Session state initialization
# =============================

if "project_name" not in st.session_state:
    st.session_state.project_name = None

if "current_step" not in st.session_state:
    st.session_state.current_step = "G1"

if "answers" not in st.session_state:
    st.session_state.answers = {}

if "started" not in st.session_state:
    st.session_state.started = False

# =============================
# Project Name Screen
# =============================

if not st.session_state.started:
    st.title("Socrates Brainstorm Tool")

    project = st.text_input("Wat is je projectnaam (of je eigen naam)?")

    if st.button("Start"):
        if project.strip() != "":
            st.session_state.project_name = project.strip()
            st.session_state.started = True
            st.rerun()

    st.stop()

# =============================
# Brainstorm Flow
# =============================

st.title(f"Project: {st.session_state.project_name}")

step_id = str(st.session_state.current_step).strip()
step = questions.get(step_id)

if step is None:
    st.error("Onbekende stap.")
    st.stop()

step_type = step["StepType"].strip().lower()
next_step = step["NextStepID"]

# =============================
# QUESTION STEP (deterministic)
# =============================

if step_type == "question":

    question_text = step["QuestionText"]

    st.markdown("### Vraag")
    st.write(question_text)

    answer = st.text_area("Jouw antwoord", key=f"input_{step_id}")

    if st.button("Volgende"):
        st.session_state.answers[step_id] = answer
        st.session_state.current_step = next_step
        st.rerun()

# =============================
# SUMMARY STEP
# =============================

elif step_type == "summary":

    summary_id = str(step["TriggerSummaryID"]).strip()
    mapping = summaries.get(summary_id)

    if mapping is None:
    st.error(f"Geen mapping gevonden voor SummaryID: {summary_id}")
    if st.button("Ga verder"):
        st.session_state.current_step = next_step
        st.rerun()
    st.stop()
      included_ids = [x.strip() for x in mapping["QuestionIDsIncluded"].split("|") if x.strip()]
        hint = mapping["PromptCategoryHint"]

        qa_text = ""
        for qid in included_ids:
            qid = qid.strip()
            q_row = questions.get(qid)
            q_text = q_row["QuestionText"] if q_row is not None else "(onbekende vraag)"
            a_text = st.session_state.answers.get(qid, "(geen antwoord)")
            qa_text += f"{qid} — {q_text}\nAntwoord: {a_text}\n\n"

        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

        response = client.responses.create(
            model="gpt-4.1",
            instructions="""
Je bent een neutrale samenvatter.
Verzin niets.
Gebruik exact dit format:

**Samenvatting (lens: <PromptCategoryHint>)**

1) **Kern**
2) **Wat kristalliseert**
3) **Open plekken**

Geen oordeel.
Geen nieuwe interpretaties.
""",
            input=f"PromptCategoryHint: {hint}\n\nTe gebruiken antwoorden:\n{qa_text}",
        )

        summary_text = response.output_text

        st.markdown(summary_text)

    if st.button("Ga verder"):
        st.session_state.current_step = next_step
        st.rerun()

# =============================
# EXPORT
# =============================

st.divider()

if st.button("Download export als JSON"):
    export_data = {
        "project": st.session_state.project_name,
        "answers": st.session_state.answers
    }
    st.download_button(
        label="Klik hier om te downloaden",
        data=json.dumps(export_data, indent=2, ensure_ascii=False),
        file_name=f"{st.session_state.project_name}_export.json",
        mime="application/json"
    )
