"""
Phase 1 POC UI — matches presentation pages:
  Overview | NL Query Interface | QC Narratives | Pattern Detection
ISU cardinal (#C8102E) and gold (#F1BE48) accents.
"""
import json
import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sql_rag.config.phase1_config import (
    BENCHMARK_QUERIES,
    CRITICAL_STATIONS,
    DB_PATH,
    PEAK_REAL_ADT,
    PEAK_REAL_STATION,
    PRIMARY_SCOPE_STATIONS,
    TOTAL_CSV_FILES,
)
from sql_rag.models import ApproachType
from sql_rag.pipeline import (
    GroundedAnalyticalSystem,
    DirectLLMApproach,
    QCNarrativeEngine,
    PatternDetectionEngine,
)
from sql_rag.retrieval.query_router import QueryRouter

st.set_page_config(
    page_title="QC Traffic LLM — Phase 1 POC",
    page_icon="🚦",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
    .stApp { background-color: #1a1a1a; color: #f5f5f5; }
    .isu-header {
        font-size: 2.2rem; font-weight: 800; color: #C8102E;
        border-bottom: 3px solid #F1BE48; padding-bottom: 0.4rem;
    }
    .metric-box {
        background: linear-gradient(135deg, #2a2a2a 0%, #1f1f1f 100%);
        border-left: 4px solid #C8102E;
        padding: 1rem 1.2rem; border-radius: 8px;
    }
    .pass { color: #4ade80; } .crit { color: #f87171; } .mod { color: #F1BE48; }
    .trace-step { font-family: monospace; font-size: 0.85rem; padding: 4px 0; }
</style>
""",
    unsafe_allow_html=True,
)

DB = str(DB_PATH)
if "router" not in st.session_state:
    st.session_state.router = QueryRouter(DB)
if "grounded" not in st.session_state:
    st.session_state.grounded = st.session_state.router.grounded
if "qc_engine" not in st.session_state:
    st.session_state.qc_engine = QCNarrativeEngine()
if "pattern_engine" not in st.session_state:
    st.session_state.pattern_engine = PatternDetectionEngine()

with st.sidebar:
    st.markdown('<p class="isu-header">QC Traffic LLM</p>', unsafe_allow_html=True)
    st.caption("Phase 1 POC — Grounded Analytical System")
    page = st.radio(
        "Navigation",
        [
            "Overview",
            "Query Interface",
            "QC Narratives",
            "Pattern Detection",
            "Methodology Compare",
        ],
    )
    st.divider()
    schema = st.session_state.router.registry.load_schema()
    st.metric("SQLite tables", len(schema))
    st.metric("CSV source files", TOTAL_CSV_FILES)

# --- Overview ---
if page == "Overview":
    st.markdown('<p class="isu-header">Dataset Overview</p>', unsafe_allow_html=True)
    st.markdown(
        "Quality Counts staging data — **Alexandria, VA** | "
        "Architecture: **Grounded Analytical System**"
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("CSV Files", TOTAL_CSV_FILES)
    c2.metric("Primary Scope", PRIMARY_SCOPE_STATIONS)
    c3.metric("Peak Real ADT", f"{PEAK_REAL_ADT:,}")
    c4.metric("Peak Station", PEAK_REAL_STATION)

    st.markdown("### QC Tier Summary (31 primary-scope stations)")
    t1, t2, t3 = st.columns(3)
    t1.markdown('<p class="pass"><b>22 Pass</b> (71%)</p>', unsafe_allow_html=True)
    t2.markdown('<p class="mod"><b>4 Moderate</b> (13%)</p>', unsafe_allow_html=True)
    t3.markdown('<p class="crit"><b>5 Critical</b> (16%)</p>', unsafe_allow_html=True)

    st.markdown("### Architecture Pipeline")
    st.code(
        "User Query → Intent Router → Query Planner → Schema Registry\n"
        "→ SQL Generator → SQL Validator → Execution Engine\n"
        "→ [RAG Layer] → Grounding System → Evaluation Layer → Conversation Memory",
        language="text",
    )
    st.markdown("**Critical exclude:** " + ", ".join(CRITICAL_STATIONS))

# --- Query Interface ---
elif page == "Query Interface":
    st.markdown('<p class="isu-header">Natural Language Query Interface</p>', unsafe_allow_html=True)
    approach = st.radio(
        "Methodology",
        ["Grounded Analytical System", "Direct LLM (comparison)"],
        horizontal=True,
    )
    use_grounded = approach.startswith("Grounded")

    with st.expander("5 Verified Benchmark Queries"):
        for bq in BENCHMARK_QUERIES:
            if st.button(bq["question"][:70] + "…", key=bq["id"]):
                st.session_state.pending_query = bq["question"]

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("sql"):
                with st.expander("SQL"):
                    st.code(msg["sql"], language="sql")
            if msg.get("metrics"):
                st.json(msg["metrics"])

    prompt = st.session_state.pop("pending_query", None) or st.chat_input(
        "Ask about Station 725, ADT, peaks…"
    )

    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("assistant"):
            with st.spinner("Running pipeline…"):
                if use_grounded:
                    resp = st.session_state.grounded.process(prompt)
                else:
                    resp = st.session_state.router.direct.answer(prompt)
                st.markdown(resp.answer)
                metrics = {
                    "approach": resp.approach.value,
                    "confidence": resp.confidence,
                    "grounding_score": resp.grounding_score,
                    "hallucination_risk": resp.hallucination_risk,
                    "reproducible": resp.reproducible,
                }
                st.json(metrics)
                if resp.rows:
                    st.dataframe(pd.DataFrame(resp.rows))
                if resp.sql:
                    st.code(resp.sql, language="sql")
                if resp.trace.pipeline_steps:
                    st.markdown("**Pipeline trace**")
                    for step in resp.trace.pipeline_steps:
                        st.markdown(
                            f'<div class="trace-step">✓ {step.component} '
                            f"({step.duration_ms} ms) — {step.detail}</div>",
                            unsafe_allow_html=True,
                        )
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": resp.answer,
                        "sql": resp.sql,
                        "metrics": metrics,
                    }
                )

# --- QC Narratives ---
elif page == "QC Narratives":
    st.markdown('<p class="isu-header">Automated QC Narratives</p>', unsafe_allow_html=True)
    st.markdown("Use Case 2 — rule-based scan of **457 CSV files** (no hallucination on detection rules).")
    if st.button("Run Global Quality Audit", type="primary"):
        with st.spinner("Scanning staging folder…"):
            report = st.session_state.qc_engine.generate_narrative_report()
        st.markdown(report["narrative"])
        if report["anomalies"]:
            st.dataframe(pd.DataFrame(report["anomalies"]))
        st.success(f"Detected {report['count']} distinct anomaly types.")

# --- Pattern Detection ---
elif page == "Pattern Detection":
    st.markdown('<p class="isu-header">Contextual Pattern Detection</p>', unsafe_allow_html=True)
    patterns = st.session_state.pattern_engine.VERIFIED_PATTERNS
    station = st.selectbox("Station", ["All"] + sorted({p.station_id for p in patterns}))
    sid = None if station == "All" else station
    summary = st.session_state.pattern_engine.summarize(sid)
    st.markdown(summary["narrative"])
    st.dataframe(pd.DataFrame(summary["patterns"]))

# --- Methodology Compare ---
else:
    st.markdown('<p class="isu-header">Methodology Comparison</p>', unsafe_allow_html=True)
    demo_q = st.text_input(
        "Demo question",
        "What is the ADT for Station 1191 on April 9, 2025?",
    )
    if st.button("Compare approaches"):
        col_g, col_d = st.columns(2)
        with col_g:
            st.subheader("Grounded Analytical System")
            rg = st.session_state.grounded.process(demo_q)
            st.write(rg.answer)
            st.caption(
                f"Confidence {rg.confidence:.3f} | "
                f"Grounding {rg.grounding_score:.3f} | "
                f"Hallucination risk {rg.hallucination_risk:.3f}"
            )
            if rg.sql:
                st.code(rg.sql, language="sql")
        with col_d:
            st.subheader("Direct LLM")
            rd = st.session_state.router.direct.answer(demo_q)
            st.write(rd.answer)
            st.caption(f"Hallucination risk ~{rd.hallucination_risk:.0%} (ungrounded)")
