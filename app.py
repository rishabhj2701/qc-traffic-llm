import glob
import json
import os
import time
from pathlib import Path

import pandas as pd
import plotly.express as px
import re
import streamlit as st

from qc_datapoint import QCDataPointAnalyzer


# Global configuration
DATA_DIR_PATTERN = "export_traffic_data_*"


# Session state initialization
def init_session_state():
    """Initialize session state for cross-page filtering."""
    if 'selected_stations' not in st.session_state:
        st.session_state.selected_stations = []
    if 'date_filter' not in st.session_state:
        st.session_state.date_filter = None
    if 'use_filters' not in st.session_state:
        st.session_state.use_filters = False


def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    """Apply current session filters to dataframe."""
    if not st.session_state.use_filters:
        return df

    filtered_df = df.copy()

    # Station filter
    if st.session_state.selected_stations:
        filtered_df = filtered_df[filtered_df['station_label'].isin(st.session_state.selected_stations)]

    # Date filter
    if st.session_state.date_filter:
        start_date, end_date = st.session_state.date_filter
        filtered_df = filtered_df[
            (filtered_df['date'].dt.date >= start_date) &
            (filtered_df['date'].dt.date <= end_date)
        ]

    return filtered_df


def render_global_filters_sidebar(df: pd.DataFrame):
    """Render global filter controls in sidebar."""
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔍 Global Filters")

    # Filter toggle
    use_filters = st.sidebar.checkbox(
        "Enable Filtering",
        value=st.session_state.use_filters,
        help="Apply filters across all pages"
    )
    st.session_state.use_filters = use_filters

    if use_filters:
        # Station selection
        all_stations = sorted(df['station_label'].unique())
        normalized_selected = []
        if st.session_state.selected_stations:
            station_lookup = {
                str(row['station_id']): row['station_label']
                for _, row in df[['station_id', 'station_label']].drop_duplicates().iterrows()
            }
            for station in st.session_state.selected_stations:
                if station in all_stations:
                    normalized_selected.append(station)
                elif str(station) in station_lookup:
                    normalized_selected.append(station_lookup[str(station)])
        selected_stations = st.sidebar.multiselect(
            "Select Stations",
            options=all_stations,
            default=normalized_selected,
            help="Filter data to selected stations only"
        )
        st.session_state.selected_stations = selected_stations

        # Date range filter
        if 'date' in df.columns:
            min_date = df['date'].min().date()
            max_date = df['date'].max().date()

            date_range = st.sidebar.date_input(
                "Date Range",
                value=st.session_state.date_filter or (min_date, max_date),
                min_value=min_date,
                max_value=max_date,
                help="Filter data by date range"
            )

            if isinstance(date_range, tuple) and len(date_range) == 2:
                st.session_state.date_filter = date_range
            else:
                st.session_state.date_filter = None

        # Filter summary
        if selected_stations or st.session_state.date_filter:
            st.sidebar.markdown("**Active Filters:**")
            if selected_stations:
                st.sidebar.write(f"📍 {len(selected_stations)} stations selected")
            if st.session_state.date_filter:
                start, end = st.session_state.date_filter
                st.sidebar.write(f"📅 {start} to {end}")

    # Reset button
    if st.sidebar.button("🔄 Reset to Full Dataset", type="secondary"):
        st.session_state.selected_stations = []
        st.session_state.date_filter = None
        st.session_state.use_filters = False
        st.rerun()

    # Filter status
    if st.session_state.use_filters and (st.session_state.selected_stations or st.session_state.date_filter):
        st.sidebar.success("✅ Filters Active")
    else:
        st.sidebar.info("📊 Using Full Dataset")


def get_data_directory_info(data_dir: str):
    """Get directory info for cache invalidation."""
    if not data_dir or not os.path.exists(data_dir):
        return None

    csv_files = glob.glob(os.path.join(data_dir, "*.csv"))
    if not csv_files:
        return None

    # Use file count and latest modification time as cache key
    file_count = len(csv_files)
    latest_mtime = max(os.path.getmtime(f) for f in csv_files)
    return {
        'path': data_dir,
        'file_count': file_count,
        'latest_mtime': latest_mtime
    }


@st.cache_resource
def load_analyzer(data_info):
    """Load analyzer with cache based on data directory state."""
    if not data_info:
        return None, None

    data_dir = data_info['path']
    analyzer = QCDataPointAnalyzer()
    df = analyzer.load_intersection_directory(data_dir)
    analyzer.csv_to_json_corpus(
        station_col='station_id',
        date_col='date',
        volume_col='volume',
        roadway_col='roadway',
        qc_status_col='qc_status'
    )
    analyzer.build_vector_store()
    return analyzer, df


def find_data_directory():
    matches = sorted(glob.glob(DATA_DIR_PATTERN))
    return matches[0] if matches else None


def make_peak_summary(df: pd.DataFrame) -> dict:
    peak_row = df.loc[df['volume'].idxmax()]
    busiest_station = peak_row['station_id']
    busiest_time = peak_row['date']
    busiest_volume = int(peak_row['volume'])
    return {
        'peak_station': busiest_station,
        'peak_time': busiest_time,
        'peak_volume': busiest_volume,
        'average_volume': int(df['volume'].mean()),
        'total_volume': int(df['volume'].sum()),
        'unique_roadways': int(df['roadway'].nunique()) if 'roadway' in df.columns else 0,
    }


def build_heatmap(df: pd.DataFrame):
    df = df.copy()
    df['hour'] = df['date'].dt.hour
    pivot = df.pivot_table(index='station_label', columns='hour', values='volume', aggfunc='mean', fill_value=0)
    fig = px.imshow(
        pivot,
        labels={'x': 'Hour of Day', 'y': 'Station', 'color': 'Avg Volume'},
        aspect='auto',
        color_continuous_scale='Viridis'
    )
    fig.update_layout(height=600, margin=dict(l=80, r=20, t=40, b=80))
    return fig


def build_weekday_comparison(df: pd.DataFrame):
    df = df.copy()
    df['weekday'] = df['date'].dt.day_name()
    df['weekend'] = df['date'].dt.weekday >= 5
    weekday_summary = df.groupby('weekday')['volume'].mean().reindex(
        ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    )
    fig = px.bar(
        x=weekday_summary.index,
        y=weekday_summary.values,
        labels={'x': 'Day of Week', 'y': 'Avg Volume'},
        title='Average Volume by Day of Week'
    )
    fig.update_traces(marker_color='teal')
    fig.update_layout(height=450, margin=dict(l=40, r=20, t=50, b=60))
    return fig


def build_mode_breakdown(df: pd.DataFrame):
    df = df.copy()
    mode_df = df[['station_label', 'volume', 'volume_bicycle', 'volume_pedestrian']].groupby('station_label').mean().reset_index()
    long_df = mode_df.melt(id_vars='station_label', var_name='mode', value_name='average')
    fig = px.bar(
        long_df,
        x='station_label',
        y='average',
        color='mode',
        labels={'station_label': 'Station', 'average': 'Average Count', 'mode': 'Mode'},
        title='Mode Breakdown by Station',
    )
    fig.update_layout(barmode='group', xaxis={'categoryorder': 'total descending'}, height=520, margin=dict(l=40, r=20, t=50, b=110))
    return fig


def df_download_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode('utf-8')


def corpus_download_bytes(analyzer: QCDataPointAnalyzer) -> bytes:
    text = "\n".join(json.dumps(obs) for obs in analyzer.corpus)
    return text.encode('utf-8')


def extract_llm_text(result):
    if hasattr(result, 'answer'):
        return result.answer
    return str(result)


def extract_llm_confidence(result):
    if hasattr(result, 'confidence_score') and hasattr(result, 'confidence_label'):
        return f"{result.confidence_score}% ({result.confidence_label})"
    return None


def extract_llm_confidence_detail(result):
    return getattr(result, 'confidence_detail', None)


def parse_station_files(data_dir: str):
    files = sorted(glob.glob(os.path.join(data_dir, '*.csv')))
    station_files = {}
    for filepath in files:
        filename = os.path.basename(filepath)
        if filename.startswith('Intersection_'):
            label = filename[len('Intersection_'):].split('_')[0]
            station_files[label] = station_files.get(label, 0) + 1
    return station_files, len(files)


def get_location_summary(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return 'Location metadata unavailable.'
    if 'lat' in df.columns and 'lng' in df.columns and not df['lat'].isna().all() and not df['lng'].isna().all():
        lat = df['lat'].median()
        lng = df['lng'].median()
        return f'Approximate location cluster around {lat:.5f}, {lng:.5f}.'
    return 'Location coordinates are not available in the dataset.'


def has_valid_coordinates(df: pd.DataFrame) -> bool:
    if df is None or df.empty:
        return False
    if 'lat' not in df.columns or 'lng' not in df.columns:
        return False
    coords = df[['lat', 'lng']].dropna()
    coords = coords[(coords['lat'] != 0) | (coords['lng'] != 0)]
    return not coords.empty


def build_station_metadata(df: pd.DataFrame) -> pd.DataFrame:
    meta = df.groupby(['station_label', 'station_id', 'roadway', 'lat', 'lng'], dropna=False).agg(
        avg_volume=('volume', 'mean'),
        total_volume=('volume', 'sum'),
        avg_bicycle=('volume_bicycle', 'mean'),
        avg_pedestrian=('volume_pedestrian', 'mean'),
        qc_flag_count=('qc_status', lambda x: (x != 'OK').sum())
    ).reset_index()
    meta['avg_volume'] = meta['avg_volume'].round(1)
    meta['avg_bicycle'] = meta['avg_bicycle'].round(1)
    meta['avg_pedestrian'] = meta['avg_pedestrian'].round(1)
    return meta.sort_values('avg_volume', ascending=False)


def build_map_figure(df: pd.DataFrame):
    coords = df[['station_label', 'station_name', 'station_id', 'roadway', 'lat', 'lng', 'volume']].dropna()
    coords = coords[(coords['lat'] != 0) | (coords['lng'] != 0)]
    if coords.empty:
        return None
    station_geo = coords.groupby(['station_label', 'station_name', 'station_id', 'roadway', 'lat', 'lng']).agg(avg_volume=('volume', 'mean')).reset_index()
    fig = px.scatter_mapbox(
        station_geo,
        lat='lat',
        lon='lng',
        size='avg_volume',
        color='avg_volume',
        hover_name='station_label',
        hover_data={'roadway': True, 'station_id': True, 'avg_volume': ':.1f'},
        zoom=11,
        height=520
    )
    fig.update_layout(mapbox_style='open-street-map', margin=dict(l=0, r=0, t=35, b=0))
    return fig


PAGE_OPTIONS = [
    'Data Overview',
    'Use Case 1: Query & Navigation',
    'Use Case 2: Summarization',
    'Use Case 3: Analytics & Patterns'
]


def extract_station_id_from_label(label: str) -> str:
    match = re.search(r'\(([^)]+)\)\s*$', label)
    return match.group(1) if match else label


def enrich_station_labels(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if 'roadway' in df.columns:
        df['station_name'] = df['roadway'].fillna('').astype(str)
        df.loc[df['station_name'].str.strip() == '', 'station_name'] = df['station_id'].astype(str)
    else:
        df['station_name'] = df['station_id'].astype(str)

    df['station_label'] = df.apply(
        lambda row: f"{row['station_name']} ({row['station_id']})",
        axis=1
    )
    return df


def build_evaluation_worksheet(df: pd.DataFrame) -> pd.DataFrame:
    busiest_station = df.groupby('station_id')['volume'].mean().idxmax() if not df.empty else 'N/A'
    top_weekday = df.groupby('weekday')['volume'].mean().idxmax() if 'weekday' in df.columns and not df.empty else 'N/A'
    qc_counts = df['qc_status'].value_counts(normalize=True).mul(100).round(1).to_dict() if 'qc_status' in df.columns else {}
    worst_qc_label = max(qc_counts, key=qc_counts.get) if qc_counts else 'N/A'
    bicycle_leader = df.groupby('station_id')['volume_bicycle'].sum().idxmax() if 'volume_bicycle' in df.columns and not df.empty else 'N/A'

    worksheet = pd.DataFrame([
        {
            'Phase 1 Category': 'A',
            'Feature': 'Query & navigation',
            'Prompt / Question': 'Which station has the highest average volume?',
            'Actual Result': f'Station {busiest_station}',
            'LLM Answer': '',
            'Confidence': ''
        },
        {
            'Phase 1 Category': 'A',
            'Feature': 'Query & navigation',
            'Prompt / Question': 'What weekday has the strongest AM peak?',
            'Actual Result': f'{top_weekday}',
            'LLM Answer': '',
            'Confidence': ''
        },
        {
            'Phase 1 Category': 'B',
            'Feature': 'Summarization',
            'Prompt / Question': 'Summarize the main QC issues and data quality status.',
            'Actual Result': f'Most common QC label: {worst_qc_label}',
            'LLM Answer': '',
            'Confidence': ''
        },
        {
            'Phase 1 Category': 'C',
            'Feature': 'Analytical assistance',
            'Prompt / Question': 'Which station has the highest bicycle volume?',
            'Actual Result': f'Station {bicycle_leader}',
            'LLM Answer': '',
            'Confidence': ''
        }
    ])
    return worksheet


def page_data_overview(filtered_df: pd.DataFrame, df: pd.DataFrame, analyzer: QCDataPointAnalyzer, stats: dict, station_files: dict, csv_count: int, location_summary: str, data_dir: str):
    st.subheader('Data Overview & Map')
    st.write('Explore the full dataset, station metadata, and geographic coverage. Use the station picker below to focus the entire dashboard on a specific location.')

    station_options = ['All stations'] + sorted(df['station_label'].unique())
    default_index = 0
    if st.session_state.selected_stations:
        selected_station = st.session_state.selected_stations[0]
        if selected_station in station_options:
            default_index = station_options.index(selected_station)
    station_selector = st.selectbox('Select a station to filter across all pages', station_options, index=default_index)
    if st.button('🔎 Apply station filter', key='apply_station_filter'):
        if station_selector == 'All stations':
            st.session_state.use_filters = False
            st.session_state.selected_stations = []
        else:
            st.session_state.use_filters = True
            st.session_state.selected_stations = [station_selector]
        st.rerun()

    summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)
    summary_col1.metric('📊 Total Records', f"{len(filtered_df):,}")
    summary_col2.metric('📍 Stations Shown', filtered_df['station_label'].nunique() if not filtered_df.empty else 0)
    summary_col3.metric('📁 CSV Files', csv_count)
    summary_col4.metric('🚗 Avg Volume', f"{int(filtered_df['volume'].mean()):,}" if not filtered_df.empty else 'N/A')

    if st.session_state.use_filters and st.session_state.selected_stations:
        st.info(f"Active filter: {', '.join(st.session_state.selected_stations)}")

    with st.expander('Station metadata and map', expanded=True):
        if not filtered_df.empty and has_valid_coordinates(filtered_df):
            map_figure = build_map_figure(filtered_df)
            st.plotly_chart(map_figure, use_container_width=True)
        elif filtered_df.empty:
            st.warning('No rows are available after filtering.')
        else:
            st.info('Coordinates are not sufficient to render a station map.')

        metadata = build_station_metadata(filtered_df)
        st.write('**Station metadata with labels, coordinates, and QC flags**')
        st.dataframe(
            metadata[['station_label', 'station_id', 'roadway', 'lat', 'lng', 'avg_volume', 'total_volume', 'avg_bicycle', 'avg_pedestrian', 'qc_flag_count']],
            width='stretch'
        )

    with st.expander('Overview charts', expanded=True):
        if filtered_df.empty:
            st.warning('No charts available for the current filter selection.')
        else:
            chart1, chart2 = st.columns([2, 1])
            with chart1:
                st.plotly_chart(build_heatmap(filtered_df), use_container_width=True)
            with chart2:
                st.plotly_chart(build_weekday_comparison(filtered_df), use_container_width=True)
                st.plotly_chart(build_mode_breakdown(filtered_df), use_container_width=True)

    with st.expander('Dataset validation and station file counts', expanded=False):
        st.write('Validating the folder and station mapping for the selected dataset.')
        st.write(f'- **CSV directory:** {data_dir}')
        st.write(f'- **Total CSV files found:** {csv_count}')
        st.write(f'- **Parsed station IDs in data:** {df["station_id"].nunique()}')
        station_label_count = len(station_files)
        st.write(f'- **Station labels discovered from filenames:** {station_label_count}')
        st.write('**Station labels from CSV filenames:**')
        st.write(', '.join(sorted(station_files.keys())))
        st.write('**File count per station label:**')
        file_counts = pd.DataFrame(
            sorted(station_files.items(), key=lambda x: x[1], reverse=True),
            columns=['station_label', 'csv_file_count']
        )
        st.dataframe(file_counts, width=700)

    with st.expander('Download outputs', expanded=False):
        download_col1, download_col2 = st.columns(2)
        with download_col1:
            st.download_button(
                'Download QC Corpus',
                data=corpus_download_bytes(analyzer),
                file_name='qc_traffic_corpus.jsonl',
                mime='application/json'
            )
        with download_col2:
            st.download_button(
                'Download Raw CSV',
                data=df_download_bytes(df),
                file_name='qc_traffic_data.csv',
                mime='text/csv'
            )

    st.markdown('---')
    st.markdown('### Why this page matters')
    st.write(
        '- Use this page as the dashboard control center for station selection and dataset quality review. '
        'Filters selected here propagate across all pages to keep charts, LLM context, and summaries aligned.'
    )


def page_query_navigation(filtered_df: pd.DataFrame, analyzer: QCDataPointAnalyzer, df: pd.DataFrame):
    st.subheader('Use Case 1: Query & Navigation')
    st.write('Ask the LLM questions about the traffic dataset and explore results for the selected stations.')

    station_options = ['All stations'] + sorted(df['station_label'].unique())
    default_index = 0
    if st.session_state.selected_stations:
        selected_station = st.session_state.selected_stations[0]
        if selected_station in station_options:
            default_index = station_options.index(selected_station)

    selected_label = st.selectbox('Station focus for this page', station_options, index=default_index, key='query_station_focus')
    if st.button('🔎 Apply station focus', key='query_station_apply'):
        if selected_label == 'All stations':
            st.session_state.use_filters = False
            st.session_state.selected_stations = []
        else:
            st.session_state.use_filters = True
            st.session_state.selected_stations = [selected_label]
        st.rerun()

    if st.session_state.use_filters and st.session_state.selected_stations:
        st.success(f"Filter applied to dashboard: {', '.join(st.session_state.selected_stations)}")

    st.write(f'*Dataset rows in view: {len(filtered_df):,}*')
    query = st.text_area('💬 Ask a traffic question:', 'What are the weekday AM peak trends for the selected stations?', help='Ask any question about traffic patterns, station performance, or QC status.')

    if st.button('🚀 Run AI Query', key='use_case_1_query'):
        with st.spinner('Searching relevant data and generating answer...'):
            result = analyzer.natural_language_query(query)
        st.markdown('### 📝 AI Answer')
        st.markdown(extract_llm_text(result))
        confidence_text = extract_llm_confidence(result)
        if confidence_text:
            confidence_class = f"confidence-{result.confidence_label.lower()}"
            st.markdown(f"""
            <div style="display: flex; align-items: center; gap: 1rem; margin: 1rem 0;">
            <div><strong>Reliability</strong>: <span class="{confidence_class}">{confidence_text}</span></div>
            </div>
            """, unsafe_allow_html=True)
        confidence_detail = extract_llm_confidence_detail(result)
        if confidence_detail:
            st.caption(confidence_detail)

    with st.expander('Sample dataset rows for current filters', expanded=True):
        st.dataframe(filtered_df.head(10), use_container_width=True)


def page_summarization(filtered_df: pd.DataFrame, analyzer: QCDataPointAnalyzer):
    st.subheader('Use Case 2: Summarization')
    st.write('Generate QC narratives, summaries, and consulting-style recommendations for the filtered dataset.')

    station_options = ['All stations'] + sorted(filtered_df['station_label'].unique())
    selected_label = st.selectbox('Summarize by station', station_options, index=0, key='summarization_station')
    station_arg = None
    if selected_label != 'All stations':
        station_arg = extract_station_id_from_label(selected_label)

    if st.button('📊 Generate QC Narrative', key='use_case_2_narrative'):
        with st.spinner('Generating QC narrative...'):
            result = analyzer.generate_qc_narrative(station_filter=station_arg)
        st.markdown('### 📋 QC Narrative')
        st.markdown(extract_llm_text(result))
        confidence_text = extract_llm_confidence(result)
        if confidence_text:
            st.caption(f'Confidence: {confidence_text}')
        confidence_detail = extract_llm_confidence_detail(result)
        if confidence_detail:
            st.write(confidence_detail)

    if st.button('👔 Generate Consultant Memo', key='use_case_2_memo'):
        with st.spinner('Generating consultant memo...'):
            result = analyzer.run_agentic_consultation(focus_area='Safety and Infrastructure')
        st.markdown('### 👔 Consultant Memo')
        st.markdown(extract_llm_text(result))
        confidence_text = extract_llm_confidence(result)
        if confidence_text:
            st.caption(f'Confidence: {confidence_text}')
        confidence_detail = extract_llm_confidence_detail(result)
        if confidence_detail:
            st.write(confidence_detail)

    st.markdown('---')
    st.write('**Current filtered summary**')
    st.write(filtered_df.describe(include='all'))


def page_analytics(filtered_df: pd.DataFrame, analyzer: QCDataPointAnalyzer):
    st.subheader('Use Case 3: Analytics & Patterns')
    st.write('View charts, station performance, and ask the AI to detect patterns in the filtered data.')

    if st.session_state.use_filters and st.session_state.selected_stations:
        st.success(f"Filter applied to dashboard: {', '.join(st.session_state.selected_stations)}")

    top_station = filtered_df.groupby('station_label')['volume'].mean().idxmax() if not filtered_df.empty else 'N/A'
    st.markdown(f'**Top average volume station:** {top_station}')

    if filtered_df.empty:
        st.warning('No analytics available for the current filter selection.')
    else:
        chart1, chart2 = st.columns(2)
        with chart1:
            st.plotly_chart(build_heatmap(filtered_df), use_container_width=True)
        with chart2:
            st.plotly_chart(build_weekday_comparison(filtered_df), use_container_width=True)
            st.plotly_chart(build_mode_breakdown(filtered_df), use_container_width=True)

    pattern_type = st.selectbox('Pattern type to analyze', ['temporal', 'volume', 'speed', 'general'], help='Choose the kind of pattern the AI should analyze.')
    station_options = ['All stations'] + sorted(filtered_df['station_label'].unique())
    selected_label = st.selectbox('Pattern station filter', station_options, index=0, key='analytics_station')
    station_arg = extract_station_id_from_label(selected_label) if selected_label != 'All stations' else None

    if st.button('🔍 Detect Patterns', key='use_case_3_patterns'):
        with st.spinner('Analyzing patterns...'):
            result = analyzer.detect_patterns(pattern_type=pattern_type, station_filter=station_arg)
        st.markdown('### 🔎 Pattern Detection Result')
        st.markdown(extract_llm_text(result))
        confidence_text = extract_llm_confidence(result)
        if confidence_text:
            confidence_class = f"confidence-{result.confidence_label.lower()}"
            st.markdown(f"""
            <div style="display: flex; align-items: center; gap: 1rem; margin: 1rem 0;">
            <div><strong>Confidence</strong>: <span class="{confidence_class}">{confidence_text}</span></div>
            </div>
            """, unsafe_allow_html=True)
        confidence_detail = extract_llm_confidence_detail(result)
        if confidence_detail:
            st.caption(confidence_detail)

    st.markdown('---')
    if not filtered_df.empty:
        station_summary = filtered_df.groupby('station_label')['volume'].agg(['mean', 'sum']).sort_values('sum', ascending=False).reset_index()
        st.write('**Top stations by volume**')
        st.dataframe(station_summary.head(10), use_container_width=True)
    else:
        st.warning('No data available for analytics with the current filter.')


def render_dashboard():
    st.set_page_config(
        page_title='QC Traffic Intelligence',
        layout='wide',
        initial_sidebar_state='expanded',
        page_icon='🚗'
    )

    init_session_state()

    # Custom CSS for better styling
    st.markdown("""
    <style>
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 3rem;
        font-weight: bold;
        text-align: center;
        margin-bottom: 1rem;
    }
    .metric-card {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #007bff;
        margin: 0.5rem 0;
    }
    .phase-summary {
        background: linear-gradient(135deg, #4e79a7 0%, #2a5f8b 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 1rem;
        margin: 1rem 0;
    }
    .confidence-high { color: #28a745; font-weight: bold; }
    .confidence-medium { color: #ffc107; font-weight: bold; }
    .confidence-low { color: #dc3545; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<h1 class="main-header">🚗 QC Traffic Intelligence Dashboard</h1>', unsafe_allow_html=True)
    st.markdown(
        '<div style="text-align: center; font-size: 1.2rem; color: #666; margin-bottom: 2rem;">'
        'A modern traffic analytics showcase with data summaries, interactive charts, and LLM-driven insights.'
        '</div>', unsafe_allow_html=True
    )

    with st.expander('🎯 Phase 1 Use Case Summary', expanded=True):
        st.markdown("""
        <div class="phase-summary">
        <h3 style="margin-top: 0;">Phase 1: LLM Exploration for Traffic QC Data</h3>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1rem; margin-top: 1rem;">
        <div style="background: rgba(255,255,255,0.1); padding: 1rem; border-radius: 0.5rem;">
        <h4>📊 A: Query & Navigation</h4>
        <p>Natural language dataset querying, station discovery, and interactive filter-based exploration.</p>
        </div>
        <div style="background: rgba(255,255,255,0.1); padding: 1rem; border-radius: 0.5rem;">
        <h4>📋 B: Summarization</h4>
        <p>Automated QC narratives, dataset summaries, and consultant-style recommendations.</p>
        </div>
        <div style="background: rgba(255,255,255,0.1); padding: 1rem; border-radius: 0.5rem;">
        <h4>🔍 C: Analytical Assistance</h4>
        <p>Pattern detection, station performance analytics, and change-aware visualizations.</p>
        </div>
        </div>
        </div>
        """, unsafe_allow_html=True)
        st.write('This dashboard is organized by page so selections, filters, and station focus stay consistent across views.')

    data_dir = find_data_directory()
    if not data_dir:
        st.error(f'No directory matching "{DATA_DIR_PATTERN}" was found. Please place your export folder in the project root.')
        return

    st.sidebar.header('Dashboard Navigation')
    page = st.sidebar.radio('Choose a page', PAGE_OPTIONS, index=PAGE_OPTIONS.index(st.session_state.get('selected_page', PAGE_OPTIONS[0])))
    st.session_state.selected_page = page

    st.sidebar.markdown('---')
    st.sidebar.header('Dataset Controls')
    st.sidebar.write(f'Loaded dataset: **{data_dir}**')

    data_info = get_data_directory_info(data_dir)
    if data_info:
        st.sidebar.write(f'Files: {data_info["file_count"]} | Last modified: {pd.to_datetime(data_info["latest_mtime"], unit="s").strftime("%Y-%m-%d %H:%M")}')

    if len(sorted(glob.glob(DATA_DIR_PATTERN))) > 1:
        latest_dir = sorted(glob.glob(DATA_DIR_PATTERN))[-1]
        if latest_dir != data_dir:
            st.sidebar.warning(f'⚠️ Newer data directory detected: {os.path.basename(latest_dir)}')
            if st.sidebar.button('Load Newer Dataset'):
                st.cache_resource.clear()
                st.rerun()

    if st.sidebar.button('🔄 Refresh Data', help='Reload data if new files were added to the export folder'):
        st.cache_resource.clear()
        st.rerun()

    with st.sidebar.expander('Model & LLM Controls'):
        st.write('Your OpenAI key is loaded from the environment via .env.')
        st.write('If no key is present, the analyzer will run in MOCK mode.')
        st.write('LLM responses are generated live based on dataset context.')

    analyzer, df = load_analyzer(data_info)
    df = enrich_station_labels(df)
    df['weekday'] = df['date'].dt.day_name()
    df['hour'] = df['date'].dt.hour
    df['is_weekend'] = df['date'].dt.weekday >= 5

    station_files, csv_count = parse_station_files(data_dir)
    location_summary = get_location_summary(df)
    stats = make_peak_summary(df)

    render_global_filters_sidebar(df)
    filtered_df = apply_filters(df)

    if st.session_state.use_filters and st.session_state.selected_stations:
        st.info(f"Active dashboard filter: {', '.join(st.session_state.selected_stations)}")

    if page == 'Data Overview':
        page_data_overview(filtered_df, df, analyzer, stats, station_files, csv_count, location_summary, data_dir)
    elif page == 'Use Case 1: Query & Navigation':
        page_query_navigation(filtered_df, analyzer, df)
    elif page == 'Use Case 2: Summarization':
        page_summarization(filtered_df, analyzer)
    elif page == 'Use Case 3: Analytics & Patterns':
        page_analytics(filtered_df, analyzer)

    st.sidebar.markdown('---')
    st.sidebar.write('Use the reset button below to clear filters and return to the full dataset.')

    if st.sidebar.button('🔁 Reset View', key='sidebar_reset'):
        st.session_state.selected_stations = []
        st.session_state.date_filter = None
        st.session_state.use_filters = False
        st.rerun()

    llm_status = '🟢 Active' if analyzer and analyzer.client else '🟡 Mock Mode'
    st.sidebar.markdown(f'**AI Status:** {llm_status}')


if __name__ == '__main__':
    render_dashboard()
