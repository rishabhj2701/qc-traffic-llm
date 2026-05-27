#!/usr/bin/env python3
"""
SQL-based RAG Traffic Data Analyzer
Run this instead of app.py to use database queries instead of CSV loading.
"""

import streamlit as st
import pandas as pd
import os
import sqlite3
from sql_rag.qc_datapoint import QCDataPointAnalyzer
from setup_database import update_database_if_needed

# Page configuration
st.set_page_config(
    page_title="Traffic Data Analyzer - SQL RAG",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Check if database exists
DB_PATH = 'traffic_data.db'
DATASETS_DIR = "../datasets"

if not os.path.exists(DB_PATH):
    st.error("Database not found! Please run setup_database.py first to import CSV data into the database.")
    st.stop()

# Get current dataset info
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
cursor.execute("SELECT value FROM metadata WHERE key = 'last_dataset'")
result = cursor.fetchone()
current_dataset = result[0] if result else "Unknown"
conn.close()

st.title("🚗 Traffic Data Quality Control Dashboard - SQL RAG")
st.markdown(f"*Database-powered RAG Analysis | Current Dataset: {current_dataset}*")

# Manual refresh button
if st.button("🔄 Check for Dataset Updates"):
    with st.spinner("Checking for updates..."):
        updated = update_database_if_needed(DB_PATH, DATASETS_DIR)
        if updated:
            st.success("Database updated! Refreshing...")
            st.cache_resource.clear()
            st.rerun()
        else:
            st.info("No updates found - database is current")

# Load analyzer
@st.cache_resource
def load_analyzer():
    # Check for database updates
    updated = update_database_if_needed(DB_PATH, "../datasets")
    if updated:
        st.cache_resource.clear()
        st.rerun()
    
    analyzer = QCDataPointAnalyzer(db_path=DB_PATH)
    df = analyzer.load_from_database()
    analyzer.csv_to_json_corpus(
        station_col='station_id',
        date_col='date',
        volume_col='volume',
        roadway_col='station_name'
    )
    analyzer.build_vector_store()
    analyzer.close_db()
    return analyzer, df

analyzer, df = load_analyzer()

if df is None or df.empty:
    st.error("No data loaded from database.")
    st.stop()

st.success(f"Loaded {len(df)} records from {len(df['station_id'].unique())} stations")

# Basic data overview
st.header("Data Overview")
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total Stations", len(df['station_id'].unique()))
with col2:
    st.metric("Total Records", len(df))
with col3:
    st.metric("Date Range", f"{df['date'].min()} to {df['date'].max()}")

# Sample data
st.header("Sample Data")
st.dataframe(df.head(10))

# Query interface
st.header("Natural Language Query")
query = st.text_input("Ask a question about the traffic data:")

if query and st.button("Search"):
    try:
        results = analyzer.semantic_search(query, top_k=5)
        st.subheader("Relevant Results:")
        for i, result in enumerate(results):
            with st.expander(f"Result {i+1}: Station {result['station']['id']}"):
                st.json(result)
    except Exception as e:
        st.error(f"Search failed: {e}")

# LLM Query
st.header("LLM Analysis")
llm_query = st.text_area("Ask the LLM for analysis:")

if llm_query and st.button("Analyze"):
    try:
        result = analyzer.natural_language_query(llm_query)
        st.subheader("LLM Response:")
        st.write(result.answer)
        st.write(f"Confidence: {result.confidence_score} ({result.confidence_label})")
    except Exception as e:
        st.error(f"LLM query failed: {e}")

if __name__ == "__main__":
    pass