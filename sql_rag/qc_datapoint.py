"""
QC DataPoint LLM Analytics System - SQL Version
Implementation of Three Core Use Cases:
1. Natural Language Query Interface
2. Automated Data Quality Narratives
3. Contextual Pattern Detection & Explanation

Requirements:
pip install anthropic pandas numpy scikit-learn faiss-cpu python-dotenv sqlite3
"""

import os
import json
import pandas as pd
import numpy as np
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any, Optional
import sqlite3

from sklearn.feature_extraction.text import TfidfVectorizer
import faiss
from dotenv import load_dotenv
import openai
from openai import OpenAI
import matplotlib.pyplot as plt
import seaborn as sns

# Load environment variables
load_dotenv()

@dataclass
class LLMResult:
    answer: str
    confidence_score: int
    confidence_label: str
    confidence_detail: str


class QCDataPointAnalyzer:
    """
    Main class for analyzing QC DataPoint traffic data using OpenAI LLM with SQL backend
    """
    
    def __init__(self, db_path: str = 'traffic_data.db', api_key: Optional[str] = None):
        """
        Initialize the analyzer with SQL database and OpenAI API
        
        Args:
            db_path: Path to SQLite database
            api_key: OpenAI API key (if not provided, reads from env)
        """
        self.db_path = db_path
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            print("WARNING: OPENAI_API_KEY not found. Running in MOCK LLM mode.")
            self.client = None
            self.model_candidates = []
        else:
            self.client = OpenAI(api_key=self.api_key)
            self.model_candidates = ["gpt-3.5-turbo", "gpt-4o", "gpt-4o-mini"]
        
        self.corpus = []
        self.vector_store = None
        self.vectorizer = None
        self.df = None
        self.conn = None
        
    def connect_db(self):
        """Connect to the SQLite database."""
        self.conn = sqlite3.connect(self.db_path)
        
    def close_db(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
        
    def _extract_response_text(self, response: Any) -> str:
        """Extract text from OpenAI 1.x response output."""
        try:
            output_item = response.output[0]
            content_item = output_item.content[0]
            return content_item.text
        except Exception:
            try:
                return str(response)
            except Exception:
                return ""

    def _estimate_llm_confidence(self,
                                 num_relevant_obs: int,
                                 use_mock: bool = False,
                                 has_coord_data: bool = False,
                                 qc_issue_count: int = 0) -> LLMResult:
        """Compute a simple confidence score and label for the LLM response."""
        if use_mock:
            score = 25
            label = 'Low'
            detail = 'Mock LLM mode is active. The answer is illustrative, not model-backed.'
        else:
            score = 35 + min(45, num_relevant_obs * 8)
            if has_coord_data:
                score += 5
            if qc_issue_count > 0:
                score += 5
            score = min(max(score, 20), 95)
            if score >= 80:
                label = 'High'
            elif score >= 60:
                label = 'Medium'
            else:
                label = 'Low'
            reason_parts = [f'{num_relevant_obs} relevant obs']
            if has_coord_data:
                reason_parts.append('location metadata available')
            if qc_issue_count > 0:
                reason_parts.append(f'{qc_issue_count} QC issue flags noted')
            detail = 'Based on ' + ', '.join(reason_parts) + '.'
        return LLMResult(answer='', confidence_score=score, confidence_label=label, confidence_detail=detail)

    def _call_llm(self, prompt: str) -> str:
        """Call the first available OpenAI model from the configured list."""
        if not self.client:
            return ""
        last_error = None
        for model in self.model_candidates:
            print(f"Trying OpenAI model: {model}")
            try:
                response = self.client.responses.create(
                    model=model,
                    input=prompt,
                    timeout=30
                )
                text = self._extract_response_text(response)
                if text:
                    print(f"Model {model} succeeded")
                    return text
                print(f"Model {model} returned no text; trying next model")
            except Exception as exc:
                err_text = str(exc).lower()
                if "model not found" in err_text or "does not have access" in err_text or "permission denied" in err_text:
                    print(f"WARNING: Model {model} unavailable: {exc}")
                    last_error = exc
                    continue
                raise
        if last_error:
            raise last_error
        raise RuntimeError(f"No accessible OpenAI model available from {self.model_candidates}")

    def load_csv_data(self, csv_path: str) -> pd.DataFrame:
        """
        Load traffic count data from CSV file
        
        Args:
            csv_path: Path to CSV file with traffic data
            
        Returns:
            Loaded DataFrame
        """
        print(f"Loading data from {csv_path}...")
        self.df = pd.read_csv(csv_path)
        
        # Parse dates if present
        date_columns = ['date', 'Date', 'DATE', 'collection_date', 'timestamp']
        for col in date_columns:
            if col in self.df.columns:
                try:
                    self.df[col] = pd.to_datetime(self.df[col])
                    break
                except:
                    pass
        
        print(f"Loaded {len(self.df)} records")
        print(f"Columns: {list(self.df.columns)}")
        return self.df
    
    def load_from_database(self) -> pd.DataFrame:
        """
        Load traffic data from SQLite database
        
        Returns:
            Loaded DataFrame
        """
        print(f"Loading data from database {self.db_path}...")
        self.connect_db()
        
        # Load stations
        stations_df = pd.read_sql_query("SELECT * FROM stations", self.conn)
        
        # Load traffic data
        query = """
        SELECT 
            td.*,
            s.name as station_name,
            s.type as station_type,
            s.latitude,
            s.longitude,
            s.city_state
        FROM traffic_data td
        LEFT JOIN stations s ON td.station_id = s.id
        """
        self.df = pd.read_sql_query(query, self.conn)
        
        # Convert date column
        if 'date' in self.df.columns:
            self.df['date'] = pd.to_datetime(self.df['date'], errors='coerce')
        
        print(f"Loaded {len(self.df)} records from database")
        print(f"Columns: {list(self.df.columns)}")
        return self.df
    
    def csv_to_json_corpus(self, 
                          station_col: str = 'station_id',
                          date_col: str = 'date',
                          volume_col: str = 'volume',
                          roadway_col: Optional[str] = None,
                          speed_mean_col: Optional[str] = None,
                          speed_p85_col: Optional[str] = None,
                          qc_status_col: Optional[str] = None) -> List[Dict]:
        """
        Convert database data to structured JSON corpus for LLM
        
        Args:
            station_col: Column name for station ID
            date_col: Column name for date
            volume_col: Column name for volume count
            roadway_col: Column name for roadway/street name
            speed_mean_col: Column name for mean speed
            speed_p85_col: Column name for 85th percentile speed
            qc_status_col: Column name for QC status/flags
            
        Returns:
            List of observation dictionaries
        """
        print("Converting database data to JSON corpus...")
        self.corpus = []
        
        for idx, row in self.df.iterrows():
            # Prepare raw data dict, converting Timestamps to strings for JSON serialization
            raw_dict = row.to_dict()
            for k, v in raw_dict.items():
                if pd.isna(v):
                    raw_dict[k] = None
                elif isinstance(v, pd.Timestamp):
                    raw_dict[k] = v.isoformat()
            
            # Build observation object
            obs = {
                "observation_id": f"OBS_{idx}",
                "station": {
                    "id": str(row.get(station_col, f"UNKNOWN_{idx}")),
                    "roadway": str(row.get('station_name', "")),
                },
                "temporal": {
                    "date": str(row.get(date_col, "")),
                    "day_of_week": "",
                    "is_weekend": False
                },
                "metrics": {
                    "volume": float(row.get(volume_col, 0)) if pd.notna(row.get(volume_col)) else 0,
                    "volume_heavy": 0,  # Not in current DB schema
                    "volume_pedestrian": 0,
                    "volume_bicycle": 0,
                },
                "qc": {
                    "status": str(row.get(qc_status_col, "UNKNOWN")) if qc_status_col else "UNKNOWN",
                },
                "raw_data": raw_dict  # Keep original for reference
            }
            
            # Add temporal enrichment if date is parsed
            if date_col in self.df.columns and pd.notna(row.get(date_col)):
                try:
                    date_obj = pd.to_datetime(row[date_col])
                    obs["temporal"]["day_of_week"] = date_obj.strftime('%A')
                    obs["temporal"]["is_weekend"] = date_obj.weekday() >= 5
                except:
                    pass
            
            self.corpus.append(obs)
        
        print(f"Created corpus with {len(self.corpus)} observations")
        return self.corpus
    
    def build_vector_store(self):
        """
        Build FAISS vector store from corpus for semantic search
        """
        print("Building vector store for semantic search...")
        
        # Create text descriptions for each observation
        texts = []
        for obs in self.corpus:
            station_id = obs['station']['id']
            roadway = obs['station'].get('roadway', '')
            date = obs['temporal'].get('date', '')
            dow = obs['temporal'].get('day_of_week', '')
            volume = obs['metrics'].get('volume', 0)
            vol_bike = obs['metrics'].get('volume_bicycle', 0)
            vol_ped = obs['metrics'].get('volume_pedestrian', 0)
            qc = obs['qc'].get('status', 'UNKNOWN')
            
            text = f"Station {station_id} on {roadway}. Date: {date} ({dow}). " \
                   f"Total volume: {volume} vehicles. Bicycle count: {vol_bike}. " \
                   f"Pedestrian count: {vol_ped}. QC status: {qc}."
            texts.append(text)
        
        # Use TF-IDF without stop words to ensure technical terms/IDs are kept
        self.vectorizer = TfidfVectorizer(max_features=200, stop_words=None)
        vectors = self.vectorizer.fit_transform(texts).toarray().astype('float32')
        
        # Build FAISS index
        dimension = vectors.shape[1]
        self.vector_store = faiss.IndexFlatL2(dimension)
        self.vector_store.add(vectors)
        
        print(f"Vector store built with {self.vector_store.ntotal} vectors")
    
    def semantic_search(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        Search corpus using semantic similarity
        
        Args:
            query: Natural language query
            top_k: Number of results to return
            
        Returns:
            List of relevant observations
        """
        if not self.vector_store or not self.vectorizer:
            raise ValueError("Vector store not built. Call build_vector_store() first")
        
        # Vectorize query
        query_vector = self.vectorizer.transform([query]).toarray().astype('float32')
        
        # Search
        distances, indices = self.vector_store.search(query_vector, top_k)
        
        # Return observations
        results = [self.corpus[idx] for idx in indices[0]]
        return results
    
    # ========================================================================
    # USE CASE 1: Natural Language Query Interface
    # ========================================================================
    
    def natural_language_query(self, user_question: str, top_k: int = 10) -> str:
        """
        USE CASE 1: Answer user's natural language question about traffic data
        
        Args:
            user_question: User's question in plain English
            top_k: Number of relevant observations to retrieve
            
        Returns:
            Natural language answer
            
        Example:
            >>> answer = analyzer.natural_language_query(
                "Show me weekday AM peaks where speed violations exceed 40%"
            )
        """
        print(f"\n{'='*60}")
        print("USE CASE 1: Natural Language Query")
        print(f"{'='*60}")
        print(f"Question: {user_question}\n")
        
        # Retrieve relevant data
        relevant_obs = self.semantic_search(user_question, top_k=top_k)
        
        # Build context for the LLM
        context = "Relevant traffic data observations:\n\n"
        for i, obs in enumerate(relevant_obs, 1):
            context += f"Observation {i}:\n"
            context += f"  Station: {obs['station']['id']}"
            if obs['station'].get('roadway'):
                context += f" on {obs['station']['roadway']}"
            context += "\n"
            context += f"  Date: {obs['temporal'].get('date', 'N/A')} ({obs['temporal'].get('day_of_week', 'N/A')})\n"
            context += f"  Volume: {obs['metrics'].get('volume', 'N/A')} vehicles\n"
            if obs['metrics'].get('speed_mean'):
                context += f"  Mean Speed: {obs['metrics']['speed_mean']} mph\n"
            if obs['metrics'].get('speed_p85'):
                context += f"  85th Percentile Speed: {obs['metrics']['speed_p85']} mph\n"
            context += f"  QC Status: {obs['qc'].get('status', 'UNKNOWN')}\n\n"
        
        # Query the LLM
        prompt = f"""You are a traffic engineering data analyst. Answer the following question based on the provided traffic count data.

Question: {user_question}

{context}

Provide a clear, concise answer that:
1. Directly addresses the question
2. Cites specific data points from the observations
3. Uses professional traffic engineering terminology
4. Flags any data quality concerns from QC status
5. If the data doesn't fully answer the question, state what's missing

Answer:"""

        if self.client:
            answer = self._call_llm(prompt)
            confidence = self._estimate_llm_confidence(
                num_relevant_obs=len(relevant_obs),
                use_mock=False,
                has_coord_data=('lat' in self.df.columns and 'lng' in self.df.columns and not self.df['lat'].isna().all() and not self.df['lng'].isna().all()),
                qc_issue_count=sum(1 for obs in relevant_obs if obs['qc'].get('status', 'UNKNOWN') != 'OK')
            )
        else:
            answer = f"[MOCK LLM RESPONSE] User Query: '{user_question}'\n" \
                     f"Analysis: Translating Natural Language to structured DataPoint filters. " \
                     f"Identified S Main St (Station 116) weekday AM peaks. Observations show " \
                     f"volumes peaking between 7:45 AM and 8:45 AM with a total of 920 vehicles " \
                     f"recorded during the peak period."
            confidence = self._estimate_llm_confidence(
                num_relevant_obs=len(relevant_obs),
                use_mock=True,
                has_coord_data=False,
                qc_issue_count=0
            )

        confidence.answer = answer
        print(f"Answer:\n{answer}\n")
        return confidence
    
    # ========================================================================
    # USE CASE 2: Automated Data Quality Narratives
    # ========================================================================
    
    def generate_qc_narrative(self, station_filter: Optional[str] = None) -> str:
        """
        USE CASE 2: Generate automated data quality narrative
        
        Args:
            station_filter: Optional station ID to filter (None = all stations)
            
        Returns:
            Plain-English QC summary
            
        Example:
            >>> qc_report = analyzer.generate_qc_narrative(station_filter="104")
        """
        print(f"\n{'='*60}")
        print("USE CASE 2: Automated Data Quality Narrative")
        print(f"{'='*60}\n")
        
        # Filter data if needed
        if station_filter:
            filtered_corpus = [obs for obs in self.corpus 
                             if obs['station']['id'] == str(station_filter)]
            print(f"Analyzing station {station_filter} ({len(filtered_corpus)} observations)")
        else:
            filtered_corpus = self.corpus
            print(f"Analyzing all stations ({len(filtered_corpus)} observations)")
        
        if not filtered_corpus:
            return "No data found for specified filter."
        
        # Analyze QC issues
        qc_summary = self._analyze_qc_issues(filtered_corpus)
        
        # Build context for the LLM
        context = f"Traffic data QC analysis:\n\n"
        context += f"Total observations: {qc_summary['total_obs']}\n"
        context += f"QC status distribution:\n"
        for status, count in qc_summary['status_counts'].items():
            context += f"  - {status}: {count} ({count/qc_summary['total_obs']*100:.1f}%)\n"
        
        if qc_summary['anomalies']:
            context += f"\nDetected anomalies:\n"
            for anomaly in qc_summary['anomalies'][:10]:  # Limit to 10
                context += f"  - {anomaly}\n"
        
        # Query the LLM for narrative
        prompt = f"""You are a traffic data quality analyst. Generate a concise, professional QC narrative based on this analysis.

{context}

Your narrative should:
1. Summarize the overall data quality
2. Highlight any significant issues or anomalies
3. Provide actionable recommendations (e.g., "Recommend data exclusion for...")
4. Use plain English suitable for both technical and non-technical audiences
5. Be no more than 3-4 paragraphs

QC Narrative:"""

        if self.client:
            narrative = self._call_llm(prompt)
            confidence = self._estimate_llm_confidence(
                num_relevant_obs=len(filtered_corpus),
                use_mock=False,
                has_coord_data=('lat' in self.df.columns and 'lng' in self.df.columns and not self.df['lat'].isna().all() and not self.df['lng'].isna().all()),
                qc_issue_count=len(qc_summary['anomalies'])
            )
        else:
            narrative = f"[MOCK LLM RESPONSE] Data Quality Narrative for Station {station_filter or 'All'}:\n" \
                        f"The data scan for {qc_summary['total_obs']} observations shows high integrity. " \
                        f"However, consistent with Category B (Data Quality) objectives, we cross-referenced " \
                        f"flags and found {len(qc_summary['anomalies'])} anomalies. Station {station_filter or '78'} " \
                        f"showed expected volumes of ~2,100, but actuals were within normal variance for this period."
            confidence = self._estimate_llm_confidence(
                num_relevant_obs=len(filtered_corpus),
                use_mock=True,
                has_coord_data=False,
                qc_issue_count=len(qc_summary['anomalies'])
            )

        confidence.answer = narrative
        print(f"QC Narrative:\n{narrative}\n")
        return confidence
    
    def _analyze_qc_issues(self, observations: List[Dict]) -> Dict:
        """
        Internal helper to analyze QC issues in observations
        """
        summary = {
            'total_obs': len(observations),
            'status_counts': {},
            'anomalies': []
        }
        
        # Count QC statuses
        for obs in observations:
            status = obs['qc'].get('status', 'UNKNOWN')
            summary['status_counts'][status] = summary['status_counts'].get(status, 0) + 1
        
        # Detect anomalies
        volumes = [obs['metrics'].get('volume', 0) for obs in observations if obs['metrics'].get('volume', 0) > 0]
        if volumes:
            mean_vol = np.mean(volumes)
            std_vol = np.std(volumes)
            
            for obs in observations:
                vol = obs['metrics'].get('volume', 0)
                station = obs['station']['id']
                date = obs['temporal'].get('date', 'Unknown')
                
                # Flag outliers (>2 std dev from mean)
                if vol > 0 and abs(vol - mean_vol) > 2 * std_vol:
                    summary['anomalies'].append(
                        f"Station {station} on {date}: Volume {vol} is {'significantly higher' if vol > mean_vol else 'significantly lower'} than average ({mean_vol:.0f})"
                    )
                
                # Flag zero/very low volumes
                if vol < 50 and obs['qc'].get('status') != 'EXCLUDED':
                    summary['anomalies'].append(
                        f"Station {station} on {date}: Very low volume ({vol}), possible equipment issue"
                    )
        
        return summary
    
    # ========================================================================
    # USE CASE 3: Contextual Pattern Detection & Explanation
    # ========================================================================
    
    def detect_patterns(self, 
                       pattern_type: str = 'temporal',
                       station_filter: Optional[str] = None) -> str:
        """
        USE CASE 3: Detect and explain patterns in traffic data
        
        Args:
            pattern_type: Type of pattern to detect ('temporal', 'spatial', 'volume', 'speed')
            station_filter: Optional station ID to focus on
            
        Returns:
            Natural language explanation of detected patterns
            
        Example:
            >>> patterns = analyzer.detect_patterns(
                pattern_type='temporal',
                station_filter='52'
            )
        """
        print(f"\n{'='*60}")
        print("USE CASE 3: Contextual Pattern Detection")
        print(f"{'='*60}")
        print(f"Pattern type: {pattern_type}")
        if station_filter:
            print(f"Station filter: {station_filter}")
        print()
        
        # Filter data
        if station_filter:
            filtered_corpus = [obs for obs in self.corpus 
                             if obs['station']['id'] == str(station_filter)]
        else:
            filtered_corpus = self.corpus
        
        if not filtered_corpus:
            return "No data found for specified filter."
        
        # Analyze patterns based on type
        if pattern_type == 'temporal':
            pattern_data = self._analyze_temporal_patterns(filtered_corpus)
        elif pattern_type == 'volume':
            pattern_data = self._analyze_volume_patterns(filtered_corpus)
        elif pattern_type == 'speed':
            pattern_data = self._analyze_speed_patterns(filtered_corpus)
        else:
            pattern_data = self._analyze_general_patterns(filtered_corpus)
        
        # Generate explanation with the LLM
        prompt = f"""You are a traffic engineering analyst. Analyze the following pattern data and provide insights.

Pattern Analysis Results:
{pattern_data}

Your explanation should:
1. Identify the key patterns or trends
2. Provide possible explanations for these patterns (e.g., correlation with events, land use, time of day)
3. Generate actionable hypotheses for further investigation
4. Suggest potential traffic management or safety interventions if applicable
5. Be written in clear, professional language

Pattern Analysis:"""

        if self.client:
            explanation = self._call_llm(prompt)
            confidence = self._estimate_llm_confidence(
                num_relevant_obs=len(filtered_corpus),
                use_mock=False,
                has_coord_data=('lat' in self.df.columns and 'lng' in self.df.columns and not self.df['lat'].isna().all() and not self.df['lng'].isna().all()),
                qc_issue_count=0
            )
        else:
            explanation = "[MOCK LLM RESPONSE] Contextual Pattern detection (Use Case 3):\n" \
                          "Identified significant Bicycle volumes at Station BikeDirectionTest. " \
                          "Consistent with ISU campus patterns, bicycle traffic shows distinct peaks " \
                          "between 8-9 AM. Weekday volumes for bicycles are approximately 65% higher " \
                          "than weekend volumes, likely correlating with class schedules."
            confidence = self._estimate_llm_confidence(
                num_relevant_obs=len(filtered_corpus),
                use_mock=True,
                has_coord_data=False,
                qc_issue_count=0
            )

        confidence.answer = explanation
        print(f"Pattern Explanation:\n{explanation}\n")
        return confidence
    
    def _analyze_temporal_patterns(self, observations: List[Dict]) -> str:
        """
        Analyze temporal patterns (day of week, seasonal, etc.)
        """
        analysis = "Temporal Pattern Analysis:\n\n"
        
        # Group by day of week
        dow_volumes = {}
        weekend_volumes = []
        weekday_volumes = []
        
        for obs in observations:
            dow = obs['temporal'].get('day_of_week', 'Unknown')
            vol = obs['metrics'].get('volume', 0)
            is_weekend = obs['temporal'].get('is_weekend', False)
            
            if dow != 'Unknown' and vol > 0:
                if dow not in dow_volumes:
                    dow_volumes[dow] = []
                dow_volumes[dow].append(vol)
                
                if is_weekend:
                    weekend_volumes.append(vol)
                else:
                    weekday_volumes.append(vol)
        
        # Summarize
        analysis += "Day of Week Averages:\n"
        for dow in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']:
            if dow in dow_volumes:
                avg = np.mean(dow_volumes[dow])
                analysis += f"  {dow}: {avg:.0f} vehicles (n={len(dow_volumes[dow])})\n"
        
        if weekend_volumes and weekday_volumes:
            weekend_avg = np.mean(weekend_volumes)
            weekday_avg = np.mean(weekday_volumes)
            pct_diff = ((weekday_avg - weekend_avg) / weekend_avg) * 100
            analysis += f"\nWeekday vs Weekend:\n"
            analysis += f"  Weekday average: {weekday_avg:.0f} vehicles\n"
            analysis += f"  Weekend average: {weekend_avg:.0f} vehicles\n"
            analysis += f"  Difference: {pct_diff:+.1f}%\n"
        
        return analysis
    
    def _analyze_volume_patterns(self, observations: List[Dict]) -> str:
        """
        Analyze volume patterns and trends
        """
        analysis = "Volume Pattern Analysis:\n\n"
        
        volumes = [obs['metrics'].get('volume', 0) for obs in observations if obs['metrics'].get('volume', 0) > 0]
        
        if volumes:
            analysis += f"Total observations: {len(volumes)}\n"
            analysis += f"Mean volume: {np.mean(volumes):.0f} vehicles\n"
            analysis += f"Median volume: {np.median(volumes):.0f} vehicles\n"
            analysis += f"Std deviation: {np.std(volumes):.0f}\n"
            analysis += f"Min volume: {np.min(volumes):.0f}\n"
            analysis += f"Max volume: {np.max(volumes):.0f}\n"
            
            # Identify high/low volume periods
            high_threshold = np.percentile(volumes, 75)
            low_threshold = np.percentile(volumes, 25)
            
            high_vol_obs = [obs for obs in observations if obs['metrics'].get('volume', 0) > high_threshold]
            low_vol_obs = [obs for obs in observations if 0 < obs['metrics'].get('volume', 0) < low_threshold]
            
            analysis += f"\nHigh volume periods (>75th percentile = {high_threshold:.0f}):\n"
            for obs in high_vol_obs[:5]:
                analysis += f"  - Station {obs['station']['id']} on {obs['temporal'].get('date')}: {obs['metrics']['volume']:.0f} vehicles\n"
            
            analysis += f"\nLow volume periods (<25th percentile = {low_threshold:.0f}):\n"
            for obs in low_vol_obs[:5]:
                analysis += f"  - Station {obs['station']['id']} on {obs['temporal'].get('date')}: {obs['metrics']['volume']:.0f} vehicles\n"
        
        return analysis
    
    def _analyze_speed_patterns(self, observations: List[Dict]) -> str:
        """
        Analyze speed patterns
        """
        analysis = "Speed Pattern Analysis:\n\n"
        
        speeds = [obs['metrics'].get('speed_mean', 0) for obs in observations 
                 if obs['metrics'].get('speed_mean') is not None and obs['metrics'].get('speed_mean') > 0]
        
        if speeds:
            analysis += f"Mean speed observations: {len(speeds)}\n"
            analysis += f"Average speed: {np.mean(speeds):.1f} mph\n"
            analysis += f"Median speed: {np.median(speeds):.1f} mph\n"
            analysis += f"Std deviation: {np.std(speeds):.1f} mph\n"
            
            # Check for speeding (assuming posted limit is common value)
            # This is a placeholder - should use actual posted speed limit from data
            analysis += f"\nNote: Actual speeding analysis requires posted speed limit data\n"
        else:
            analysis += "No speed data available in dataset\n"
        
        return analysis
    
    def _analyze_general_patterns(self, observations: List[Dict]) -> str:
        """
        General pattern analysis across all dimensions
        """
        return f"General analysis of {len(observations)} observations:\n" + \
               self._analyze_temporal_patterns(observations) + "\n" + \
               self._analyze_volume_patterns(observations)

    def infer_location_context(self) -> str:
        """Infer a concise location summary from the loaded data."""
        if self.df is None or self.df.empty:
            return "an unknown geographic region"

        station_count = int(self.df['station_id'].nunique()) if 'station_id' in self.df.columns else 0
        roadways = []
        if 'roadway' in self.df.columns:
            roadways = self.df['roadway'].dropna().astype(str)
            roadways = [r for r in roadways if r and r != '']

        lat_vals = self.df['lat'].dropna() if 'lat' in self.df.columns else pd.Series([], dtype=float)
        lng_vals = self.df['lng'].dropna() if 'lng' in self.df.columns else pd.Series([], dtype=float)

        location_parts = []
        if not lat_vals.empty and not lng_vals.empty:
            lat = float(lat_vals.median())
            lng = float(lng_vals.median())
            location_parts.append(f"a cluster of intersections around latitude {lat:.5f}, longitude {lng:.5f}")
        else:
            location_parts.append("a set of local intersections")

        location_parts.append(f"covering {station_count} unique station(s)")

        if roadways:
            top_roadways = self.df['roadway'].value_counts().head(5).index.tolist()
            location_parts.append("major corridors such as " + ", ".join(top_roadways[:3]))

        return ", ".join(location_parts)

    # ========================================================================
    # USE CASE 4: The Agentic Consultant (LLM Exploration)
    # ========================================================================
    
    def run_agentic_consultation(self, focus_area: str = "Safety and Infrastructure") -> str:
        """
        USE CASE 4: The "Crazy" LLM Exploration.
        LLM acts as an autonomous consultant synthesizing all data modes and spatial insights.
        """
        print(f"\n{'='*60}")
        print(f"USE CASE 4: Agentic Consultant Exploration")
        print(f"Goal: {focus_area}")
        print(f"{'='*60}\n")
        
        # Aggregate high-level insights to give the LLM "vision" of the network
        total_vol = self.df['volume'].sum()
        max_bike_station = self.df.groupby('station_id')['volume_bicycle'].sum().idxmax()
        top_conflict_stations = self.df.groupby('station_id').agg({
            'volume': 'mean',
            'volume_bicycle': 'mean',
            'volume_pedestrian': 'mean'
        }).nlargest(3, 'volume_bicycle').to_string()
        location_context = self.infer_location_context()
        
        prompt = f"""You are a Senior Traffic Engineering Consultant for a local transportation agency.
The dataset appears to cover {location_context}.

DATA SYNTHESIS:
- Total Network Volume Processed: {total_vol:,.0f} vehicles.
- Primary Bicycle Activity Hub: Station {max_bike_station}.
- Top 3 Conflict Zones (Avg Volumes):
{top_conflict_stations}

Based on the available intersection and roadway data, provide a "Consultant's Safety Memo" tailored to this location and its traffic context.

Your thinking must be "Out-of-the-Box":
1. Hypothesize WHY the bicycle peaks occur based on local conditions, land use, or nearby activity generators.
2. Identify the most dangerous "Safety Gap" in the existing network based on volume/bike/ped ratios.
3. Propose 2 specific "Crazy" but feasible infrastructure or operational interventions.
4. Predict how a 10% shift from cars to bikes would impact the most congested station identified.

Provide a professional, strategic narrative.

Memo:"""

        if self.client:
            memo = self._call_llm(prompt)
            confidence = self._estimate_llm_confidence(
                num_relevant_obs=len(self.df) if self.df is not None else 0,
                use_mock=False,
                has_coord_data=('lat' in self.df.columns and 'lng' in self.df.columns and not self.df['lat'].isna().all() and not self.df['lng'].isna().all()) if self.df is not None else False,
                qc_issue_count=0
            )
        else:
            memo = f"[MOCK AGENT RESPONSE] MEMO: ISU TRAFFIC INTELLIGENCE\n" \
                   f"The analysis of Station {max_bike_station} reveals a critical modal conflict. " \
                   f"Hypothesis: Peaks correlate with the 8 AM ISU engineering lecture blocks. " \
                   f"Safety Gap: Conflict indices at the top 3 stations suggest that vehicle turn volumes " \
                   f"are cutting across direct student desire paths. \n" \
                   f"Intervention 1: Implement 'Scramble' pedestrian phases during class change minutes.\n" \
                   f"Intervention 2: Deploy AI-enabled signal pre-emption for bicycle groups to clear the intersection faster."
            confidence = self._estimate_llm_confidence(
                num_relevant_obs=len(self.df) if self.df is not None else 0,
                use_mock=True,
                has_coord_data=False,
                qc_issue_count=0
            )

        confidence.answer = memo
        print(f"Consultant Memo:\n{memo}\n")
        return confidence

    # ========================================================================
    # Utility Methods
    # ========================================================================
    
    def save_corpus(self, output_path: str):
        """
        Save JSON corpus to file
        """
        with open(output_path, 'w') as f:
            for obs in self.corpus:
                f.write(json.dumps(obs) + '\n')
        print(f"Corpus saved to {output_path}")

    def create_visualizations(self, output_dir: str = "visualizations"):
        """
        Generate and save advanced, impressive visual analytics
        """
        if self.df is None or self.df.empty:
            print("No data available for visualization.")
            return

        os.makedirs(output_dir, exist_ok=True)
        print(f"Generating advanced visualizations for {len(self.df)} records in {output_dir}/...")
        
        # Set professional style
        sns.set_theme(style="whitegrid", palette="muted")
        plt.rcParams['font.family'] = 'sans-serif'

        # 1. THE TRAFFIC PULSE (Heatmap) - Solves overlapping and shows scale
        plt.figure(figsize=(16, 12))
        plot_df = self.df.copy()
        plot_df['hour'] = plot_df['date'].dt.hour
        pivot_df = plot_df.pivot_table(index='station_id', columns='hour', values='volume', aggfunc='mean')
        
        sns.heatmap(pivot_df, cmap="YlGnBu", annot=False, cbar_kws={'label': 'Average Vehicle Volume'})
        plt.title('The Traffic Pulse: Hourly Intensity Across All Stations', fontsize=20, pad=30)
        plt.xlabel('Hour of Day (24h)', fontsize=14)
        plt.ylabel('Station ID', fontsize=14)
        plt.savefig(f"{output_dir}/01_traffic_pulse_heatmap.png", dpi=300, bbox_inches='tight')
        plt.close()

        # 2. VULNERABILITY RADAR (Conflict Zones) - Out of the box thinking
        plt.figure(figsize=(10, 8))
        # Aggregate by station
        station_total = self.df.groupby('station_id').agg({
            'volume': 'sum',
            'volume_bicycle': 'sum',
            'volume_pedestrian': 'sum'
        }).reset_index()
        
        # Bubble plot: Bike vs Ped, size = All Vehicles
        scatter = plt.scatter(
            station_total['volume_bicycle'], 
            station_total['volume_pedestrian'],
            s=station_total['volume']/100, # Size relative to total traffic
            alpha=0.6, 
            c=station_total['volume'], 
            cmap='plasma'
        )
        
        # Label top 5 conflict stations to avoid mess
        top_conflict = station_total.nlargest(5, 'volume_bicycle')
        for i, txt in enumerate(top_conflict['station_id']):
            plt.annotate(txt, (top_conflict['volume_bicycle'].iloc[i], top_conflict['volume_pedestrian'].iloc[i]), 
                         xytext=(5,5), textcoords='offset points', fontsize=10, weight='bold')

        plt.colorbar(scatter, label='Total Vehicle Volume')
        plt.title('VRU Conflict Radar: Pedestrian & Bicycle Density', fontsize=18, pad=20)
        plt.xlabel('Cumulative Bicycle Volume', fontsize=14)
        plt.ylabel('Cumulative Pedestrian Volume', fontsize=14)
        plt.savefig(f"{output_dir}/02_vru_conflict_radar.png", dpi=300, bbox_inches='tight')
        plt.close()

        # 3. SPATIAL INSIGHT MAP (using Lat/Lng) - High impact
        if 'lat' in self.df.columns and self.df['lat'].sum() != 0:
            plt.figure(figsize=(12, 10))
            # Average volume and mode split per location
            loc_data = self.df.groupby(['lat', 'lng', 'station_id'])['volume'].mean().reset_index()
            
            sns.scatterplot(data=loc_data, x='lng', y='lat', size='volume', hue='volume', 
                            palette='coolwarm', sizes=(100, 1000), alpha=0.7)
            
            plt.title('Spatial Distribution of Traffic Intensity', fontsize=18, pad=20)
            plt.xlabel('Longitude', fontsize=12)
            plt.ylabel('Latitude', fontsize=12)
            plt.legend(title='Avg Volume', bbox_to_anchor=(1.05, 1), loc='upper left')
            plt.savefig(f"{output_dir}/03_spatial_distribution.png", dpi=300, bbox_inches='tight')
            plt.close()

        # 4. MODE DENSITY VIOLINS (Data distribution)
        plt.figure(figsize=(12, 6))
        # Melt data for visualization
        melted_df = pd.melt(self.df, id_vars=['station_id'], 
                            value_vars=['volume_heavy', 'volume_pedestrian', 'volume_bicycle'],
                            var_name='Mode', value_name='Count')
        
        sns.violinplot(data=melted_df, x='Mode', y='Count', split=True, inner="quart", palette="Pastel1")
        plt.title('Mode Density & Variance Analysis', fontsize=18, pad=20)
        plt.ylabel('Volume Per Time Period', fontsize=14)
        plt.xticks([0, 1, 2], ['Heavy Trucks', 'Pedestrians', 'Bicycles'])
        plt.savefig(f"{output_dir}/04_mode_density_variance.png", dpi=300, bbox_inches='tight')
        plt.close()

        print(f"✅ Advanced Visualizations saved to {output_dir}/")

    def generate_sample_queries(self) -> List[str]:
        """
        Generate sample queries based on the data
        """
        queries = [
            "What are the traffic volumes at all stations?",
            "Which stations have the highest traffic volumes?",
            "Are there any data quality issues I should be aware of?",
            "Show me weekday traffic patterns",
            "What's the difference between weekday and weekend volumes?",
            "Identify any anomalous volume readings",
            "What patterns do you see in the data?",
            "Which days have the highest traffic?",
        ]
        
        # Add station-specific queries if we have station data
        if self.corpus:
            unique_stations = list(set(obs['station']['id'] for obs in self.corpus))
            if unique_stations:
                sample_station = unique_stations[0]
                queries.extend([
                    f"Tell me about station {sample_station}",
                    f"What are the traffic patterns at station {sample_station}?",
                ])
        
        return queries


# ========================================================================
# Example Usage Script
# ========================================================================

def main():
    """
    Example script demonstrating all three use cases
    """
    print("QC DataPoint LLM Analytics System")
    print("=" * 60)
    
    # Initialize analyzer
    analyzer = QCDataPointAnalyzer()
    
    # Find the data directory
    data_dirs = glob.glob("export_traffic_data_*")
    if not data_dirs or not os.path.isdir(data_dirs[0]):
        print("\nERROR: No directory matching 'export_traffic_data_*' found!")
        return
        
    data_dir = data_dirs[0]
    
    print(f"\nStep 1: Loading Intersection CSV data from {data_dir}...")
    df = analyzer.load_intersection_directory(data_dir)
    
    # Convert to JSON corpus
    print("\nStep 2: Converting to JSON corpus...")
    analyzer.csv_to_json_corpus(
        station_col='station_id',
        date_col='date',
        volume_col='volume',
        roadway_col='roadway',
        qc_status_col='qc_status'
    )
    
    # Build vector store
    print("\nStep 3: Building vector store...")
    analyzer.build_vector_store()
    
    # Save corpus (optional)
    analyzer.save_corpus("qc_traffic_corpus.jsonl")
    
    print("\n" + "=" * 60)
    print("RUNNING THREE CORE USE CASES")
    print("=" * 60)
    
    # USE CASE 1: Natural Language Query
    print("\n\nTEST 1/3: Natural Language Query Interface")
    print("-" * 60)
    # Using example from Category A slide
    answer1 = analyzer.natural_language_query(
        "Show me weekday AM peaks on S Main St (Station 116)"
    )
    
    # USE CASE 2: Automated QC Narrative
    print("\n\nTEST 2/3: Automated Data Quality Narrative")
    print("-" * 60)
    # Using example from Use Case 2 slide
    qc_report = analyzer.generate_qc_narrative(station_filter="116")
    
    # USE CASE 3: Pattern Detection
    print("\n\nTEST 3/3: Contextual Pattern Detection")
    print("-" * 60)
    # Using example from Use Case 3 slide (Bicycle focus)
    pattern_analysis = analyzer.detect_patterns(pattern_type='temporal', station_filter='BikeDirectionTest')
    
    # USE CASE 4: Agentic Consultant
    print("\n\nTEST 4/4: THE 'CRAZY' LLM CONSULTANT")
    print("-" * 60)
    consultant_memo = analyzer.run_agentic_consultation()
    
    # NEW: Create Visualizations
    print("\n\nSTEP 5: Generating Charts")
    print("-" * 60)
    analyzer.create_visualizations()
    
    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETE")
    print("=" * 60)
    
    # Show sample queries
    print("\n\nSample queries you can try:")
    for i, query in enumerate(analyzer.generate_sample_queries()[:5], 1):
        print(f"  {i}. {query}")
    
    print("\n\nTo use this system interactively:")
    print("  analyzer = QCDataPointAnalyzer()")
    print("  analyzer.load_csv_data('your_file.csv')")
    print("  analyzer.csv_to_json_corpus(...)")  
    print("  analyzer.build_vector_store()")
    print("  answer = analyzer.natural_language_query('your question here')")


if __name__ == "__main__":
    main()